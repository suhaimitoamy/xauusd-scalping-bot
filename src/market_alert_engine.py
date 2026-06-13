"""V6 market alert engine.

Telegram market alerts only. This module does not create entry signals.
It reuses BOT DATA (candles, OB, SD, liquidity) and records deduped events
in brain_events so the same level does not spam Telegram.
"""
from __future__ import annotations

from datetime import datetime, timezone, time as dtime
from typing import Any, Dict, List, Optional, Tuple

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
        self.touch_tolerance = float(cfg.get('touch_tolerance_points', 0.35))
        self.break_buffer = float(cfg.get('break_buffer_points', 0.25))
        self.sweep_buffer = float(cfg.get('sweep_buffer_points', 0.15))
        self.retest_tolerance = float(cfg.get('retest_tolerance_points', 0.60))
        self.dedupe_minutes = int(cfg.get('dedupe_minutes', 25))
        self.session_tz_offset = int(cfg.get('session_utc_offset_hours', 7))  # WIB default
        self.priority_min = str(cfg.get('min_priority', 'LOW')).upper()

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
            source='V6_MARKET_ALERT', raw=raw,
            dedupe_window_minutes=dedupe_minutes or self.dedupe_minutes,
        )
        if ok and telegram_is_configured():
            send_telegram_message(message)
        return ok

    def _priority_allowed(self, priority: str) -> bool:
        rank = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
        return rank.get(priority, 1) >= rank.get(self.priority_min, 1)

    def process_tick(self, symbol: str, price: float, timestamp: Any = None) -> None:
        if not self.enabled:
            return
        try:
            price = float(price)
            self._alert_ob_touched(price)
            # DISABLED PER USER REQUEST
            # self._alert_support_resistance_touched(price)
            # self._alert_ssl_bsl_touched(price)
            self._alert_session_high_low_touched(price)
            self._alert_premium_discount_ote(price)
        except Exception:
            return

    def process_closed_candle(self, candle: Any) -> None:
        if not self.enabled:
            return
        try:
            tf = str(getattr(candle, 'timeframe', '') or '').upper()
            if tf not in {'M1', 'M5', 'M15', 'H1'}:
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
            if len(candles) < 6:
                return
            self._alert_break_and_sweep(tf, candles)
            self._alert_bos_choch(tf, candles)
            self._alert_retest_rejection_displacement(tf, candles)
            if tf == 'M15':
                self._alert_m15_candlestick(candles)
            if tf in {'M5', 'M15'}:
                self._alert_chart_patterns(tf, candles)
                self._alert_judas_swing(tf, candles)
        except Exception:
            return

    # 4. OB touched
    def _alert_ob_touched(self, price: float) -> None:
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
                    f"📦 MARKET ALERT: HARGA MASUK OB\n"
                    f"TF: {tf}\nType: {ob_type} OB\n"
                    f"Area: {_fmt(low)} - {_fmt(high)}\n"
                    f"Harga sekarang: {_fmt(price)}\n"
                    f"Priority: MEDIUM\nSource: BOT DATA"
                )
                self._notify('OB_TOUCHED', tf, ob_type.upper(), round((low + high) / 2, 3), price, msg, 'MEDIUM', raw=ob)
                break

    # 5. Support / Resistance touched
    def _alert_support_resistance_touched(self, price: float) -> None:
        candles = self.storage.get_recent_candles(self.symbol, 'M15', 80)
        if len(candles) < 12:
            candles = self.storage.get_recent_candles(self.symbol, 'M5', 80)
        if len(candles) < 12:
            return
        highs, lows = get_swings(candles, 2, 2)
        levels: List[Tuple[str, float]] = []
        levels += [('RESISTANCE', _f(x.get('high'))) for x in highs[-8:]]
        levels += [('SUPPORT', _f(x.get('low'))) for x in lows[-8:]]
        if not levels:
            return
        kind, level = min(levels, key=lambda kv: abs(kv[1] - price))
        if abs(level - price) <= self.touch_tolerance:
            msg = (
                f"📍 MARKET ALERT: HARGA DI {kind}\n"
                f"Level: {_fmt(level)}\nHarga sekarang: {_fmt(price)}\n"
                f"TF basis: M15/M5 swing\nPriority: LOW\nSource: BOT DATA"
            )
            self._notify(f'{kind}_TOUCHED', 'M15', kind.lower(), level, price, msg, 'LOW')

    # 6 / 7. Break and sweep
    def _alert_break_and_sweep(self, tf: str, candles: List[Dict[str, Any]]) -> None:
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
                f"🚀 MARKET ALERT: BREAK RESISTANCE\n"
                f"TF: {tf}\nBreak level: {_fmt(prev_high)}\n"
                f"Close: {_fmt(close)}\nPriority: HIGH\nSource: BOT DATA"
            )
            self._notify('BREAK_RESISTANCE', tf, 'bullish', prev_high, close, msg, 'HIGH', raw=last)
        if close < prev_low - self.break_buffer:
            msg = (
                f"🩸 MARKET ALERT: BREAK SUPPORT\n"
                f"TF: {tf}\nBreak level: {_fmt(prev_low)}\n"
                f"Close: {_fmt(close)}\nPriority: HIGH\nSource: BOT DATA"
            )
            self._notify('BREAK_SUPPORT', tf, 'bearish', prev_low, close, msg, 'HIGH', raw=last)
        if high > prev_high + self.sweep_buffer and close < prev_high:
            msg = (
                f"🧹 MARKET ALERT: SWEEP HIGH / BSL\n"
                f"TF: {tf}\nSwept level: {_fmt(prev_high)}\n"
                f"Sweep high: {_fmt(high)}\nClose reclaim: {_fmt(close)}\n"
                f"Priority: HIGH\nSource: BOT DATA"
            )
            self._notify('SWEEP_HIGH', tf, 'bearish_watch', prev_high, close, msg, 'HIGH', raw=last)
        if low < prev_low - self.sweep_buffer and close > prev_low:
            msg = (
                f"🧹 MARKET ALERT: SWEEP LOW / SSL\n"
                f"TF: {tf}\nSwept level: {_fmt(prev_low)}\n"
                f"Sweep low: {_fmt(low)}\nClose reclaim: {_fmt(close)}\n"
                f"Priority: HIGH\nSource: BOT DATA"
            )
            self._notify('SWEEP_LOW', tf, 'bullish_watch', prev_low, close, msg, 'HIGH', raw=last)

    # 8. M15 candlestick pinbar / engulfing
    def _alert_m15_candlestick(self, candles: List[Dict[str, Any]]) -> None:
        if len(candles) < 2:
            return
        c = candles[-1]
        p = candles[-2]
        o, h, l, cl = [_f(c.get(k)) for k in ('open', 'high', 'low', 'close')]
        po, pc = _f(p.get('open')), _f(p.get('close'))
        body = max(abs(cl - o), 0.01)
        upper = h - max(o, cl)
        lower = min(o, cl) - l
        rng = max(h - l, 0.01)
        pattern = None
        direction = 'neutral'
        if lower >= body * 2.0 and upper <= body * 0.7 and body / rng >= 0.18:
            pattern = 'Bullish Pinbar'
            direction = 'bullish_watch'
        elif upper >= body * 2.0 and lower <= body * 0.7 and body / rng >= 0.18:
            pattern = 'Bearish Pinbar'
            direction = 'bearish_watch'
        elif cl > o and pc < po and cl >= po and o <= pc:
            pattern = 'Bullish Engulfing'
            direction = 'bullish'
        elif cl < o and pc > po and cl <= po and o >= pc:
            pattern = 'Bearish Engulfing'
            direction = 'bearish'
        if pattern:
            msg = (
                f"🕯️ MARKET ALERT: M15 {pattern.upper()}\n"
                f"Open: {_fmt(o)} | High: {_fmt(h)} | Low: {_fmt(l)} | Close: {_fmt(cl)}\n"
                f"Priority: MEDIUM\nSource: BOT DATA"
            )
            self._notify('M15_CANDLE_' + pattern.upper().replace(' ', '_'), 'M15', direction, cl, cl, msg, 'MEDIUM', raw=c)

    # 9 / 10 / 11. Chart patterns
    def _alert_chart_patterns(self, tf: str, candles: List[Dict[str, Any]]) -> None:
        if len(candles) < 24:
            return
        # Tingkatkan filter swing dari 2 bar menjadi 4 bar agar tidak tertipu oleh zigzag kecil
        highs, lows = get_swings(candles, 4, 4)
        price = _f(candles[-1].get('close'))
        tol = 1.0
        if len(highs) >= 2:
            h1, h2 = highs[-2], highs[-1]
            lvl1, lvl2 = _f(h1.get('high')), _f(h2.get('high'))
            if abs(lvl1 - lvl2) <= tol and price < min(_f(h1.get('low', lvl1)), _f(h2.get('low', lvl2))):
                level = round((lvl1 + lvl2) / 2, 3)
                msg = (
                    f"📐 MARKET ALERT: DOUBLE TOP TERBENTUK\n"
                    f"TF: {tf}\nTop area: {_fmt(level)}\nHarga sekarang: {_fmt(price)}\n"
                    f"Priority: MEDIUM\nSource: BOT DATA"
                )
                self._notify('DOUBLE_TOP', tf, 'bearish_watch', level, price, msg, 'MEDIUM')
        if len(lows) >= 2:
            l1, l2 = lows[-2], lows[-1]
            lvl1, lvl2 = _f(l1.get('low')), _f(l2.get('low'))
            if abs(lvl1 - lvl2) <= tol and price > max(_f(l1.get('high', lvl1)), _f(l2.get('high', lvl2))):
                level = round((lvl1 + lvl2) / 2, 3)
                msg = (
                    f"📐 MARKET ALERT: DOUBLE BOTTOM TERBENTUK\n"
                    f"TF: {tf}\nBottom area: {_fmt(level)}\nHarga sekarang: {_fmt(price)}\n"
                    f"Priority: MEDIUM\nSource: BOT DATA"
                )
                self._notify('DOUBLE_BOTTOM', tf, 'bullish_watch', level, price, msg, 'MEDIUM')
        if len(highs) >= 3:
            a, b, c = highs[-3], highs[-2], highs[-1]
            left, head, right = _f(a.get('high')), _f(b.get('high')), _f(c.get('high'))
            if head > left + 0.8 and head > right + 0.8 and abs(left - right) <= 2.0:
                level = round(head, 3)
                msg = (
                    f"📐 MARKET ALERT: HEAD AND SHOULDER TERBENTUK\n"
                    f"TF: {tf}\nLeft: {_fmt(left)} | Head: {_fmt(head)} | Right: {_fmt(right)}\n"
                    f"Harga sekarang: {_fmt(price)}\nPriority: MEDIUM\nSource: BOT DATA"
                )
                self._notify('HEAD_AND_SHOULDER', tf, 'bearish_watch', level, price, msg, 'MEDIUM')

    # 12 / 13. SSL / BSL touched
    def _alert_ssl_bsl_touched(self, price: float) -> None:
        try:
            rows = self.storage.fetchall(
                """
                SELECT * FROM liquidity_pools
                WHERE status IN ('VALID','ACTIVE','UNTOUCHED')
                ORDER BY id DESC LIMIT 40
                """
            )
        except Exception:
            rows = []
        for row in rows:
            level = _f(row.get('level'))
            if abs(price - level) <= self.touch_tolerance:
                ptype = str(row.get('pool_type') or '').lower()
                if 'sell' in ptype or 'ssl' in ptype or 'low' in ptype:
                    ev, title, direction = 'SSL_TOUCHED', 'SSL TERSENTUH', 'bullish_watch'
                else:
                    ev, title, direction = 'BSL_TOUCHED', 'BSL TERSENTUH', 'bearish_watch'
                msg = (
                    f"💧 MARKET ALERT: {title}\n"
                    f"TF: {row.get('timeframe') or 'NA'}\nLevel: {_fmt(level)}\n"
                    f"Harga sekarang: {_fmt(price)}\nPriority: HIGH\nSource: BOT DATA"
                )
                self._notify(ev, str(row.get('timeframe') or 'M15'), direction, level, price, msg, 'HIGH', raw=row)
                return
        # fallback from recent swings if DB pool does not exist yet
        candles = self.storage.get_recent_candles(self.symbol, 'M15', 60)
        if len(candles) < 12:
            return
        highs, lows = get_swings(candles, 2, 2)
        candidates = []
        candidates += [('BSL_TOUCHED', 'BSL TERSENTUH', 'bearish_watch', _f(h.get('high'))) for h in highs[-5:]]
        candidates += [('SSL_TOUCHED', 'SSL TERSENTUH', 'bullish_watch', _f(l.get('low'))) for l in lows[-5:]]
        if not candidates:
            return
        ev, title, direction, level = min(candidates, key=lambda x: abs(x[3] - price))
        if abs(level - price) <= self.touch_tolerance:
            msg = (
                f"💧 MARKET ALERT: {title}\n"
                f"TF: M15 swing\nLevel: {_fmt(level)}\nHarga sekarang: {_fmt(price)}\n"
                f"Priority: HIGH\nSource: BOT DATA"
            )
            self._notify(ev, 'M15', direction, level, price, msg, 'HIGH')

    # 14 / 15. BOS / CHoCH
    def _alert_bos_choch(self, tf: str, candles: List[Dict[str, Any]]) -> None:
        if len(candles) < 16:
            return
        highs, lows = get_swings(candles[:-1], 2, 2)
        last = candles[-1]
        close = _f(last.get('close'))
        bias = calculate_bias(candles[:-1]) if len(candles) >= 12 else 'neutral'
        if highs:
            level = _f(highs[-1].get('high'))
            if close > level + self.break_buffer:
                ev = 'CHoCH_BULLISH' if bias == 'bearish' else 'BOS_BULLISH'
                title = 'CHoCH BULLISH' if bias == 'bearish' else 'BOS BULLISH'
                msg = (
                    f"📊 MARKET ALERT: {title}\n"
                    f"TF: {tf}\nLevel: {_fmt(level)}\nClose: {_fmt(close)}\n"
                    f"Previous bias: {bias}\nPriority: HIGH\nSource: BOT DATA"
                )
                self._notify(ev, tf, 'bullish', level, close, msg, 'HIGH', raw=last)
        if lows:
            level = _f(lows[-1].get('low'))
            if close < level - self.break_buffer:
                ev = 'CHoCH_BEARISH' if bias == 'bullish' else 'BOS_BEARISH'
                title = 'CHoCH BEARISH' if bias == 'bullish' else 'BOS BEARISH'
                msg = (
                    f"📊 MARKET ALERT: {title}\n"
                    f"TF: {tf}\nLevel: {_fmt(level)}\nClose: {_fmt(close)}\n"
                    f"Previous bias: {bias}\nPriority: HIGH\nSource: BOT DATA"
                )
                self._notify(ev, tf, 'bearish', level, close, msg, 'HIGH', raw=last)

    # 16 / 17 / 18. Retest, rejection, displacement
    def _alert_retest_rejection_displacement(self, tf: str, candles: List[Dict[str, Any]]) -> None:
        if len(candles) < 15:
            return
        last = candles[-1]
        prev = candles[-13:-1]
        close, open_, high, low = [_f(last.get(k)) for k in ('close', 'open', 'high', 'low')]
        body = abs(close - open_)
        rng = max(high - low, 0.01)
        avg_rng = sum(max(_f(c.get('high')) - _f(c.get('low')), 0.01) for c in prev[-10:]) / min(10, len(prev))
        prev_high = max(_f(c.get('high')) for c in prev)
        prev_low = min(_f(c.get('low')) for c in prev)
        # displacement candle
        if body >= max(1.5, avg_rng * 1.5) and body / rng >= 0.65:
            direction = 'bullish' if close > open_ else 'bearish'
            msg = (
                f"⚡ MARKET ALERT: DISPLACEMENT CANDLE\n"
                f"TF: {tf}\nDirection: {direction.upper()}\n"
                f"Range: {_fmt(rng)} | Body: {_fmt(body)}\nClose: {_fmt(close)}\n"
                f"Priority: MEDIUM\nSource: BOT DATA"
            )
            self._notify('DISPLACEMENT_CANDLE', tf, direction, close, close, msg, 'MEDIUM', raw=last)
        # retest after recent break
        if abs(low - prev_high) <= self.retest_tolerance and close > prev_high:
            msg = (
                f"🔁 MARKET ALERT: RETEST SUPPORT BARU\n"
                f"TF: {tf}\nRetest level: {_fmt(prev_high)}\nClose: {_fmt(close)}\n"
                f"Priority: MEDIUM\nSource: BOT DATA"
            )
            self._notify('RETEST_AFTER_BREAK_BULLISH', tf, 'bullish_watch', prev_high, close, msg, 'MEDIUM', raw=last)
        if abs(high - prev_low) <= self.retest_tolerance and close < prev_low:
            msg = (
                f"🔁 MARKET ALERT: RETEST RESISTANCE BARU\n"
                f"TF: {tf}\nRetest level: {_fmt(prev_low)}\nClose: {_fmt(close)}\n"
                f"Priority: MEDIUM\nSource: BOT DATA"
            )
            self._notify('RETEST_AFTER_BREAK_BEARISH', tf, 'bearish_watch', prev_low, close, msg, 'MEDIUM', raw=last)
        # rejection near range edges
        upper = high - max(open_, close)
        lower = min(open_, close) - low
        if high >= prev_high - self.touch_tolerance and upper >= max(body * 1.5, 0.7) and close < prev_high:
            msg = (
                f"❌ MARKET ALERT: REJECTION DI RESISTANCE\n"
                f"TF: {tf}\nResistance: {_fmt(prev_high)}\nClose: {_fmt(close)}\n"
                f"Priority: MEDIUM\nSource: BOT DATA"
            )
            self._notify('REJECTION_RESISTANCE', tf, 'bearish_watch', prev_high, close, msg, 'MEDIUM', raw=last)
        if low <= prev_low + self.touch_tolerance and lower >= max(body * 1.5, 0.7) and close > prev_low:
            msg = (
                f"❌ MARKET ALERT: REJECTION DI SUPPORT\n"
                f"TF: {tf}\nSupport: {_fmt(prev_low)}\nClose: {_fmt(close)}\n"
                f"Priority: MEDIUM\nSource: BOT DATA"
            )
            self._notify('REJECTION_SUPPORT', tf, 'bullish_watch', prev_low, close, msg, 'MEDIUM', raw=last)

    # 19. Session high / low
    def _alert_session_high_low_touched(self, price: float) -> None:
        candles = self.storage.get_recent_candles(self.symbol, 'M5', 220)
        if len(candles) < 20:
            return
        now = datetime.now(timezone.utc)
        # WIB session ranges, converted by offset only for alert labelling.
        sessions = {
            'ASIA': (dtime(6, 0), dtime(14, 0)),
        }
        for name, (start, end) in sessions.items():
            selected = []
            for c in candles:
                try:
                    dt = datetime.fromisoformat(str(c.get('open_time')).replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    local_hour = (dt.hour + self.session_tz_offset) % 24
                    local_min = dt.minute
                    local_t = dtime(local_hour, local_min)
                    if start <= local_t <= end:
                        selected.append(c)
                except Exception:
                    pass
            if len(selected) < 4:
                continue
            hi = max(_f(c.get('high')) for c in selected)
            lo = min(_f(c.get('low')) for c in selected)
            if abs(price - hi) <= self.touch_tolerance:
                msg = (
                    f"🕒 MARKET ALERT: {name} HIGH TERSENTUH\n"
                    f"Level: {_fmt(hi)}\nHarga sekarang: {_fmt(price)}\n"
                    f"Priority: MEDIUM\nSource: BOT DATA"
                )
                self._notify(f'{name}_HIGH_TOUCHED', 'M5', 'bearish_watch', hi, price, msg, 'MEDIUM', dedupe_minutes=60)
            if abs(price - lo) <= self.touch_tolerance:
                msg = (
                    f"🕒 MARKET ALERT: {name} LOW TERSENTUH\n"
                    f"Level: {_fmt(lo)}\nHarga sekarang: {_fmt(price)}\n"
                    f"Priority: MEDIUM\nSource: BOT DATA"
                )
                self._notify(f'{name}_LOW_TOUCHED', 'M5', 'bullish_watch', lo, price, msg, 'MEDIUM', dedupe_minutes=60)

    # 20. Judas swing alert
    def _alert_judas_swing(self, tf: str, candles: List[Dict[str, Any]]) -> None:
        if len(candles) < 20:
            return
        last = candles[-1]
        close = _f(last.get('close'))
        high = _f(last.get('high'))
        low = _f(last.get('low'))
        prev = candles[-20:-1]
        prev_high = max(_f(c.get('high')) for c in prev)
        prev_low = min(_f(c.get('low')) for c in prev)
        try:
            raw = str(last.get('open_time')).replace('Z', '+00:00')
            dt = datetime.fromisoformat(raw)
            hour_local = (dt.hour + self.session_tz_offset) % 24
        except Exception:
            hour_local = datetime.now().hour
        in_killzone_open = hour_local in {14, 15, 19, 20}
        if not in_killzone_open:
            return
        if high > prev_high + self.sweep_buffer and close < prev_high:
            msg = (
                f"🎭 MARKET ALERT: JUDAS SWING HIGH\n"
                f"TF: {tf}\nSwept high: {_fmt(prev_high)}\nClose: {_fmt(close)}\n"
                f"Session hour WIB: {hour_local}:00\nPriority: HIGH\nSource: BOT DATA"
            )
            self._notify('JUDAS_SWING_HIGH', tf, 'bearish_watch', prev_high, close, msg, 'HIGH', raw=last)
        if low < prev_low - self.sweep_buffer and close > prev_low:
            msg = (
                f"🎭 MARKET ALERT: JUDAS SWING LOW\n"
                f"TF: {tf}\nSwept low: {_fmt(prev_low)}\nClose: {_fmt(close)}\n"
                f"Session hour WIB: {hour_local}:00\nPriority: HIGH\nSource: BOT DATA"
            )
            self._notify('JUDAS_SWING_LOW', tf, 'bullish_watch', prev_low, close, msg, 'HIGH', raw=last)

    # 21. Premium/discount + OTE area
    def _alert_premium_discount_ote(self, price: float) -> None:
        candles = self.storage.get_recent_candles(self.symbol, 'M15', 64)
        if len(candles) < 20:
            return
        hi = max(_f(c.get('high')) for c in candles[-32:])
        lo = min(_f(c.get('low')) for c in candles[-32:])
        swing = max(hi - lo, 0.01)
        eq = (hi + lo) / 2
        pos = (price - lo) / swing
        if pos >= 0.62:
            zone = 'PREMIUM / OTE SELL WATCH'
            direction = 'bearish_watch'
            ote_low = lo + swing * 0.62
            ote_high = lo + swing * 0.79
        elif pos <= 0.38:
            zone = 'DISCOUNT / OTE BUY WATCH'
            direction = 'bullish_watch'
            ote_low = hi - swing * 0.79
            ote_high = hi - swing * 0.62
        else:
            return
        if min(ote_low, ote_high) <= price <= max(ote_low, ote_high):
            msg = (
                f"⚖️ MARKET ALERT: {zone}\n"
                f"Range High: {_fmt(hi)} | Range Low: {_fmt(lo)} | EQ: {_fmt(eq)}\n"
                f"OTE Area: {_fmt(min(ote_low, ote_high))} - {_fmt(max(ote_low, ote_high))}\n"
                f"Harga sekarang: {_fmt(price)}\nPriority: LOW\nSource: BOT DATA"
            )
            self._notify('PREMIUM_DISCOUNT_OTE', 'M15', direction, round((ote_low + ote_high) / 2, 3), price, msg, 'LOW', dedupe_minutes=45)
