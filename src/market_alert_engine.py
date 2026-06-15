"""Calm market alert engine.

This module records market context events into local DB for the brain, but it no
longer spams Telegram with raw CHoCH/OB/rejection alerts by default. Raw alerts
were confusing because a single touch/rejection does not equal a trade setup.

Telegram rule:
- Entry signal messages are still sent by the signal engine.
- TP/SL event messages are still sent by signal_tracker.
- Market alerts are recorded silently unless explicitly enabled in config:

market_alerts:
  enabled: true
  send_raw_to_telegram: false
  telegram_event_whitelist: []
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.market_memory import MarketMemory
from src.market_structure import get_swings, calculate_bias
from src.telegram_notifier import send_telegram_message, telegram_is_configured


def _f(value, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return default


def _fmt(value) -> str:
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "N/A"


def _candle_time(candle: Dict[str, Any]) -> str:
    return str(candle.get('open_time') or candle.get('time') or candle.get('timestamp') or '')


class MarketAlertEngine:
    def __init__(self, storage, symbol: str = 'XAU/USD', config: Optional[Dict[str, Any]] = None):
        self.storage = storage
        self.symbol = symbol
        self.config = config or {}
        self.memory = MarketMemory(storage)
        cfg = (self.config.get('market_alerts') or {})
        self.enabled = bool(cfg.get('enabled', True))
        self.send_raw_to_telegram = bool(cfg.get('send_raw_to_telegram', False))
        self.telegram_event_whitelist = set(str(x).upper() for x in (cfg.get('telegram_event_whitelist') or []))
        self.touch_tolerance = float(cfg.get('touch_tolerance_points', 0.35))
        self.break_buffer = float(cfg.get('break_buffer_points', 0.25))
        self.sweep_buffer = float(cfg.get('sweep_buffer_points', 0.15))
        self.retest_tolerance = float(cfg.get('retest_tolerance_points', 0.60))
        self.dedupe_minutes = int(cfg.get('dedupe_minutes', 60))
        self.priority_min = str(cfg.get('min_priority', 'MEDIUM')).upper()
        self.enable_ob_touch_alerts = bool(cfg.get('enable_ob_touch_alerts', False))
        self.enable_rejection_alerts = bool(cfg.get('enable_rejection_alerts', False))
        self.enable_choch_alerts = bool(cfg.get('enable_choch_alerts', False))

    def _priority_allowed(self, priority: str) -> bool:
        rank = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
        return rank.get(str(priority or 'LOW').upper(), 1) >= rank.get(self.priority_min, 1)

    def _should_send_telegram(self, event_type: str, priority: str) -> bool:
        if not self.send_raw_to_telegram:
            return False
        if not telegram_is_configured():
            return False
        if not self._priority_allowed(priority):
            return False
        event = str(event_type or '').upper()
        if self.telegram_event_whitelist and event not in self.telegram_event_whitelist:
            return False
        return True

    def _notify(self, event_type: str, timeframe: str, direction: str, level: Optional[float],
                price: float, message: str, priority: str = 'LOW', raw: Optional[Dict[str, Any]] = None,
                dedupe_minutes: Optional[int] = None) -> bool:
        if not self.enabled:
            return False
        priority = str(priority or 'LOW').upper()
        if not self._priority_allowed(priority):
            return False
        raw = raw or {}
        ok = self.memory.record_event(
            self.symbol, timeframe, event_type, direction, level, price,
            weight={'LOW': 1.0, 'MEDIUM': 1.5, 'HIGH': 2.0}.get(priority, 1.0),
            source='MARKET_CONTEXT_SILENT', raw=raw,
            dedupe_window_minutes=dedupe_minutes or self.dedupe_minutes,
        )
        if ok and self._should_send_telegram(event_type, priority):
            send_telegram_message(message)
        return ok

    def process_tick(self, symbol: str, price: float, timestamp: Any = None) -> None:
        if not self.enabled:
            return
        try:
            price = float(price)
            if self.enable_ob_touch_alerts:
                self._record_ob_touch(price)
        except Exception:
            return

    def process_closed_candle(self, candle: Any) -> None:
        if not self.enabled:
            return
        try:
            tf = str(getattr(candle, 'timeframe', '') or '').upper()
            if tf not in {'M5', 'M15', 'H1'}:
                return
            c = {
                'open': _f(getattr(candle, 'open', None)),
                'high': _f(getattr(candle, 'high', None)),
                'low': _f(getattr(candle, 'low', None)),
                'close': _f(getattr(candle, 'close', None)),
                'open_time': getattr(candle, 'open_time', None),
                'close_time': getattr(candle, 'close_time', None),
            }
            candles = self.storage.get_recent_candles(self.symbol, tf, 80)
            if not candles or _candle_time(candles[-1]) != _candle_time(c):
                candles = (candles + [c])[-80:]
            if len(candles) < 16:
                return
            self._record_break_and_sweep(tf, candles)
            self._record_bos_choch(tf, candles)
            if self.enable_rejection_alerts:
                self._record_rejection(tf, candles)
        except Exception:
            return

    def _record_ob_touch(self, price: float) -> None:
        try:
            rows = self.storage.fetchall(
                """
                SELECT * FROM active_order_blocks
                WHERE status IN ('VALID','ACTIVE')
                ORDER BY id DESC LIMIT 30
                """
            )
        except Exception:
            rows = []
        for ob in rows:
            low, high = _f(ob.get('low')), _f(ob.get('high'))
            if low <= price <= high:
                ob_type = str(ob.get('type') or ob.get('direction') or 'OB')
                tf = str(ob.get('timeframe') or 'NA')
                msg = (
                    "📦 MARKET CONTEXT: OB TOUCHED\n"
                    f"TF: {tf}\nType: {ob_type} OB\n"
                    f"Area: {_fmt(low)} - {_fmt(high)}\n"
                    f"Price: {_fmt(price)}\n"
                    "Note: Ini hanya konteks, bukan sinyal entry."
                )
                self._notify('OB_TOUCHED', tf, ob_type.upper(), round((low + high) / 2, 3), price, msg, 'MEDIUM', raw=ob)
                break

    def _record_break_and_sweep(self, tf: str, candles: List[Dict[str, Any]]) -> None:
        last = candles[-1]
        prev = candles[-13:-1] if len(candles) >= 13 else candles[:-1]
        if len(prev) < 5:
            return
        prev_high = max(_f(c.get('high')) for c in prev)
        prev_low = min(_f(c.get('low')) for c in prev)
        close = _f(last.get('close'))
        high = _f(last.get('high'))
        low = _f(last.get('low'))
        if close > prev_high + self.break_buffer:
            msg = (
                "📊 MARKET CONTEXT: BREAK HIGH\n"
                f"TF: {tf}\nLevel: {_fmt(prev_high)}\nClose: {_fmt(close)}\n"
                "Note: Konteks saja; tunggu setup entry terpisah."
            )
            self._notify('BREAK_RESISTANCE', tf, 'bullish', prev_high, close, msg, 'HIGH', raw=last)
        if close < prev_low - self.break_buffer:
            msg = (
                "📊 MARKET CONTEXT: BREAK LOW\n"
                f"TF: {tf}\nLevel: {_fmt(prev_low)}\nClose: {_fmt(close)}\n"
                "Note: Konteks saja; tunggu setup entry terpisah."
            )
            self._notify('BREAK_SUPPORT', tf, 'bearish', prev_low, close, msg, 'HIGH', raw=last)
        if high > prev_high + self.sweep_buffer and close < prev_high:
            msg = (
                "🧹 MARKET CONTEXT: SWEEP HIGH\n"
                f"TF: {tf}\nSwept: {_fmt(prev_high)}\nClose: {_fmt(close)}\n"
                "Note: Ini sweep + close balik, bukan entry otomatis."
            )
            self._notify('SWEEP_HIGH', tf, 'bearish_watch', prev_high, close, msg, 'HIGH', raw=last)
        if low < prev_low - self.sweep_buffer and close > prev_low:
            msg = (
                "🧹 MARKET CONTEXT: SWEEP LOW\n"
                f"TF: {tf}\nSwept: {_fmt(prev_low)}\nClose: {_fmt(close)}\n"
                "Note: Ini sweep + close balik, bukan entry otomatis."
            )
            self._notify('SWEEP_LOW', tf, 'bullish_watch', prev_low, close, msg, 'HIGH', raw=last)

    def _record_bos_choch(self, tf: str, candles: List[Dict[str, Any]]) -> None:
        if not self.enable_choch_alerts:
            # Tetap catat BOS sederhana, tapi jangan klaim CHoCH ke Telegram.
            pass
        highs, lows = get_swings(candles[:-1], 3, 2)
        last = candles[-1]
        close = _f(last.get('close'))
        body = abs(_f(last.get('close')) - _f(last.get('open')))
        rng = max(_f(last.get('high')) - _f(last.get('low')), 0.01)
        strong_close = body / rng >= 0.45
        bias = calculate_bias(candles[:-1]) if len(candles) >= 20 else 'neutral'
        if highs:
            level = _f(highs[-1].get('high'))
            if close > level + self.break_buffer and strong_close:
                ev = 'CHoCH_BULLISH' if bias == 'bearish' else 'BOS_BULLISH'
                title = 'CHoCH BULLISH' if bias == 'bearish' else 'BOS BULLISH'
                msg = (
                    f"📊 MARKET CONTEXT: {title}\n"
                    f"TF: {tf}\nLevel: {_fmt(level)}\nClose: {_fmt(close)}\nPrevious bias: {bias}\n"
                    "Note: Structure context only, bukan validasi entry."
                )
                self._notify(ev, tf, 'bullish', level, close, msg, 'HIGH', raw=last)
        if lows:
            level = _f(lows[-1].get('low'))
            if close < level - self.break_buffer and strong_close:
                ev = 'CHoCH_BEARISH' if bias == 'bullish' else 'BOS_BEARISH'
                title = 'CHoCH BEARISH' if bias == 'bullish' else 'BOS BEARISH'
                msg = (
                    f"📊 MARKET CONTEXT: {title}\n"
                    f"TF: {tf}\nLevel: {_fmt(level)}\nClose: {_fmt(close)}\nPrevious bias: {bias}\n"
                    "Note: Structure context only, bukan validasi entry."
                )
                self._notify(ev, tf, 'bearish', level, close, msg, 'HIGH', raw=last)

    def _record_rejection(self, tf: str, candles: List[Dict[str, Any]]) -> None:
        last = candles[-1]
        prev = candles[-13:-1]
        if len(prev) < 5:
            return
        close, open_, high, low = [_f(last.get(k)) for k in ('close', 'open', 'high', 'low')]
        body = abs(close - open_)
        prev_high = max(_f(c.get('high')) for c in prev)
        prev_low = min(_f(c.get('low')) for c in prev)
        upper = high - max(open_, close)
        lower = min(open_, close) - low
        if high >= prev_high - self.touch_tolerance and upper >= max(body * 2.0, 1.0) and close < prev_high:
            msg = (
                "⚠️ MARKET CONTEXT: POSSIBLE REJECTION HIGH\n"
                f"TF: {tf}\nResistance: {_fmt(prev_high)}\nClose: {_fmt(close)}\n"
                "Note: Possible only, bukan konfirmasi entry."
            )
            self._notify('REJECTION_RESISTANCE', tf, 'bearish_watch', prev_high, close, msg, 'MEDIUM', raw=last)
        if low <= prev_low + self.touch_tolerance and lower >= max(body * 2.0, 1.0) and close > prev_low:
            msg = (
                "⚠️ MARKET CONTEXT: POSSIBLE REJECTION LOW\n"
                f"TF: {tf}\nSupport: {_fmt(prev_low)}\nClose: {_fmt(close)}\n"
                "Note: Possible only, bukan konfirmasi entry."
            )
            self._notify('REJECTION_SUPPORT', tf, 'bullish_watch', prev_low, close, msg, 'MEDIUM', raw=last)
