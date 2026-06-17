"""Adaptive trading brain for XAUUSD.

This file is intentionally small and editable by the AI Trainer.
Public API that must stay stable:
    BrainEngine(storage, symbol='XAU/USD', config=None)
    BrainEngine.analyze(current_price, m5_candles, m15_candles, h1_candles, data_health=None)
"""
from __future__ import annotations

from statistics import mean
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from .fvg_engine import detect_fvgs
from .market_structure import analyze_structure

from src.market_memory import MarketMemory


def _no_trade(reason: str, confidence: float = 0, pattern_key: str = "") -> Dict[str, Any]:
    return {
        'symbol': 'XAU/USD',
        'direction': 'NO_TRADE',
        'entry_low': None,
        'entry_high': None,
        'sl': None,
        'tp1': None,
        'tp2': None,
        'tp3': None,
        'invalid_level': None,
        'confidence': confidence,
        'reason': reason,
        'status': 'NO_TRADE',
        'pattern_key': pattern_key,
        'source': 'ADAPTIVE_BRAIN'
    }


def _cval(candle: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(candle.get(key, default) or default)
    except Exception:
        return default

def _is_pivot_high(candles: List[Dict[str, Any]], index: int, left: int = 3, right: int = 1) -> bool:
    if index - left < 0 or index + right >= len(candles):
        return False
    center_high = _cval(candles[index], 'high')
    for i in range(index - left, index + right + 1):
        if i == index: continue
        if _cval(candles[i], 'high') >= center_high:
            return False
    return True

def _is_pivot_low(candles: List[Dict[str, Any]], index: int, left: int = 3, right: int = 1) -> bool:
    if index - left < 0 or index + right >= len(candles):
        return False
    center_low = _cval(candles[index], 'low')
    for i in range(index - left, index + right + 1):
        if i == index: continue
        if _cval(candles[i], 'low') <= center_low:
            return False
    return True


class BrainEngine:
    def __init__(self, storage, symbol: str = 'XAU/USD', config: Optional[Dict[str, Any]] = None):
        self.storage = storage
        self.symbol = symbol
        self.config = config or {}
        self.memory = MarketMemory(storage)
        adaptive_cfg = (self.config or {}).get('adaptive_brain', {})
        self.min_confidence = float(adaptive_cfg.get('min_confidence', 10))
        self.max_recent_events = int(adaptive_cfg.get('max_recent_events', 30))
        self.sl_atr_mult = float(adaptive_cfg.get('sl_atr_mult', 1.15))
        self.tp1_rr = float(adaptive_cfg.get('tp1_rr', 1.0))
        self.tp2_rr = float(adaptive_cfg.get('tp2_rr', 2.0))
        self.tp3_rr = 0.0
        self.pips_per_price_point = float(adaptive_cfg.get('pips_per_price_point', 10))
        self.max_sl_pips = float(adaptive_cfg.get('max_sl_pips', 100))
        self.max_sl_price_distance = self.max_sl_pips / max(self.pips_per_price_point, 0.01)
        default_blocked_methods = {
            'AI_METHOD_2025_002_FVG_BREAKER_SELL_SANDBOX_RELAXED',
        }
        configured_blocked = adaptive_cfg.get('blocked_methods')
        self.blocked_methods = set(configured_blocked or default_blocked_methods)
        self.signal_timeframe = str(adaptive_cfg.get('signal_timeframe') or 'M5').upper()
        self.signal_class = 'M1_AGGRESSIVE' if self.signal_timeframe == 'M1' else 'M5_RECOMMENDED'
        self.lookbacks = list(adaptive_cfg.get('v6_lookbacks') or [6, 8, 12])
        # Main-method whitelist: only these methods are allowed to produce bot signals.
        # Empty/missing list keeps old behavior.
        self.main_methods = set(adaptive_cfg.get('main_methods') or [])

    def _main_method_allowed(self, pattern_key: str) -> bool:
        if not self.main_methods:
            return True
        return bool(pattern_key and pattern_key in self.main_methods)

    def _method_blocked(self, pattern_key: str) -> bool:
        return bool(pattern_key and pattern_key in self.blocked_methods)

    def analyze(self, current_price: float, m5_candles: List[Dict[str, Any]],
                m15_candles: Optional[List[Dict[str, Any]]] = None,
                h1_candles: Optional[List[Dict[str, Any]]] = None,
                data_health: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if data_health and not data_health.get('is_healthy', True):
            sig = _no_trade('Data belum sehat / masih warming up')
            self.memory.save_decision(sig)
            return sig

        if not current_price or len(m5_candles or []) < 8:
            sig = _no_trade('Data M5 belum cukup untuk adaptive brain')
            self.memory.save_decision(sig)
            return sig

        active = self.memory.active_signal(self.signal_timeframe)
        if active:
            sig = _no_trade(f"Ada signal {self.signal_timeframe} ACTIVE #{active.get('id')} {active.get('direction')}. Brain menahan signal baru di TF yang sama.")
            sig['signal_timeframe'] = self.signal_timeframe
            sig['signal_class'] = self.signal_class
            self.memory.save_decision(sig)
            return sig

        price = float(current_price)
        context = self._read_market_context(price, m5_candles, m15_candles or [], h1_candles or [])
        self._record_context_events(context, price)

        direction, reason, pattern_key, base_conf = self._decide(context)
        if self._method_blocked(pattern_key):
            sig = _no_trade(f'Method {pattern_key} diblokir hasil backtest karena terlalu banyak SL.', 0, pattern_key)
            sig['current_price'] = price
            sig['brain_context'] = context
            self.memory.save_decision(sig)
            return sig
        if direction == 'NO_TRADE':
            sig = _no_trade(reason, base_conf, pattern_key)
            sig['current_price'] = price
            sig['brain_context'] = context
            self.memory.save_decision(sig)
            return sig

        pattern = self.memory.get_pattern(pattern_key)
        if self.memory.is_pattern_in_cooldown(pattern_key):
            sig = _no_trade(f'Pattern {pattern_key} sedang cooldown setelah hasil buruk.', 0, pattern_key)
            sig['current_price'] = price
            sig['brain_context'] = context
            self.memory.save_decision(sig)
            return sig

        learned_score = float(pattern.get('score') or 0)
        confidence = max(1, min(95, base_conf + learned_score))
        
        wins = int(pattern.get('wins') or 0)
        losses = int(pattern.get('losses') or 0)
        total_trades = wins + losses
        
        # Self-Healing Auto-Block: Block methods with terrible historical win rate
        # Threshold lowered to 40% because RR is 1:1.5 (Break-even is 40%)
        # Only block if we have a solid sample size (e.g., >= 10 trades)
        if total_trades >= 10:
            win_rate = (wins / total_trades) * 100
            # DIMATIKAN SEMENTARA ATAS PERMINTAAN BOS UNTUK ULTRA BACKTEST 2025
            # if win_rate < 40.0:
            #     sig = _no_trade(f'Auto-Block: {pattern_key} dihentikan sementara (WR {win_rate:.1f}% dari {total_trades} trade). Bot butuh reset memori.', 0, pattern_key)
            #     sig['current_price'] = price
            #     sig['brain_context'] = context
            #     self.memory.save_decision(sig)
            #     return sig
        
        if total_trades < 10:
            confidence = max(confidence, self.min_confidence)
            
        if confidence < self.min_confidence:
            sig = _no_trade(f'Confidence adaptive masih rendah: {confidence:.0f}%', confidence, pattern_key)
            sig['current_price'] = price
            sig['brain_context'] = context
            self.memory.save_decision(sig)
            return sig

        signal = self._build_signal(direction, price, context, confidence, reason, pattern_key, pattern)
        if not signal:
            sig = _no_trade(f'Signal batal: SL terlalu lebar/Risk tidak masuk kriteria', confidence, pattern_key)
            sig['current_price'] = price
            sig['brain_context'] = context
            self.memory.save_decision(sig)
            return sig

        self.memory.save_decision(signal)
        return signal

    def _read_market_context(self, price: float, m5: List[Dict[str, Any]], m15: List[Dict[str, Any]], h1: List[Dict[str, Any]]) -> Dict[str, Any]:
        last = m5[-1]
        lookback = m5[-8:-1] if len(m5) >= 8 else m5[:-1]
        lookback_20 = m5[-21:-1] if len(m5) >= 21 else m5[:-1]
        highs = [_cval(c, 'high') for c in lookback]
        lows = [_cval(c, 'low') for c in lookback]
        highs_20 = [_cval(c, 'high') for c in lookback_20]
        lows_20 = [_cval(c, 'low') for c in lookback_20]
        prev_high = max(highs) if highs else _cval(last, 'high')
        prev_low = min(lows) if lows else _cval(last, 'low')
        prev_high_20 = max(highs_20) if highs_20 else prev_high
        prev_low_20 = min(lows_20) if lows_20 else prev_low
        close = _cval(last, 'close', price)
        open_ = _cval(last, 'open', close)
        high = _cval(last, 'high', close)
        low = _cval(last, 'low', close)
        atr = self._atr(m5, 14)
        body = abs(close - open_)
        rng = max(high - low, 0.01)
        body_ratio = body / rng
        momentum = 'bullish' if close > open_ else 'bearish' if close < open_ else 'neutral'
        break_bull = close > prev_high
        break_bear = close < prev_low
        sentuh_high = high >= prev_high
        sentuh_low = low <= prev_low
        choppy = self._is_choppy(m5)
        recent_events = self.memory.recent_events(
            self.symbol,
            self.max_recent_events,
            current_price=price,
            max_age_minutes=180,
            max_distance_points=25.0,
        )
        fvgs = self.memory.storage.get_active_fvgs(self.symbol, 'M5')
        m15_fvgs = self.memory.storage.get_active_fvgs(self.symbol, 'M15')
        if m15_fvgs:
            fvgs.extend(m15_fvgs)
        try:
            obs = self.storage.fetchall("SELECT * FROM active_order_blocks WHERE status IN ('VALID','ACTIVE') ORDER BY id DESC LIMIT 20")
        except Exception:
            obs = []
        try:
            breakers = self.storage.fetchall("SELECT * FROM active_breakers WHERE status IN ('VALID','ACTIVE') ORDER BY id DESC LIMIT 20")
        except Exception:
            breakers = []
        try:
            ote_zones = self.storage.fetchall("SELECT * FROM active_ote_zones WHERE status IN ('VALID','ACTIVE') ORDER BY id DESC LIMIT 10")
        except Exception:
            ote_zones = []
        structure = analyze_structure(m5, m15, h1)
        try:
            h4_candles = self.storage.get_recent_candles(self.symbol, 'H4', 80)
        except Exception:
            h4_candles = []
        try:
            d1_candles = self.storage.get_recent_candles(self.symbol, 'D1', 80)
        except Exception:
            d1_candles = []
        if not d1_candles:
            d1_candles = self._aggregate_daily_from_h1(h1)
        h1_break = self._h1_break_context(h1, last)

        def _ema(data, period):
            if not data: return 0
            k = 2 / (period + 1)
            ema = data[0]
            for price in data[1:]:
                ema = (price * k) + (ema * (1 - k))
            return ema

        htf_bias = 'MIXED'
        if len(h1) >= 50:
            h1_closes = [_cval(c, 'close') for c in h1]
            ema20 = _ema(h1_closes, 20)
            ema50 = _ema(h1_closes, 50)
            last_h1_close = h1_closes[-1]
            if last_h1_close > ema20 and ema20 > ema50:
                htf_bias = 'BULLISH'
            elif last_h1_close < ema20 and ema20 < ema50:
                htf_bias = 'BEARISH'

        active_resistance = None
        active_support = None
        if len(m15) >= 5:
            # Find the most recent pivot high/low using pivothigh(3, 1) logic
            for i in range(len(m15)-2, 3, -1):
                if active_resistance is None and _is_pivot_high(m15, i, 3, 1):
                    active_resistance = _cval(m15[i], 'high')
                if active_support is None and _is_pivot_low(m15, i, 3, 1):
                    active_support = _cval(m15[i], 'low')
                if active_resistance is not None and active_support is not None:
                    break

        return {
            'price': price,
            'htf_bias': htf_bias,
            'active_resistance': active_resistance,
            'active_support': active_support,
            'prev_high': prev_high,
            'prev_low': prev_low,
            'prev_high_20': prev_high_20,
            'prev_low_20': prev_low_20,
            'last_open': open_,
            'last_high': high,
            'last_low': low,
            'last_close': close,
            'atr': atr,
            'body_ratio': body_ratio,
            'momentum': momentum,
            'break_bull': break_bull,
            'break_bear': break_bear,
            'sentuh_high': sentuh_high,
            'sentuh_low': sentuh_low,
            'choppy': choppy,
            'recent_events': recent_events[:12],
            'm15_bias': self._bias(m15),
            'h1_bias': self._bias(h1),
            'h1_candles': h1,
            'h4_candles': h4_candles,
            'd1_candles': d1_candles,
            'h1_break': h1_break,
            'fvgs': fvgs,
            'obs': obs,
            'breakers': breakers,
            'ote_zones': ote_zones,
            'structure': structure,
            'intraday_context': self._intraday_context(price, m15, h1),
            'candles': m5,
            'last_time': last.get('open_time') or last.get('time') or last.get('timestamp') or last.get('dt') or last.get('close_time'),
        }

    def _intraday_context(self, price: float, m15: List[Dict[str, Any]], h1: List[Dict[str, Any]]) -> Dict[str, Any]:
        candles = m15[-32:] if len(m15 or []) >= 8 else (h1[-16:] if h1 else [])
        if not candles or len(candles) < 5:
            return {
                'bias': 'unknown',
                'range_high': None,
                'range_low': None,
                'equilibrium': None,
                'position': 'unknown',
                'supply': None,
                'demand': None,
            }
        highs = [_cval(c, 'high') for c in candles]
        lows = [_cval(c, 'low') for c in candles]
        closes = [_cval(c, 'close') for c in candles]
        range_high = max(highs)
        range_low = min(lows)
        equilibrium = (range_high + range_low) / 2
        first = closes[0]
        last = closes[-1]
        swing = max(range_high - range_low, 0.01)
        if last > first and last > equilibrium:
            bias = 'bullish'
        elif last < first and last < equilibrium:
            bias = 'bearish'
        else:
            bias = 'sideways'
        if price >= equilibrium + swing * 0.15:
            position = 'premium'
        elif price <= equilibrium - swing * 0.15:
            position = 'discount'
        else:
            position = 'equilibrium'
        supply_candle = max(candles, key=lambda c: _cval(c, 'high'))
        demand_candle = min(candles, key=lambda c: _cval(c, 'low'))
        def zone_from(c):
            o = _cval(c, 'open')
            cl = _cval(c, 'close')
            hi = _cval(c, 'high')
            lo = _cval(c, 'low')
            body_low = min(o, cl)
            body_high = max(o, cl)
            return {
                'low': round(max(lo, body_low - 0.20), 3),
                'high': round(min(hi, body_high + 0.20), 3),
                'candle_time': c.get('open_time') or c.get('time') or c.get('timestamp'),
            }
        return {
            'bias': bias,
            'range_high': round(range_high, 3),
            'range_low': round(range_low, 3),
            'equilibrium': round(equilibrium, 3),
            'position': position,
            'supply': zone_from(supply_candle),
            'demand': zone_from(demand_candle),
        }

    def _record_context_events(self, ctx: Dict[str, Any], price: float) -> None:
        tf = self.signal_timeframe
        if ctx.get('sentuh_high'):
            self.memory.record_event(self.symbol, tf, 'SENTUH_HIGH', 'bearish_watch', ctx.get('prev_high'), price, 1.0, raw=ctx)
        if ctx.get('sentuh_low'):
            self.memory.record_event(self.symbol, tf, 'SENTUH_LOW', 'bullish_watch', ctx.get('prev_low'), price, 1.0, raw=ctx)
        if ctx.get('break_bull'):
            self.memory.record_event(self.symbol, tf, 'BREAK_BULLISH', 'bullish', ctx.get('prev_high'), price, 1.4, raw=ctx)
        if ctx.get('break_bear'):
            self.memory.record_event(self.symbol, tf, 'BREAK_BEARISH', 'bearish', ctx.get('prev_low'), price, 1.4, raw=ctx)
        if ctx.get('choppy'):
            self.memory.record_event(self.symbol, tf, 'CHOPPY', 'neutral', None, price, 0.5, raw=ctx, dedupe_window_minutes=30)

    def _evaluate_dynamic_rules(self, ctx: Dict[str, Any]) -> __import__('typing').Optional[Tuple[str, str, str, float]]:
        conn = self.memory.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM dynamic_rules")
            rules = cur.fetchall()
        except Exception:
            rules = []
        finally:
            conn.close()
            
        for r in rules:
            try:
                rj = __import__('json').loads(r['rule_json'])
                rule_conds = rj.get('rules', {})
                match = True
                
                if 'momentum_bias' in rule_conds:
                    if ctx.get('momentum') != rule_conds['momentum_bias']: match = False
                if 'max_body_ratio' in rule_conds:
                    if float(ctx.get('body_ratio') or 0) > float(rule_conds['max_body_ratio']): match = False
                if 'min_body_ratio' in rule_conds:
                    if float(ctx.get('body_ratio') or 0) < float(rule_conds['min_body_ratio']): match = False
                if rule_conds.get('requires_sentuh_high') and not ctx.get('sentuh_high'): match = False
                if rule_conds.get('requires_sentuh_low') and not ctx.get('sentuh_low'): match = False
                if rule_conds.get('requires_break_bull') and not ctx.get('break_bull'): match = False
                if rule_conds.get('requires_break_bear') and not ctx.get('break_bear'): match = False
                
                if match:
                    pattern_key = r['pattern_key']
                    if self._method_blocked(pattern_key):
                        continue
                    return (rj.get('direction', 'BUY').upper(), f"AI Dynamic: {rj.get('description', '')}", pattern_key, 55.0)
            except Exception:
                pass
        return None

    def _relaxed_sandbox_quality_ok(self, method: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
        name = str(method.get('name') or '')
        if 'SANDBOX_RELAXED' not in name:
            return True
        direction = str(method.get('direction') or '').upper()
        m15_bias = ctx.get('m15_bias')
        h1_bias = ctx.get('h1_bias')
        body_ratio = float(ctx.get('body_ratio') or 0)
        atr = float(ctx.get('atr') or 0)
        if body_ratio < 0.20 or atr < 0.5 or atr > 6.0:
            return False
        if direction == 'BUY' and (m15_bias == 'bearish' or h1_bias == 'bearish'):
            return False
        if direction == 'SELL' and (m15_bias == 'bullish' or h1_bias == 'bullish'):
            return False
        return True

    def _strict_m15_sweep_reclaim(self, ctx: Dict[str, Any]) -> __import__('typing').Optional[Tuple[str, str, str, float]]:
        close = float(ctx.get('last_close') or 0)
        open_ = float(ctx.get('last_open') or 0)
        high = float(ctx.get('last_high') or 0)
        low = float(ctx.get('last_low') or 0)
        prev_high_20 = float(ctx.get('prev_high_20') or ctx.get('prev_high') or 0)
        prev_low_20 = float(ctx.get('prev_low_20') or ctx.get('prev_low') or 0)
        atr = float(ctx.get('atr') or 0)
        body_ratio = float(ctx.get('body_ratio') or 0)
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        body_size = max(body_top - body_bottom, 0.01)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        m15_bias = ctx.get('m15_bias')

        if atr < 0.5 or atr > 6.0 or body_ratio < 0.20:
            return None
        if low <= prev_low_20 and close > prev_low_20 and close > open_ and lower_wick >= body_size * 0.5 and m15_bias == 'bullish':
            return ('BUY', 'STRICT M15 SWEEP: 20-candle low sweep + bullish reclaim', 'METHOD_STRICT_M15_SWEEP_RECLAIM_BUY', 92.0)
        if high >= prev_high_20 and close < prev_high_20 and close < open_ and upper_wick >= body_size * 0.5 and m15_bias == 'bearish':
            return ('SELL', 'STRICT M15 SWEEP: 20-candle high sweep + bearish reclaim', 'METHOD_STRICT_M15_SWEEP_RECLAIM_SELL', 92.0)
        return None

    def _ctx_utc_hour(self, ctx: Dict[str, Any]) -> Optional[int]:
        raw = ctx.get('last_time')
        if raw is None:
            return None
        try:
            if isinstance(raw, (int, float)):
                return datetime.fromtimestamp(float(raw), timezone.utc).hour
            text = str(raw).strip()
            if text.isdigit():
                return datetime.fromtimestamp(float(text), timezone.utc).hour
            text = text.replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(text)
            except Exception:
                dt = None
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y.%m.%d %H:%M'):
                    try:
                        dt = datetime.strptime(text[:19], fmt)
                        break
                    except Exception:
                        pass
            if dt is None:
                return None
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc)
            return dt.hour
        except Exception:
            return None

    def _ctx_utc_weekday(self, ctx: Dict[str, Any]) -> Optional[int]:
        raw = ctx.get('last_time')
        if raw is None:
            return None
        try:
            if isinstance(raw, (int, float)):
                return datetime.fromtimestamp(float(raw), timezone.utc).weekday()
            text = str(raw).strip()
            if text.isdigit():
                return datetime.fromtimestamp(float(text), timezone.utc).weekday()
            text = text.replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(text)
            except Exception:
                dt = None
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y.%m.%d %H:%M'):
                    try:
                        dt = datetime.strptime(text[:19], fmt)
                        break
                    except Exception:
                        pass
            if dt is None:
                return None
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc)
            return dt.weekday()
        except Exception:
            return None

    def _rr2_group_sell(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        """Backtested RR 1:2 SELL group.

        This method is intentionally small and locked by config. It does not
        replace existing methods; it is only allowed when whitelisted in
        adaptive_brain.main_methods.
        """
        if not self._main_method_allowed('RR2_GROUP_SELL'):
            return None
        hour = self._ctx_utc_hour(ctx)
        weekday = self._ctx_utc_weekday(ctx)
        atr = float(ctx.get('atr') or 0)
        body_ratio = float(ctx.get('body_ratio') or 0)
        close = float(ctx.get('last_close') or 0)
        open_ = float(ctx.get('last_open') or close)
        high = float(ctx.get('last_high') or close)
        low = float(ctx.get('last_low') or close)
        prev_low = float(ctx.get('prev_low') or low)

        if weekday != 2 or hour != 22:
            return None
        if atr < 0.50 or atr > 6.00 or body_ratio < 0.25:
            return None
        if ctx.get('h1_bias') != 'bearish' or ctx.get('h4_bias') != 'bearish':
            return None
        if close < open_ and (close <= prev_low or (high - close) >= max(abs(open_ - close), 0.01) * 0.50):
            return ('SELL', 'RR2 GROUP SELL: locked Wednesday 22 UTC bearish continuation/rejection', 'RR2_GROUP_SELL', 92.0)
        return None

    def _high_wr_safe_hour_ok(self, ctx: Dict[str, Any]) -> bool:
        adaptive_cfg = (self.config or {}).get('adaptive_brain', {})
        hours = adaptive_cfg.get('high_wr_safe_hours_utc', list(range(8, 16)))
        if hours is None or hours == []:
            return True
        hour = self._ctx_utc_hour(ctx)
        if hour is None:
            return True
        try:
            return int(hour) in {int(h) for h in hours}
        except Exception:
            return True

    def _high_wr_common_filter(self, ctx: Dict[str, Any], direction: str) -> bool:
        atr = float(ctx.get('atr') or 0)
        body_ratio = float(ctx.get('body_ratio') or 0)
        m15_bias = ctx.get('m15_bias')
        h1_bias = ctx.get('h1_bias')
        adaptive_cfg = (self.config or {}).get('adaptive_brain', {})
        tf_cfg = adaptive_cfg.get('v6_timeframe_filters', {}) or {}
        cur_tf_cfg = tf_cfg.get(self.signal_timeframe, {}) or {}
        min_atr = float(cur_tf_cfg.get('atr_min', 0.20 if self.signal_timeframe == 'M1' else 0.65))
        max_atr = float(cur_tf_cfg.get('atr_max', 6.0))
        min_body = float(cur_tf_cfg.get('body_ratio_min', 0.35))
        if not self._high_wr_safe_hour_ok(ctx):
            return False
        if atr < min_atr or atr > max_atr or body_ratio < min_body:
            return False

        # Approved high-WR sweep repairs use bias as context, not as a hard blocker.
        # The old hard M15+H1 bias filter caused valid sweep entries to disappear.
        if bool(adaptive_cfg.get('relaxed_sweep_reclaim', True)):
            return True

        if direction == 'BUY':
            return True
        else:
            return True
        return False

    def _high_wr_sweep_variant(self, ctx: Dict[str, Any], lookback: int, max_span: float, method_base: str) -> Optional[Tuple[str, str, str, float]]:
        candles = ctx.get('candles') or []
        if len(candles) <= lookback:
            return None
        close = float(ctx.get('last_close') or 0)
        open_ = float(ctx.get('last_open') or 0)
        high = float(ctx.get('last_high') or 0)
        low = float(ctx.get('last_low') or 0)
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        body_size = max(body_top - body_bottom, 0.01)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        previous = candles[-lookback-1:-1]
        if len(previous) < lookback:
            return None
        prev_high = max(_cval(c, 'high') for c in previous)
        prev_low = min(_cval(c, 'low') for c in previous)
        prev_span = max(prev_high - prev_low, 0.01)
        if prev_span > max_span:
            return None

        buy_ok = (
            self._high_wr_common_filter(ctx, 'BUY')
            and low <= prev_low
            and close > prev_low
            and close > open_
            and lower_wick >= body_size * 0.35
            and (prev_low - low) >= 0.15
            and (close - prev_low) >= 0.25
        )
        if buy_ok:
            return ('BUY', f'HIGH WR MULTI SWEEP {lookback}: low sweep + reclaim + same strict filter', f'{method_base}_BUY', 95.0)

        sell_ok = (
            self._high_wr_common_filter(ctx, 'SELL')
            and high >= prev_high
            and close < prev_high
            and close < open_
            and upper_wick >= body_size * 0.35
            and (high - prev_high) >= 0.15
            and (prev_high - close) >= 0.25
        )
        if sell_ok:
            return ('SELL', f'HIGH WR MULTI SWEEP {lookback}: high sweep + reclaim + same strict filter', f'{method_base}_SELL', 95.0)
        return None

    def _high_wr_break_variant(self, ctx: Dict[str, Any], lookback: int, max_span: float, method_base: str) -> Optional[Tuple[str, str, str, float]]:
        candles = ctx.get('candles') or []
        if len(candles) <= lookback:
            return None
        close = float(ctx.get('last_close') or 0)
        open_ = float(ctx.get('last_open') or 0)
        high = float(ctx.get('last_high') or 0)
        low = float(ctx.get('last_low') or 0)
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        body_size = max(body_top - body_bottom, 0.01)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        body = abs(close - open_)
        previous = candles[-lookback-1:-1]
        if len(previous) < lookback:
            return None
        prev_high = max(_cval(c, 'high') for c in previous)
        prev_low = min(_cval(c, 'low') for c in previous)
        prev_span = max(prev_high - prev_low, 0.01)
        if prev_span > max_span:
            return None

        buy_ok = (
            self._high_wr_common_filter(ctx, 'BUY')
            and close > prev_high + 0.45
            and close > open_
            and upper_wick <= body_size * 1.0
            and body >= 0.90
        )
        if buy_ok:
            return ('BUY', f'HIGH WR MULTI BREAK {lookback}: bullish continuation break + same strict filter', f'{method_base}_BUY', 94.0)

        sell_ok = (
            self._high_wr_common_filter(ctx, 'SELL')
            and close < prev_low - 0.45
            and close < open_
            and lower_wick <= body_size * 1.0
            and body >= 0.90
        )
        if sell_ok:
            return ('SELL', f'HIGH WR MULTI BREAK {lookback}: bearish continuation break + same strict filter', f'{method_base}_SELL', 94.0)
        return None

    def _parse_candle_dt(self, raw: Any) -> Optional[datetime]:
        if raw is None:
            return None
        try:
            if isinstance(raw, (int, float)):
                return datetime.fromtimestamp(float(raw), timezone.utc)
            text = str(raw).strip().replace('Z', '+00:00')
            if text.isdigit():
                return datetime.fromtimestamp(float(text), timezone.utc)
            try:
                dt = datetime.fromisoformat(text)
            except Exception:
                dt = None
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y.%m.%d %H:%M'):
                    try:
                        dt = datetime.strptime(text[:19], fmt)
                        break
                    except Exception:
                        pass
            if dt is None:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _candle_time(self, candle: Dict[str, Any]) -> Optional[datetime]:
        return self._parse_candle_dt(
            candle.get('open_time') or candle.get('time') or candle.get('timestamp') or candle.get('dt') or candle.get('close_time')
        )

    def _aggregate_daily_from_h1(self, h1: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for c in h1 or []:
            dt = self._candle_time(c)
            if not dt:
                continue
            key = dt.date().isoformat()
            buckets.setdefault(key, []).append(c)
        days: List[Dict[str, Any]] = []
        for day in sorted(buckets):
            rows = buckets[day]
            if not rows:
                continue
            rows.sort(key=lambda x: self._candle_time(x) or datetime.min.replace(tzinfo=timezone.utc))
            days.append({
                'symbol': self.symbol,
                'timeframe': 'D1',
                'open_time': day + 'T00:00:00+00:00',
                'open': _cval(rows[0], 'open'),
                'high': max(_cval(x, 'high') for x in rows),
                'low': min(_cval(x, 'low') for x in rows),
                'close': _cval(rows[-1], 'close'),
                'is_closed': 1,
            })
        return days

    def _h1_break_context(self, h1: List[Dict[str, Any]], trigger_candle: Dict[str, Any]) -> Dict[str, Any]:
        if not h1 or len(h1) < 2:
            return {'side': None, 'level': None, 'minutes_after_close': None, 'break_distance': None}
        prev = h1[-2]
        last = h1[-1]
        prev_high = _cval(prev, 'high')
        prev_low = _cval(prev, 'low')
        last_close = _cval(last, 'close')
        last_open = _cval(last, 'open')
        side = None
        level = None
        dist = None
        if last_close > prev_high and last_close > last_open:
            side = 'BUY'
            level = prev_high
            dist = last_close - prev_high
        elif last_close < prev_low and last_close < last_open:
            side = 'SELL'
            level = prev_low
            dist = prev_low - last_close
        last_dt = self._candle_time(last)
        trigger_dt = self._candle_time(trigger_candle)
        minutes_after_close = None
        if last_dt and trigger_dt:
            h1_close = last_dt + timedelta(hours=1)
            minutes_after_close = (trigger_dt - h1_close).total_seconds() / 60.0
        return {
            'side': side,
            'level': round(level, 3) if level is not None else None,
            'minutes_after_close': minutes_after_close,
            'break_distance': round(float(dist), 3) if dist is not None else None,
            'last_h1_open': last.get('open_time'),
        }

    def _user_method_cfg(self) -> Dict[str, Any]:
        return ((self.config or {}).get('adaptive_brain', {}).get('user_methods', {}) or {})

    def _buffer_ok(self, distance: float, min_buffer: float, max_buffer: float) -> bool:
        try:
            return float(min_buffer) <= float(distance) <= float(max_buffer)
        except Exception:
            return False

    def _crt_sweep_method(self, ctx: Dict[str, Any], tf: str) -> Optional[Tuple[str, str, str, float]]:
        cfg = self._user_method_cfg().get(f'crt_{tf.lower()}', {}) or {}
        if not bool(cfg.get('enabled', True)):
            return None
        candles = ctx.get(f'{tf.lower()}_candles') or []
        if len(candles) < 1:
            return None
        ref = candles[-1]
        ref_high = _cval(ref, 'high')
        ref_low = _cval(ref, 'low')
        close = float(ctx.get('last_close') or 0)
        open_ = float(ctx.get('last_open') or close)
        high = float(ctx.get('last_high') or close)
        low = float(ctx.get('last_low') or close)
        min_buffer = float(cfg.get('buffer_min_points', 1.0))
        max_buffer = max(float(cfg.get('buffer_max_points', 2.0)), 4.0)
        m15_bias = ctx.get('m15_bias')
        buy_sweep = ref_low - low
        sell_sweep = high - ref_high
        
        body = abs(close - open_)
        lower_wick = min(open_, close) - low
        upper_wick = high - max(open_, close)
        
        if self._buffer_ok(buy_sweep, min_buffer, max_buffer) and close > ref_low and close > open_:
            if m15_bias != 'bearish' and lower_wick >= body * 1.5:
                ctx[f'crt_{tf.lower()}_level'] = ref_low
                return ('BUY', f'CRT {tf}: sweep low {ref_low:.2f} buffer {buy_sweep:.2f} point lalu reclaim/reversal', f'METHOD_CRT_{tf}_SWEEP_BUY', 96.0)
                
        if self._buffer_ok(sell_sweep, min_buffer, max_buffer) and close < ref_high and close < open_:
            if m15_bias != 'bullish' and upper_wick >= body * 1.5:
                ctx[f'crt_{tf.lower()}_level'] = ref_high
                return ('SELL', f'CRT {tf}: sweep high {ref_high:.2f} buffer {sell_sweep:.2f} point lalu reclaim/reversal', f'METHOD_CRT_{tf}_SWEEP_SELL', 96.0)
                
        return None

    def _h1_break_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        cfg = self._user_method_cfg().get('h1_break', {}) or {}
        if not bool(cfg.get('enabled', True)):
            return None
        info = ctx.get('h1_break') or {}
        side = info.get('side')
        level = info.get('level')
        if not side or level is None:
            return None
        minutes = info.get('minutes_after_close')
        window = float(cfg.get('next_candle_window_minutes', 15.0))
        if minutes is not None and not (0 <= float(minutes) <= window):
            return None
        min_break = float(cfg.get('min_break_points', 0.45))
        if float(info.get('break_distance') or 0) < min_break:
            return None
        m15_bias = ctx.get('m15_bias')
        ctx['h1_break_level'] = float(level)
        if side == 'BUY':
            return ('BUY', f'H1 BREAK: break high {float(level):.2f}, next candle pending buffer 5-10 point', 'METHOD_H1_BREAK_BUY', 90.0)
        if side == 'SELL':
            return ('SELL', f'H1 BREAK: break low {float(level):.2f}, next candle pending buffer 5-10 point', 'METHOD_H1_BREAK_SELL', 90.0)
        return None

    def _m15_double_top_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        events = ctx.get('recent_events', [])
        for ev in events:
            evt_type = str(ev.get('event_type', '')).upper()
            msg = str(ev.get('message', '')).upper()
            if 'DOUBLE TOP' in evt_type or 'DOUBLE TOP' in msg:
                if 'M15' in msg or ev.get('timeframe') == 'M15':
                    return ('SELL', 'Reaksi Pola Double Top M15', 'METHOD_M15_DOUBLE_TOP', 85.0)
        return None

    def _fvg_rejection_aggro_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        fvgs = ctx.get('fvgs', [])
        high = ctx.get('last_high', 0.0)
        low = ctx.get('last_low', 0.0)
        close = ctx.get('last_close', 0.0)
        open_ = ctx.get('last_open', 0.0)
        
        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low
        
        for fvg in fvgs:
            if fvg['direction'] == 'Bearish' and high >= fvg['low'] and close < fvg['low'] and close < open_:
                if upper_wick > body * 1.5:
                    return ('SELL', 'Aggressive FVG Rejection (Pinbar Bearish di FVG)', 'METHOD_FVG_REJECTION_SELL', 86.0)
            if fvg['direction'] == 'Bullish' and low <= fvg['high'] and close > fvg['high'] and close > open_:
                if lower_wick > body * 1.5:
                    return ('BUY', 'Aggressive FVG Rejection (Pinbar Bullish di FVG)', 'METHOD_FVG_REJECTION_BUY', 86.0)
        return None

    def _ifvg_breakout_aggro_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        close = ctx.get('last_close', 0.0)
        open_ = ctx.get('last_open', 0.0)
        low = ctx.get('last_low', 0.0)
        high = ctx.get('last_high', 0.0)
        
        try:
            # Fetch recently invalidated FVGs (IFVGs)
            ifvgs = self.storage.fetchall(f"SELECT * FROM fvgs WHERE symbol = '{self.symbol}' AND status = 'INVALID' ORDER BY last_touched_at DESC LIMIT 5")
        except Exception:
            ifvgs = []
            
        for fvg in ifvgs:
            # Setup 1: Fresh Breakout (Candle ini yang menjebol)
            if fvg['direction'] == 'Bearish' and close > fvg['high'] and open_ <= fvg['high']:
                return ('BUY', 'IFVG Breakout (Bearish FVG Jebol menjadi Support)', 'METHOD_IFVG_BREAKOUT_BUY', 89.0)
            if fvg['direction'] == 'Bullish' and close < fvg['low'] and open_ >= fvg['low']:
                return ('SELL', 'IFVG Breakout (Bullish FVG Jebol menjadi Resistance)', 'METHOD_IFVG_BREAKOUT_SELL', 89.0)
                
            # Setup 2: IFVG Retest (Harga kembali menguji IFVG setelah dijebol)
            if fvg['direction'] == 'Bearish' and low <= fvg['high'] and close > fvg['high'] and close > open_:
                # Harga turun retest Bearish IFVG (sekarang Support), lalu mantul naik
                body = abs(close - open_)
                lower_wick = min(open_, close) - low
                if lower_wick > body * 1.5:
                    return ('BUY', 'IFVG Retest (Mantul dari Inversion FVG Support)', 'METHOD_IFVG_RETEST_BUY', 89.5)
                    
            if fvg['direction'] == 'Bullish' and high >= fvg['low'] and close < fvg['low'] and close < open_:
                # Harga naik retest Bullish IFVG (sekarang Resistance), lalu mantul turun
                body = abs(close - open_)
                upper_wick = high - max(open_, close)
                if upper_wick > body * 1.5:
                    return ('SELL', 'IFVG Retest (Mantul dari Inversion FVG Resistance)', 'METHOD_IFVG_RETEST_SELL', 89.5)
                    
        return None

    def _resistance_support_rejection_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        active_res = ctx.get('active_resistance')
        active_sup = ctx.get('active_support')
        high = ctx.get('last_high', 0.0)
        low = ctx.get('last_low', 0.0)
        close = ctx.get('last_close', 0.0)
        open_ = ctx.get('last_open', 0.0)

        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low

        # Sell Rejection at Resistance (Shooting Star / Bearish Pinbar)
        if active_res and high >= active_res and close < active_res and close < open_:
            if upper_wick > body * 1.5:
                return ('SELL', 'Price Action Rejection di Resistance (Bearish Pinbar)', 'METHOD_REJECTION_RESISTANCE', 85.0)

        # Buy Rejection at Support (Hammer / Bullish Pinbar)
        if active_sup and low <= active_sup and close > active_sup and close > open_:
            if lower_wick > body * 1.5:
                return ('BUY', 'Price Action Rejection di Support (Bullish Pinbar)', 'METHOD_REJECTION_SUPPORT', 85.0)

        return None
    def _choch_reversal_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        """CHoCH = Change of Character. Struktur pasar berbalik arah.
        Ini adalah sinyal reversal paling kuat di SMC."""
        events = ctx.get('recent_events', [])
        for ev in events:
            evt_type = str(ev.get('event_type', '')).upper()
            if evt_type == 'CHOCH_BEARISH':
                return ('SELL', 'CHoCH Bearish: Struktur berbalik dari Bullish ke Bearish (Reversal Kuat)', 'METHOD_CHOCH_REVERSAL_SELL', 93.0)
            elif evt_type == 'CHOCH_BULLISH':
                return ('BUY', 'CHoCH Bullish: Struktur berbalik dari Bearish ke Bullish (Reversal Kuat)', 'METHOD_CHOCH_REVERSAL_BUY', 93.0)
        return None

    def _bos_momentum_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        """BOS = Break of Structure. Struktur pasar meneruskan tren.
        Ini adalah sinyal continuation yang kuat."""
        events = ctx.get('recent_events', [])
        for ev in events:
            evt_type = str(ev.get('event_type', '')).upper()
            if evt_type == 'BOS_BEARISH':
                return ('SELL', 'BOS Bearish: Struktur meneruskan tren turun (Continuation)', 'METHOD_BOS_MOMENTUM_SELL', 90.0)
            elif evt_type == 'BOS_BULLISH':
                return ('BUY', 'BOS Bullish: Struktur meneruskan tren naik (Continuation)', 'METHOD_BOS_MOMENTUM_BUY', 90.0)
        return None

    def _ote_retrace_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        """OTE (Optimal Trade Entry) - Fibonacci 0.618-0.786 retracement."""
        high = ctx.get('last_high', 0.0)
        low = ctx.get('last_low', 0.0)
        close = ctx.get('last_close', 0.0)
        open_ = ctx.get('last_open', 0.0)
        
        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low
        
        for ote in ctx.get('ote_zones', []):
            # Cek penolakan di area OTE dengan Pinbar
            if str(ote.get('direction', '')).upper() == 'BULLISH':
                if low <= ote['high'] and close > ote['low'] and close > open_:
                    if lower_wick > body * 1.5:
                        return ('BUY', 'Rejection di zona OTE Bullish (Pinbar Fib 0.618-0.786)', 'METHOD_OTE_BULLISH_RETRACE', 92.0)
            elif str(ote.get('direction', '')).upper() == 'BEARISH':
                if high >= ote['low'] and close < ote['high'] and close < open_:
                    if upper_wick > body * 1.5:
                        return ('SELL', 'Rejection di zona OTE Bearish (Pinbar Fib 0.618-0.786)', 'METHOD_OTE_BEARISH_RETRACE', 92.0)
        return None

    def _breaker_block_retest_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        """Breaker Block Retest - OB gagal yang menjadi level support/resistance kuat."""
        high = ctx.get('last_high', 0.0)
        low = ctx.get('last_low', 0.0)
        close = ctx.get('last_close', 0.0)
        open_ = ctx.get('last_open', 0.0)
        
        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low
        
        for brk in ctx.get('breakers', []):
            if str(brk.get('direction', '')).upper() == 'BULLISH':
                # Bullish Breaker Block adalah OB jebol yang kini jadi Support
                if low <= brk['high'] and close > brk['low'] and close > open_:
                    if lower_wick > body * 1.5:
                        return ('BUY', 'Retest Pinbar di Bullish Breaker Block (OB jebol jadi Support)', 'METHOD_BREAKER_BLOCK_BUY', 88.0)
            elif str(brk.get('direction', '')).upper() == 'BEARISH':
                # Bearish Breaker Block adalah OB jebol yang kini jadi Resistance
                if high >= brk['low'] and close < brk['high'] and close < open_:
                    if upper_wick > body * 1.5:
                        return ('SELL', 'Retest Pinbar di Bearish Breaker Block (OB jebol jadi Resistance)', 'METHOD_BREAKER_BLOCK_SELL', 88.0)
        return None

    def _asian_session_sweep_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        """Asian Session Liquidity Sweep - Sapuan High/Low sesi Asia untuk reversal."""
        try:
            m5 = self.storage.get_recent_candles(self.symbol, 'M5', 200)
            if not m5: return None
        except Exception:
            return None
            
        asian_high = -float('inf')
        asian_low = float('inf')
        
        # 10:00 to 14:00 Tokyo time is 01:00 to 05:00 UTC
        for c in m5:
            try:
                dt = datetime.fromisoformat(c.get('timestamp') or c.get('open_time'))
                if 1 <= dt.hour < 5:
                    asian_high = max(asian_high, _cval(c, 'high'))
                    asian_low = min(asian_low, _cval(c, 'low'))
            except Exception:
                continue
                
        if asian_high == -float('inf') or asian_low == float('inf'):
            return None
            
        high = ctx.get('last_high', 0.0)
        low = ctx.get('last_low', 0.0)
        close = ctx.get('last_close', 0.0)
        open_ = ctx.get('last_open', 0.0)
        
        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low
        
        # Sweep High: price went above asian_high, but closed below it (rejection)
        if high > asian_high and close < asian_high and close < open_:
            if upper_wick > body * 1.5:
                return ('SELL', 'Asian High Liquidity Sweep (Reversal Bearish)', 'METHOD_ASIAN_SWEEP_SELL', 89.0)
                
        if low < asian_low and close > asian_low and close > open_:
            if lower_wick > body * 1.5:
                return ('BUY', 'Asian Low Liquidity Sweep (Reversal Bullish)', 'METHOD_ASIAN_SWEEP_BUY', 89.0)
                
        return None

    def _ob_fvg_confluence_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        """OB + FVG Confluence (Power of 3) - Sniper entry area super kuat."""
        price = ctx['price']
        obs = ctx.get('obs', [])
        fvgs = ctx.get('fvgs', [])
        for ob in obs:
            for fvg in fvgs:
                ob_type = str(ob.get('type', '')).upper()
                fvg_dir = str(fvg.get('direction', '')).upper()
                if ob_type == fvg_dir:
                    # Cek overlap
                    overlap_low = max(ob['low'], fvg['low'])
                    overlap_high = min(ob['high'], fvg['high'])
                    if overlap_low <= overlap_high:  # Ada tumpukan
                        if overlap_low <= price <= overlap_high:
                            if ob_type == 'BULLISH':
                                return ('BUY', 'Power of 3: Harga masuk area Confluence Bullish OB + FVG', 'METHOD_OB_FVG_CONFLUENCE_BUY', 95.0)
                            elif ob_type == 'BEARISH':
                                return ('SELL', 'Power of 3: Harga masuk area Confluence Bearish OB + FVG', 'METHOD_OB_FVG_CONFLUENCE_SELL', 95.0)
        return None

    def _user_method_suite(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        # V7 user methods: raw rules as requested.
        htf_bias = ctx.get('htf_bias', 'MIXED')
        
        for fn in (
            lambda: self._crt_sweep_method(ctx, 'H4'),
            lambda: self._crt_sweep_method(ctx, 'D1'),
            lambda: self._h1_break_method(ctx),
            lambda: self._m15_double_top_method(ctx),
            lambda: self._fvg_rejection_aggro_method(ctx),
            lambda: self._ifvg_breakout_aggro_method(ctx),
            lambda: self._resistance_support_rejection_method(ctx),
            lambda: self._choch_reversal_method(ctx),
            lambda: self._bos_momentum_method(ctx),
            lambda: self._ote_retrace_method(ctx),
            lambda: self._breaker_block_retest_method(ctx),
            lambda: self._asian_session_sweep_method(ctx),
            lambda: self._ob_fvg_confluence_method(ctx),
        ):
            match = fn()
            if match and self._main_method_allowed(match[2]):
                dir_ = match[0]
                if htf_bias != 'MIXED' and dir_ != htf_bias:
                    continue  # Filter SMC execution based on HTF Bias (EMA 20 & 50)
                return match
        return None

    def _high_wr_method_suite(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        # V6: M1 and M5 run independently with shorter 6/8/12 lookbacks,
        # while still using M15 + H1 bias as the common safety filter.
        if self.signal_timeframe in ('M1', 'M5'):
            span_cfg = ((self.config or {}).get('adaptive_brain', {}).get('v6_timeframe_filters', {}) or {}).get(self.signal_timeframe, {}) or {}
            base_spans = span_cfg.get('max_span_by_lookback') or {}
            for lb in self.lookbacks:
                max_span = float(base_spans.get(str(lb), base_spans.get(lb, 5.0 if self.signal_timeframe == 'M1' else 10.0)))
                match = self._high_wr_sweep_variant(ctx, int(lb), max_span, f'METHOD_{self.signal_timeframe}_SWEEP_{int(lb)}')
                if match and self._main_method_allowed(match[2]):
                    return match
            for lb in self.lookbacks:
                max_span = float(base_spans.get(str(lb), base_spans.get(lb, 5.0 if self.signal_timeframe == 'M1' else 10.0)))
                match = self._high_wr_break_variant(ctx, int(lb), max_span, f'METHOD_{self.signal_timeframe}_BREAK_{int(lb)}')
                if match and self._main_method_allowed(match[2]):
                    return match
            return None

        checks = (
            lambda: self._high_wr_sweep_variant(ctx, 12, 10.0, 'METHOD_HW_SWEEP_12'),
            lambda: self._high_wr_m15_sweep_scalp(ctx),
            lambda: self._high_wr_sweep_variant(ctx, 32, 16.0, 'METHOD_HW_SWEEP_32'),
            lambda: self._high_wr_break_variant(ctx, 12, 10.0, 'METHOD_HW_BREAK_12'),
            lambda: self._high_wr_break_variant(ctx, 20, 13.0, 'METHOD_HW_BREAK_20'),
        )
        for fn in checks:
            match = fn()
            if match and self._main_method_allowed(match[2]):
                return match
        return None

    def _high_wr_m15_sweep_scalp(self, ctx: Dict[str, Any]) -> __import__('typing').Optional[Tuple[str, str, str, float]]:
        close = float(ctx.get('last_close') or 0)
        open_ = float(ctx.get('last_open') or 0)
        high = float(ctx.get('last_high') or 0)
        low = float(ctx.get('last_low') or 0)
        prev_high_20 = float(ctx.get('prev_high_20') or ctx.get('prev_high') or 0)
        prev_low_20 = float(ctx.get('prev_low_20') or ctx.get('prev_low') or 0)
        atr = float(ctx.get('atr') or 0)
        body_ratio = float(ctx.get('body_ratio') or 0)
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        body_size = max(body_top - body_bottom, 0.01)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        m15_bias = ctx.get('m15_bias')
        h1_bias = ctx.get('h1_bias')

        prev_span = max(prev_high_20 - prev_low_20, 0.01)
        buy_sweep_dist = prev_low_20 - low
        buy_reclaim_dist = close - prev_low_20
        sell_sweep_dist = high - prev_high_20
        sell_reclaim_dist = prev_high_20 - close

        # V2 strict filter: keeps only clean sweep-reclaim setups that stayed >65% WR
        # in the uploaded month-by-month CSV scan.
        if atr < 1.10 or atr > 6.0 or body_ratio < 0.35 or prev_span > 13.0:
            return None

        buy_ok = (
            low <= prev_low_20
            and close > prev_low_20
            and close > open_
            and lower_wick >= body_size * 0.5
            and buy_sweep_dist >= 0.30
            and buy_reclaim_dist >= 1.25
            and self._high_wr_common_filter(ctx, 'BUY')
        )
        if buy_ok:
            return ('BUY', 'HIGH WR V2 M15 SWEEP SCALP: strict low sweep + reclaim + TP1 scalp', 'METHOD_HIGH_WR_M15_SWEEP_SCALP_BUY', 95.0)

        sell_ok = (
            high >= prev_high_20
            and close < prev_high_20
            and close < open_
            and upper_wick >= body_size * 0.5
            and sell_sweep_dist >= 0.30
            and sell_reclaim_dist >= 1.25
            and self._high_wr_common_filter(ctx, 'SELL')
        )
        if sell_ok:
            return ('SELL', 'HIGH WR V2 M15 SWEEP SCALP: strict high sweep + reclaim + TP1 scalp', 'METHOD_HIGH_WR_M15_SWEEP_SCALP_SELL', 95.0)

        return None

    def _evaluate_sandbox_rules(self, ctx: Dict[str, Any]) -> __import__('typing').Optional[Tuple[str, str, str, float]]:
        import sys
        if 'run_simulator' not in sys.modules:
            return None
            
        run_sim = sys.modules['run_simulator']
        sandbox_data = getattr(run_sim, 'SANDBOX_RULES', None)
        if not sandbox_data:
            return None
            
        for m in sandbox_data.get('methods', []):
            if self._method_blocked(m.get('name', '')):
                continue
            if not self._relaxed_sandbox_quality_ok(m, ctx):
                continue
            match = True
            
            # Prepare safe evaluation context
            safe_ctx = dict(ctx)
            safe_ctx['True'] = True
            safe_ctx['False'] = False
            safe_ctx['true'] = True
            safe_ctx['false'] = False
            
            # Map complex properties
            if 'fvgs' in safe_ctx:
                safe_ctx['fvgs'] = len(safe_ctx['fvgs']) > 0
            if 'ob' not in safe_ctx: safe_ctx['ob'] = False
            if 'ote' not in safe_ctx: safe_ctx['ote'] = False
            
            # Evaluate Conditions
            for cond in m.get('conditions', []):
                cond_py = cond.replace('== true', '== True').replace('== false', '== False')
                if 'contains' in cond_py:
                    parts = cond_py.split('contains')
                    cond_py = f"{parts[1].strip()} in str({parts[0].strip()})"
                
                try:
                    if not eval(cond_py, {"__builtins__": {}}, safe_ctx):
                        match = False
                        break
                except Exception as e:
                    match = False
                    break
                    
            if not match: continue
            
            # Evaluate Invalid_If
            for inv in m.get('invalid_if', []):
                inv_py = inv.replace('== true', '== True').replace('== false', '== False')
                if 'contains' in inv_py:
                    parts = inv_py.split('contains')
                    inv_py = f"{parts[1].strip()} in str({parts[0].strip()})"
                
                try:
                    if eval(inv_py, {"__builtins__": {}}, safe_ctx):
                        match = False
                        break
                except Exception:
                    pass
                    
            if match:
                return (m['direction'].upper(), f"AI Sandbox: {m['name']}", m['name'], 55.0)
                
        return None

    def _antigravity_experimental_method(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        # ANTIGRAVITY_MINED_V1: High-Probability Trend Continuation + Liquidity Sweep Rejection
        # Mined from Jan-May 2026 Data
        m15_bias = ctx.get('m15_bias')
        h1_bias = ctx.get('h1_bias')
        momentum = ctx.get('momentum')
        close = ctx.get('last_close', 0)
        open_ = ctx.get('last_open', 0)
        high = ctx.get('last_high', 0)
        low = ctx.get('last_low', 0)
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        body_size = max(body_top - body_bottom, 0.01)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        body_ratio = float(ctx.get('body_ratio') or 0)
        
        # Bullish Setup
        if m15_bias == 'bullish' and h1_bias == 'bullish' and momentum != 'bearish':
            if ctx.get('sentuh_low') and close > open_ and body_ratio > 0.6:
                # True Pinbar Rejection: Wick at least 2x the body
                if lower_wick > body_size * 2.0:
                    return ('BUY', 'ANTIGRAVITY_MINED_V1: Bullish Trend + Liquidity Sweep + Strong Pinbar', 'ANTIGRAVITY_MINED_V1_BUY', 97.0)
                    
        # Bearish Setup
        if m15_bias == 'bearish' and h1_bias == 'bearish' and momentum != 'bullish':
            if ctx.get('sentuh_high') and close < open_ and body_ratio > 0.6:
                # True Pinbar Rejection: Wick at least 2x the body
                if upper_wick > body_size * 2.0:
                    return ('SELL', 'ANTIGRAVITY_MINED_V1: Bearish Trend + Liquidity Sweep + Strong Pinbar', 'ANTIGRAVITY_MINED_V1_SELL', 97.0)

        # CHOPPY MARKET SCALP (Auto-Injected)
        # Sangat rileks, hanya mengandalkan ekor panjang di market ranging/biasa
        atr = ctx.get('atr', 2.0)
        if (m15_bias == 'ranging' or h1_bias == 'ranging' or (m15_bias != h1_bias)) and (1.0 < atr < 3.0):
            if lower_wick > body_size * 2.5 and lower_wick > atr * 0.4 and close > open_:
                return ('BUY', 'CHOPPY_SCALP: Market Ranging + Rejection Ekor Bawah Panjang (ATR 1-3)', 'METHOD_CHOPPY_SCALP_BUY', 85.0)
            if upper_wick > body_size * 2.5 and upper_wick > atr * 0.4 and close < open_:
                return ('SELL', 'CHOPPY_SCALP: Market Ranging + Rejection Ekor Atas Panjang (ATR 1-3)', 'METHOD_CHOPPY_SCALP_SELL', 85.0)

        struct = ctx.get('structure', {})
        support = struct.get('nearest_support')
        resistance = struct.get('nearest_resistance')
        choppy = ctx.get('choppy', False) or struct.get('choppy', False)
        fvgs = ctx.get('fvgs', [])
        candles = ctx.get('candles', [])
        c1 = candles[-1] if len(candles) >= 1 else None
        c2 = candles[-2] if len(candles) >= 2 else None
        c3 = candles[-3] if len(candles) >= 3 else None

        # 1. METHOD_POI_REBOUND (Mantul Keras)
        # Harga turun ke Support/FVG lalu ditolak keras (Pinbar besar) + Sweep + Retest
        sweep_type = struct.get('sweep_type')
        if support and abs(low - support) < (atr * 1.0):
            # Batalkan setup jika close kuat menembus support
            if close > support and lower_wick > body_size * 1.8 and close > open_:
                if sweep_type == 'bullish' and h1_bias == 'bullish' and m15_bias == 'bullish' and ctx.get('h4_bias') == 'bullish' and atr > 1.2:
                    return ('BUY', 'POI_REBOUND: Rejection + Sweep dari Support (ATR>1.2)', 'METHOD_POI_REBOUND_BUY', 88.0)
        if resistance and abs(high - resistance) < (atr * 1.0):
            if close < resistance and upper_wick > body_size * 1.8 and close < open_:
                if sweep_type == 'bearish' and h1_bias == 'bearish' and m15_bias == 'bearish' and ctx.get('h4_bias') == 'bearish' and atr > 1.2:
                    return ('SELL', 'POI_REBOUND: Rejection + Sweep dari Resistance (ATR>1.2)', 'METHOD_POI_REBOUND_SELL', 88.0)

        # Cek FVG & OB Rebound
        for fvg in fvgs:
            if fvg['direction'] == 'Bullish' and low <= fvg['high'] and close > fvg['low']:
                if close > open_ and lower_wick > body_size * 2.0:
                    if sweep_type == 'bullish' and h1_bias != 'bearish' and m15_bias != 'bearish':
                        return ('BUY', 'POI_REBOUND: Rejection keras + Sweep di Bullish FVG', 'METHOD_POI_REBOUND_FVG_BUY', 87.0)
            if fvg['direction'] == 'Bearish' and high >= fvg['low'] and close < fvg['high']:
                if close < open_ and upper_wick > body_size * 2.0:
                    if sweep_type == 'bearish' and h1_bias != 'bullish' and m15_bias != 'bullish':
                        return ('SELL', 'POI_REBOUND: Rejection keras + Sweep di Bearish FVG', 'METHOD_POI_REBOUND_FVG_SELL', 87.0)
                    
        obs = ctx.get('obs', [])
        for ob in obs:
            ob_dir = str(ob.get('type') or ob.get('direction') or '').lower()
            ob_low, ob_high = float(ob.get('low', 0)), float(ob.get('high', 0))
            is_fresh = ob.get('touches', 0) == 0 or ob.get('fresh', True)
            if is_fresh and 'bull' in ob_dir and low <= ob_high and close > ob_low:
                # Cancel if close is below OB (jebol OB)
                if close > ob_low and lower_wick > body_size * 2.0 and close > open_ and m15_bias == 'bullish' and h1_bias == 'bullish':
                    if sweep_type == 'bullish':
                        return ('BUY', 'POI_REBOUND: Rejection keras + Sweep di Fresh Bullish Order Block', 'METHOD_POI_REBOUND_OB_BUY', 87.5)
            if is_fresh and 'bear' in ob_dir and high >= ob_low and close < ob_high:
                # Cancel if close is above OB
                if close < ob_high and upper_wick > body_size * 2.0 and close < open_ and m15_bias == 'bearish' and h1_bias == 'bearish':
                    if sweep_type == 'bearish':
                        return ('SELL', 'POI_REBOUND: Rejection keras + Sweep di Fresh Bearish Order Block', 'METHOD_POI_REBOUND_OB_SELL', 87.5)

        # 2. METHOD_POI_ACCUMULATION (Sideways di POI lalu Break)
        if c1 and c2 and c3:
            c1_body = abs(c1['open'] - c1['close'])
            c2_body = abs(c2['open'] - c2['close'])
            c3_body = abs(c3['open'] - c3['close'])
            
            # Akumulasi ketat: c2 dan c3 sangat kecil (kurang dari 0.25 ATR)
            if choppy or (c2_body < atr * 0.25 and c3_body < atr * 0.25):
                # Breakout kuat (Ledakan lebih dari 1.0 ATR)
                if support and abs(c1['low'] - support) < (atr * 0.5):
                    if c1['close'] > c1['open'] and c1_body > atr * 1.0 and c1['close'] > max(c2['high'], c3['high']):
                        return ('BUY', 'POI_ACCUMULATION: Sideways ketat di Support lalu Breakout Kuat ke Atas', 'METHOD_POI_ACCUMULATION_BUY', 86.0)
                if resistance and abs(c1['high'] - resistance) < (atr * 0.5):
                    if c1['close'] < c1['open'] and c1_body > atr * 1.0 and c1['close'] < min(c2['low'], c3['low']):
                        return ('SELL', 'POI_ACCUMULATION: Sideways ketat di Resistance lalu Breakdown Kuat ke Bawah', 'METHOD_POI_ACCUMULATION_SELL', 86.0)

        # 3. METHOD_POI_FLIP_BREAK (Ngerem lalu Dijebol / POI Gagal)
        if c1 and c2:
            c2_body = abs(c2['open'] - c2['close'])
            c1_body = abs(c1['open'] - c1['close'])
            
            # c2 ngerem (doji/kecil) di dekat Support, tapi c1 malah jebol Support ke bawah
            if support and abs(c2['low'] - support) < (atr * 1.0) and c2_body < atr * 0.4:
                if c1['close'] < support and c1['close'] < c1['open'] and c1_body > atr * 0.8:
                    return ('SELL', 'POI_FLIP_BREAK: Support dijebol keras setelah ngerem (Support turns Resistance)', 'METHOD_POI_FLIP_BREAK_SELL', 89.0)
            
            # c2 ngerem (doji/kecil) di dekat Resistance, tapi c1 malah jebol Resistance ke atas
            if resistance and abs(c2['high'] - resistance) < (atr * 1.0) and c2_body < atr * 0.4:
                if c1['close'] > resistance and c1['close'] > c1['open'] and c1_body > atr * 0.8:
                    return ('BUY', 'POI_FLIP_BREAK: Resistance dijebol keras setelah ngerem (Resistance turns Support)', 'METHOD_POI_FLIP_BREAK_BUY', 89.0)

        # 4. METHOD_BOS_BREAKOUT (Mengejar Momentum Break of Structure dengan Retest)
        # Jangan entry langsung saat BOS. Tunggu retest ke OB/FVG.
        h1_bias = ctx.get('h1_bias')
        h4_bias = ctx.get('h4_bias')
        
        # Cek FVG/OB untuk retest
        retest_fvg_bull = False
        retest_fvg_bear = False
        for fvg in fvgs:
            if fvg['direction'] == 'Bullish' and low <= fvg['high'] and close > fvg['low']:
                retest_fvg_bull = True
            if fvg['direction'] == 'Bearish' and high >= fvg['low'] and close < fvg['high']:
                retest_fvg_bear = True
                
        retest_ob_bull = False
        retest_ob_bear = False
        obs = ctx.get('obs', [])
        for ob in obs:
            ob_dir = str(ob.get('type') or ob.get('direction') or '').lower()
            if 'bull' in ob_dir and low <= float(ob.get('high', 0)) and close > float(ob.get('low', 0)):
                retest_ob_bull = True
            if 'bear' in ob_dir and high >= float(ob.get('low', 0)) and close < float(ob.get('high', 0)):
                retest_ob_bear = True
        
        has_retest_bull = retest_fvg_bull or retest_ob_bull
        has_retest_bear = retest_fvg_bear or retest_ob_bear
        
        demand_zone = struct.get('nearest_support')
        supply_zone = struct.get('nearest_resistance')
        
        # Bullish BOS Retest
        if ctx.get('break_bull') and has_retest_bull:
            # Entry hanya jika candle retest close bullish dan menolak dari OB/FVG
            if close > open_ and lower_wick > body_size * 1.0:
                # Filter: supply zone lawan jangan terlalu dekat (misal jarak minimal 1.5 ATR)
                if not supply_zone or abs(supply_zone - close) > atr * 1.5:
                    # Filter: harus ada sweep low sebelumnya
                    if struct.get('sweep_type') == 'bullish' or ctx.get('sentuh_low'):
                        return ('BUY', 'BOS_BREAKOUT: Bullish BOS Retest FVG/OB (Terkonfirmasi)', 'METHOD_BOS_BREAKOUT_BUY', 88.5)
                
        # Bearish BOS Retest
        if ctx.get('break_bear') and has_retest_bear:
            # Entry hanya jika candle retest close bearish dan menolak dari OB/FVG
            if close < open_ and upper_wick > body_size * 1.0:
                # Filter: demand zone lawan jangan terlalu dekat
                if not demand_zone or abs(close - demand_zone) > atr * 1.5:
                    # Filter: harus ada sweep high sebelumnya
                    if struct.get('sweep_type') == 'bearish' or ctx.get('sentuh_high'):
                        return ('SELL', 'BOS_BREAKOUT: Bearish BOS Retest FVG/OB (Terkonfirmasi)', 'METHOD_BOS_BREAKOUT_SELL', 88.5)

        # 5. METHOD_IFVG_BREAKOUT (Inversion FVG Momentum)
        # Jika Bearish FVG dijebol keras ke atas, langsung BUY (karena menjadi Support baru)
        for fvg in fvgs:
            if fvg['direction'] == 'Bearish' and close > fvg['high'] and open_ <= fvg['high']:
                if close > open_ and body_size > atr * 0.5:
                    if upper_wick < body_size * 0.8: # Pastikan bukan ekor/fakeout
                        return ('BUY', 'IFVG_BREAKOUT: Bearish FVG dijebol ke atas (Inversion FVG Momentum)', 'METHOD_IFVG_BREAK_BUY', 88.2)
                        
            # Jika Bullish FVG dijebol keras ke bawah, langsung SELL
            if fvg['direction'] == 'Bullish' and close < fvg['low'] and open_ >= fvg['low']:
                if close < open_ and body_size > atr * 0.5:
                    if lower_wick < body_size * 0.8: # Pastikan bukan ekor/fakeout
                        return ('SELL', 'IFVG_BREAKOUT: Bullish FVG dijebol ke bawah (Inversion FVG Momentum)', 'METHOD_IFVG_BREAK_SELL', 88.2)

        return None

    def _new_user_methods(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        price = ctx.get('price', 0)
        close = ctx.get('last_close', 0)
        open_ = ctx.get('last_open', 0)
        high = ctx.get('last_high', 0)
        low = ctx.get('last_low', 0)
        momentum = ctx.get('momentum')
        atr = ctx.get('atr', 2.0)
        m15_bias = ctx.get('m15_bias')
        h1_bias = ctx.get('h1_bias')
        h4_bias = ctx.get('h4_bias')
        fvgs = ctx.get('fvgs', [])
        obs = ctx.get('obs', [])
        struct = ctx.get('structure', {})
        sweep_type = struct.get('sweep_type')
        candles = ctx.get('candles', [])
        
        if len(candles) < 3: return None
        
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        body_size = max(body_top - body_bottom, 0.01)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        
        is_bullish_close = close > open_
        is_bearish_close = close < open_
        is_strong_bullish = is_bullish_close and body_size > atr * 0.8
        is_strong_bearish = is_bearish_close and body_size > atr * 0.8
        
        demand_zone = struct.get('nearest_support')
        supply_zone = struct.get('nearest_resistance')
        trend = struct.get('trend', '')
        
        # NEW AGGRESSIVE: 1. MICRO SWEEP SCALP (M1/M5 Fast Sweep)
        if body_size > atr * 0.4 and (atr < 2.5) and trend == 'EXPANSION' and h1_bias == m15_bias:
            if sweep_type == 'bullish' and is_bullish_close and lower_wick > body_size * 1.0:
                if m15_bias == 'bullish':
                    return ('BUY', 'MICRO_SWEEP_SCALP: Sweep Low + Rejection (Aggressive)', 'METHOD_MICRO_SWEEP_SCALP_BUY', 85.0)
            if sweep_type == 'bearish' and is_bearish_close and upper_wick > body_size * 1.0:
                if m15_bias == 'bearish':
                    return ('SELL', 'MICRO_SWEEP_SCALP: Sweep High + Rejection (Aggressive)', 'METHOD_MICRO_SWEEP_SCALP_SELL', 85.0)

        # NEW AGGRESSIVE: 2. MOMENTUM IGNITION (Marubozu/Engulfing without Retest)
        if body_size > atr * 1.5 and upper_wick < atr * 0.2 and lower_wick < atr * 0.2 and trend == 'EXPANSION' and h1_bias == m15_bias:
            if is_bullish_close and m15_bias == 'bullish' and h1_bias == 'bullish' and ctx.get('break_bull') and (not supply_zone or abs(supply_zone - close) > atr * 2.0):
                return ('BUY', 'MOMENTUM_IGNITION: Giant Bullish Marubozu (Institutional Entry)', 'METHOD_MOMENTUM_IGNITION_BUY', 86.0)
            if is_bearish_close and m15_bias == 'bearish' and h1_bias == 'bearish' and ctx.get('break_bear') and (not demand_zone or abs(close - demand_zone) > atr * 2.0):
                return ('SELL', 'MOMENTUM_IGNITION: Giant Bearish Marubozu (Institutional Entry)', 'METHOD_MOMENTUM_IGNITION_SELL', 86.0)

        # NEW AGGRESSIVE: 3. SESSION OPEN BREAKOUT (First 30 mins of NY/London)
        try:
            from datetime import datetime, timezone
            dt_str = ctx.get('timestamp') or ''
            if dt_str:
                dt = datetime.fromisoformat(dt_str)
                hour = dt.hour
                minute = dt.minute
            else:
                hour = datetime.now(timezone.utc).hour
                minute = datetime.now(timezone.utc).minute
            is_session_open = (hour == 8 or hour == 13) and minute <= 30
        except:
            is_session_open = False
            
        if is_session_open:
            if ctx.get('break_bull') and is_strong_bullish and m15_bias == 'bullish' and trend == 'EXPANSION' and h1_bias == 'bullish':
                if not supply_zone or abs(supply_zone - close) > atr * 2.0:
                    return ('BUY', 'SESSION_OPEN_BREAKOUT: Bullish Breakout in first 30 mins of Session', 'METHOD_SESSION_OPEN_BREAKOUT_BUY', 87.0)
            if ctx.get('break_bear') and is_strong_bearish and m15_bias == 'bearish' and trend == 'EXPANSION' and h1_bias == 'bearish':
                if not demand_zone or abs(close - demand_zone) > atr * 2.0:
                    return ('SELL', 'SESSION_OPEN_BREAKOUT: Bearish Breakout in first 30 mins of Session', 'METHOD_SESSION_OPEN_BREAKOUT_SELL', 87.0)

        # 1. METHOD_LIQUIDITY_SWEEP_FVG_BUY & 2. METHOD_LIQUIDITY_SWEEP_FVG_SELL
        for fvg in fvgs:
            fvg_size = fvg['high'] - fvg['low']
            if fvg_size < atr * 0.2: continue
            
            if fvg['direction'] == 'Bullish':
                if low <= fvg['high'] and close > fvg['low'] and is_bullish_close:
                    if sweep_type == 'bullish' or ctx.get('sentuh_low'):
                        if not supply_zone or abs(supply_zone - close) > atr * 1.5:
                            return ('BUY', 'LIQUIDITY_SWEEP_FVG: Sweep Low + Strong Bullish + FVG Retest', 'METHOD_LIQUIDITY_SWEEP_FVG_BUY', 90.0)
            
            if fvg['direction'] == 'Bearish':
                if high >= fvg['low'] and close < fvg['high'] and is_bearish_close:
                    if sweep_type == 'bearish' or ctx.get('sentuh_high'):
                        if not demand_zone or abs(close - demand_zone) > atr * 1.5:
                            return ('SELL', 'LIQUIDITY_SWEEP_FVG: Sweep High + Strong Bearish + FVG Retest', 'METHOD_LIQUIDITY_SWEEP_FVG_SELL', 90.0)

        # 3. METHOD_BOS_RETEST_OB_BUY & 4. METHOD_BOS_RETEST_OB_SELL
        for ob in obs:
            ob_dir = str(ob.get('type') or ob.get('direction') or '').lower()
            ob_low, ob_high = float(ob.get('low', 0)), float(ob.get('high', 0))
            is_fresh = ob.get('touches', 0) == 0 or ob.get('fresh', True)
            if is_fresh and atr > 1.0:
                if 'bull' in ob_dir and low <= ob_high and close > ob_low:
                    if ctx.get('break_bull') and is_bullish_close and lower_wick > body_size * 1.5:
                        if not supply_zone or abs(supply_zone - close) > atr * 1.5:
                            return ('BUY', 'BOS_RETEST_OB: Bullish BOS + Retest Fresh OB + Strong Pinbar', 'METHOD_BOS_RETEST_OB_BUY', 89.0)
                if 'bear' in ob_dir and high >= ob_low and close < ob_high:
                    if ctx.get('break_bear') and is_bearish_close and upper_wick > body_size * 1.5:
                        if not demand_zone or abs(close - demand_zone) > atr * 1.5:
                            return ('SELL', 'BOS_RETEST_OB: Bearish BOS + Retest Fresh OB + Strong Pinbar', 'METHOD_BOS_RETEST_OB_SELL', 89.0)

        # 5. METHOD_CHOCH_SWEEP_REVERSAL_BUY & 6. METHOD_CHOCH_SWEEP_REVERSAL_SELL
        if sweep_type == 'bullish' and struct.get('break_type') == 'MSS_BULLISH':
            if is_bullish_close and lower_wick > body_size * 1.5 and m15_bias != 'bearish' and h1_bias != 'bearish':
                return ('BUY', 'CHOCH_SWEEP_REVERSAL: Sweep Low + CHOCH Bullish + Rejection', 'METHOD_CHOCH_SWEEP_REVERSAL_BUY', 91.0)
        if sweep_type == 'bearish' and struct.get('break_type') == 'MSS_BEARISH':
            if is_bearish_close and upper_wick > body_size * 1.5 and m15_bias != 'bullish' and h1_bias != 'bullish':
                return ('SELL', 'CHOCH_SWEEP_REVERSAL: Sweep High + CHOCH Bearish + Rejection', 'METHOD_CHOCH_SWEEP_REVERSAL_SELL', 91.0)

        # 7. METHOD_ASIA_RANGE_SWEEP_BUY & 8. METHOD_ASIA_RANGE_SWEEP_SELL
        try:
            hour = datetime.now(timezone.utc).hour
        except:
            hour = 14
        if 8 <= hour <= 21:
            if sweep_type == 'bullish' and is_strong_bullish and lower_wick > body_size * 0.8 and m15_bias == 'bullish' and h1_bias == 'bullish':
                return ('BUY', 'ASIA_RANGE_SWEEP: London/NY Sweep Low + Reversal Bullish', 'METHOD_ASIA_RANGE_SWEEP_BUY', 89.5)
            if sweep_type == 'bearish' and is_strong_bearish and upper_wick > body_size * 0.8 and m15_bias == 'bearish' and h1_bias == 'bearish':
                return ('SELL', 'ASIA_RANGE_SWEEP: London/NY Sweep High + Reversal Bearish', 'METHOD_ASIA_RANGE_SWEEP_SELL', 89.5)

        # 9. METHOD_INDUCEMENT_TRAP_BUY & 10. METHOD_INDUCEMENT_TRAP_SELL
        if not ctx.get('choppy') and atr > 1.2:
            if sweep_type == 'bullish':
                is_huge_engulfing = is_strong_bullish and body_size > (atr * 1.5)
                reclaim_fvg = False
                for fvg in fvgs:
                    if fvg['direction'] == 'Bullish' and low < fvg['low'] and close > fvg['low']:
                        reclaim_fvg = True
                        break
                if is_huge_engulfing or reclaim_fvg:
                    if m15_bias == 'bullish' and h1_bias == 'bullish':
                        return ('BUY', 'INDUCEMENT_TRAP: Sweep Low + Engulfing/FVG Reclaim', 'METHOD_INDUCEMENT_TRAP_BUY', 92.0)
            if sweep_type == 'bearish' and is_strong_bearish:
                if m15_bias == 'bearish' and h1_bias == 'bearish':
                    return ('SELL', 'INDUCEMENT_TRAP: Sweep Minor High/Equal High + Strong Reversal (ATR>1.2)', 'METHOD_INDUCEMENT_TRAP_SELL', 92.0)

        # 11. METHOD_FVG_CONTINUATION_BUY & 12. METHOD_FVG_CONTINUATION_SELL
        if trend == 'TRENDING' or trend == 'EXPANSION':
            for fvg in fvgs:
                if fvg['direction'] == 'Bullish' and momentum != 'bearish':
                    if low <= fvg['high'] and close > fvg['low'] and is_bullish_close:
                        if not supply_zone or abs(supply_zone - close) > atr * 1.5:
                            return ('BUY', 'FVG_CONTINUATION: Bullish Trend + Retest FVG', 'METHOD_FVG_CONTINUATION_BUY', 88.0)
                if fvg['direction'] == 'Bearish' and momentum != 'bullish':
                    if high >= fvg['low'] and close < fvg['high'] and is_bearish_close:
                        if not demand_zone or abs(close - demand_zone) > atr * 1.5:
                            return ('SELL', 'FVG_CONTINUATION: Bearish Trend + Retest FVG', 'METHOD_FVG_CONTINUATION_SELL', 88.0)
        # 13. METHOD_BREAK_AND_RETEST
        if trend in ['TRENDING', 'EXPANSION'] and not ctx.get('choppy') and atr > 1.2:
            if h1_bias == 'bullish' and m15_bias == 'bullish':
                if demand_zone and abs(low - demand_zone) < atr * 0.8 and is_bullish_close and lower_wick > body_size * 1.5 and upper_wick < body_size * 0.8:
                    return ('BUY', 'BREAK_AND_RETEST: Trend Naik (H1+M15) + Retest Support + Strong Rejection', 'METHOD_BREAK_AND_RETEST_BUY', 89.5)
            if h1_bias == 'bearish' and m15_bias == 'bearish':
                if supply_zone and abs(high - supply_zone) < atr * 0.8 and is_bearish_close and upper_wick > body_size * 1.5 and lower_wick < body_size * 0.8:
                    return ('SELL', 'BREAK_AND_RETEST: Trend Turun (H1+M15) + Retest Resistance + Strong Rejection', 'METHOD_BREAK_AND_RETEST_SELL', 89.5)

        # 14. METHOD_DRAW_ON_LIQUIDITY (Kebalikan Inducement)
        if trend in ['TRENDING', 'EXPANSION'] and not ctx.get('choppy') and atr > 1.2:
            if supply_zone and (atr * 1.5) < (supply_zone - close) < (atr * 3.0) and m15_bias == 'bullish' and h1_bias == 'bullish':
                if is_bullish_close and body_size > atr * 0.8 and lower_wick < body_size * 0.5:
                    return ('BUY', 'DRAW_ON_LIQUIDITY: Harga ditarik menuju Unmitigated Supply/Liquidity (M15+H1 Aligned)', 'METHOD_DRAW_ON_LIQUIDITY_BUY', 89.0)
            if demand_zone and (atr * 1.5) < (close - demand_zone) < (atr * 3.0) and m15_bias == 'bearish' and h1_bias == 'bearish':
                if is_bearish_close and body_size > atr * 0.8 and upper_wick < body_size * 0.5:
                    return ('SELL', 'DRAW_ON_LIQUIDITY: Harga ditarik menuju Unmitigated Demand/Liquidity (M15+H1 Aligned)', 'METHOD_DRAW_ON_LIQUIDITY_SELL', 89.0)
        # 15. METHOD_FOLLOW_THE_TREND (M5/M15 Breakout Continuation)
        if trend == 'EXPANSION' and momentum == m15_bias and m15_bias == h1_bias and not ctx.get('choppy'):
            if m15_bias == 'bullish' and ctx.get('break_bull') and is_strong_bullish and (atr * 1.2) < body_size < (atr * 2.0) and lower_wick < body_size * 0.5 and upper_wick < body_size * 0.3:
                if not supply_zone or abs(supply_zone - close) > atr * 2.0:
                    return ('BUY', 'FOLLOW_THE_TREND: M5+M15+H1 Bullish + Strong Breakout High (Body > ATR, No Exhaustion)', 'METHOD_FOLLOW_THE_TREND_BUY', 90.0)
            if m15_bias == 'bearish' and ctx.get('break_bear') and is_strong_bearish and (atr * 1.2) < body_size < (atr * 2.0) and upper_wick < body_size * 0.5 and lower_wick < body_size * 0.3:
                if not demand_zone or abs(close - demand_zone) > atr * 2.0:
                    return ('SELL', 'FOLLOW_THE_TREND: M5+M15+H1 Bearish + Strong Breakout Low (Body > ATR, No Exhaustion)', 'METHOD_FOLLOW_THE_TREND_SELL', 90.0)

        # 16. METHOD_REVERSAL (M5/M15 Counter-Momentum Sniper)
        if sweep_type == 'bullish' and momentum == 'bearish':
            if m15_bias == 'bullish' and h1_bias == 'bullish' and close > open_ and lower_wick > body_size * 2.0:
                return ('BUY', 'CHOCH_SWEEP_REVERSAL: Sweep Support (M5 Bearish -> M15+H1 Bullish Divergence)', 'METHOD_CHOCH_SWEEP_REVERSAL_BUY', 88.0)
        if sweep_type == 'bearish' and momentum == 'bullish':
            if m15_bias == 'bearish' and h1_bias == 'bearish' and close < open_ and upper_wick > body_size * 2.0:
                return ('SELL', 'CHOCH_SWEEP_REVERSAL: Sweep Resistance (M5 Bullish -> M15+H1 Bearish Divergence)', 'METHOD_CHOCH_SWEEP_REVERSAL_SELL', 88.0)

        return None

    
    def _aggressive_30_methods(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        price = ctx.get('price', 0)
        close = ctx.get('last_close', 0)
        open_ = ctx.get('last_open', 0)
        high = ctx.get('last_high', 0)
        low = ctx.get('last_low', 0)
        momentum = ctx.get('momentum')
        atr = ctx.get('atr', 2.0)
        m15_bias = ctx.get('m15_bias')
        h1_bias = ctx.get('h1_bias')
        fvgs = ctx.get('fvgs', [])
        obs = ctx.get('obs', [])
        struct = ctx.get('structure', {})
        sweep_type = struct.get('sweep_type')
        candles = ctx.get('candles', [])
        
        if len(candles) < 2: return None
        
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        body_size = max(body_top - body_bottom, 0.01)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        
        is_bullish_close = close > open_
        is_bearish_close = close < open_
        is_strong_bullish = is_bullish_close and body_size > atr * 0.8
        is_strong_bearish = is_bearish_close and body_size > atr * 0.8
        trend = struct.get('trend', '')
        demand_zone = struct.get('nearest_support')
        supply_zone = struct.get('nearest_resistance')

        prev_c = candles[-2] if len(candles) >= 2 else None
        
        # CATEGORY 1: Turtle Soup & Liquidity Sweeps
        # 1-2. Micro Turtle Soup
        if sweep_type == 'bullish' and is_bullish_close and lower_wick > body_size * 1.5 and m15_bias == 'bullish' and h1_bias == 'bullish' and demand_zone and abs(low - demand_zone) < atr * 2.0:
            return ('BUY', 'MICRO_TURTLE_SOUP: Sweep Low + Pinbar Rejection', 'METHOD_MICRO_TURTLE_SOUP_BUY', 86.0)
        if sweep_type == 'bearish' and is_bearish_close and upper_wick > body_size * 1.5 and m15_bias == 'bearish' and h1_bias == 'bearish' and supply_zone and abs(high - supply_zone) < atr * 2.0:
            return ('SELL', 'MICRO_TURTLE_SOUP: Sweep High + Pinbar Rejection', 'METHOD_MICRO_TURTLE_SOUP_SELL', 86.0)

        # 3-4. H1 Sweep Scalp
        if ctx.get('h1_sweep_low') and is_strong_bullish and m15_bias == 'bullish':
            return ('BUY', 'H1_SWEEP_SCALP: H1 Low Swept + M15 Bullish Engulf', 'METHOD_H1_SWEEP_SCALP_BUY', 88.0)
        if ctx.get('h1_sweep_high') and is_strong_bearish and m15_bias == 'bearish':
            return ('SELL', 'H1_SWEEP_SCALP: H1 High Swept + M15 Bearish Engulf', 'METHOD_H1_SWEEP_SCALP_SELL', 88.0)

        # 5-6. Equal Highs/Lows Sweep
        if struct.get('eqh_sweep') and is_bearish_close and upper_wick > body_size:
            return ('SELL', 'EQUAL_HIGHS_SWEEP: Double Top Swept + Rejection', 'METHOD_EQUAL_HIGHS_SWEEP_SELL', 89.0)
        if struct.get('eql_sweep') and is_bullish_close and lower_wick > body_size:
            return ('BUY', 'EQUAL_LOWS_SWEEP: Double Bottom Swept + Rejection', 'METHOD_EQUAL_LOWS_SWEEP_BUY', 89.0)

        # 7-8. Asia Liquidity Run
        try:
            from datetime import datetime, timezone
            dt_str = ctx.get('timestamp') or ''
            if dt_str:
                dt = datetime.fromisoformat(dt_str)
                hour = dt.hour
            else:
                hour = datetime.now(timezone.utc).hour
            if hour in [7, 8, 9]: # London Open
                if sweep_type == 'bullish' and is_strong_bullish and lower_wick > atr * 0.8 and (not supply_zone or abs(supply_zone - close) > atr * 2.0):
                    return ('BUY', 'ASIA_LIQUIDITY_RUN: Asian Low Swept at London Open', 'METHOD_ASIA_LIQUIDITY_RUN_BUY', 88.5)
                if sweep_type == 'bearish' and is_strong_bearish and upper_wick > atr * 0.8 and (not demand_zone or abs(close - demand_zone) > atr * 2.0):
                    return ('SELL', 'ASIA_LIQUIDITY_RUN: Asian High Swept at London Open', 'METHOD_ASIA_LIQUIDITY_RUN_SELL', 88.5)
        except: pass

        # CATEGORY 2: ICT Order Blocks & FVG
        # 9-10. M5 FVG Instant Rebound
        for fvg in fvgs:
            if fvg['direction'] == 'Bullish' and low <= fvg['high'] and close > fvg['low']:
                if is_bullish_close and lower_wick > atr * 0.5:
                    return ('BUY', 'M5_FVG_INSTANT_REBOUND: Bullish FVG Tapped & Rejected', 'METHOD_M5_FVG_INSTANT_REBOUND_BUY', 87.5)
            if fvg['direction'] == 'Bearish' and high >= fvg['low'] and close < fvg['high']:
                if is_bearish_close and upper_wick > atr * 0.5:
                    return ('SELL', 'M5_FVG_INSTANT_REBOUND: Bearish FVG Tapped & Rejected', 'METHOD_M5_FVG_INSTANT_REBOUND_SELL', 87.5)
        
        # 11-12. Inversion FVG Momentum
        for fvg in fvgs:
            if fvg['direction'] == 'Bearish' and close > fvg['high'] and open_ <= fvg['high']:
                if is_strong_bullish and upper_wick < body_size * 0.5:
                    return ('BUY', 'IFVG_MOMENTUM: Bearish FVG broken upwards', 'METHOD_IFVG_MOMENTUM_BUY', 87.0)
            if fvg['direction'] == 'Bullish' and close < fvg['low'] and open_ >= fvg['low']:
                if is_strong_bearish and lower_wick < body_size * 0.5:
                    return ('SELL', 'IFVG_MOMENTUM: Bullish FVG broken downwards', 'METHOD_IFVG_MOMENTUM_SELL', 87.0)

        # 13-14. Breaker Block
        for ob in obs:
            ob_dir = str(ob.get('type') or ob.get('direction') or '').lower()
            if 'bull' in ob_dir and high >= float(ob.get('low', 0)) and close < float(ob.get('low', 0)): # Broken bull OB retest
                if is_bearish_close and upper_wick > body_size * 2.0 and m15_bias == 'bearish' and h1_bias == 'bearish' and trend == 'EXPANSION' and (not demand_zone or abs(close - demand_zone) > atr * 1.5):
                    return ('SELL', 'BREAKER_BLOCK_SCALP: Broken Bullish OB Retested as Resistance', 'METHOD_BREAKER_BLOCK_SCALP_SELL', 88.0)
            if 'bear' in ob_dir and low <= float(ob.get('high', 0)) and close > float(ob.get('high', 0)): # Broken bear OB retest
                if is_bullish_close and lower_wick > body_size * 2.0 and m15_bias == 'bullish' and h1_bias == 'bullish' and trend == 'EXPANSION' and (not supply_zone or abs(supply_zone - close) > atr * 1.5):
                    return ('BUY', 'BREAKER_BLOCK_SCALP: Broken Bearish OB Retested as Support', 'METHOD_BREAKER_BLOCK_SCALP_BUY', 88.0)

        # 15-16. Order Block Tap
        for ob in obs:
            ob_dir = str(ob.get('type') or ob.get('direction') or '').lower()
            ob_low, ob_high = float(ob.get('low', 0)), float(ob.get('high', 0))
            is_fresh = ob.get('touches', 0) == 0 or ob.get('fresh', True)
            if is_fresh:
                if 'bull' in ob_dir and low <= ob_high and close > ob_low:
                    if is_bullish_close and lower_wick > atr * 1.0 and m15_bias == 'bullish' and h1_bias == 'bullish' and trend == 'EXPANSION':
                        return ('BUY', 'ORDER_BLOCK_TAP: First tap on fresh Bullish OB', 'METHOD_ORDER_BLOCK_TAP_BUY', 88.0)
                if 'bear' in ob_dir and high >= ob_low and close < ob_high:
                    if is_bearish_close and upper_wick > atr * 1.0 and m15_bias == 'bearish' and h1_bias == 'bearish' and trend == 'EXPANSION':
                        return ('SELL', 'ORDER_BLOCK_TAP: First tap on fresh Bearish OB', 'METHOD_ORDER_BLOCK_TAP_SELL', 88.0)

        # CATEGORY 3: Momentum Ignition & Breakouts
        # 17-18. Momentum Marubozu
        if body_size > atr * 2.5 and upper_wick < atr * 0.2 and lower_wick < atr * 0.2 and trend == 'EXPANSION':
            if is_bullish_close and ctx.get('break_bull') and m15_bias == 'bullish' and h1_bias == 'bullish':
                return ('BUY', 'MOMENTUM_MARUBOZU: Giant Bullish breakout no wick', 'METHOD_MOMENTUM_MARUBOZU_BUY', 87.0)
            if is_bearish_close and ctx.get('break_bear') and m15_bias == 'bearish' and h1_bias == 'bearish':
                return ('SELL', 'MOMENTUM_MARUBOZU: Giant Bearish breakout no wick', 'METHOD_MOMENTUM_MARUBOZU_SELL', 87.0)

        # 19-22. Session Open Breakout
        try:
            hour = datetime.now(timezone.utc).hour
            minute = datetime.now(timezone.utc).minute
            is_ny_open = (hour == 13) and minute <= 30
            is_london_open = (hour == 8) and minute <= 30
        except:
            is_ny_open = False
            is_london_open = False
            
        if is_ny_open:
            if ctx.get('break_bull') and is_strong_bullish and trend == 'EXPANSION' and (not supply_zone or abs(supply_zone - close) > atr * 2.0): return ('BUY', 'NY_OPEN_BREAKOUT: NY Breakout Up', 'METHOD_NY_OPEN_BREAKOUT_BUY', 86.5)
            if ctx.get('break_bear') and is_strong_bearish and trend == 'EXPANSION' and (not demand_zone or abs(close - demand_zone) > atr * 2.0): return ('SELL', 'NY_OPEN_BREAKOUT: NY Breakout Down', 'METHOD_NY_OPEN_BREAKOUT_SELL', 86.5)
        elif is_london_open:
            if ctx.get('break_bull') and is_strong_bullish and lower_wick < body_size * 0.5 and m15_bias == 'bullish' and trend == 'EXPANSION' and (not supply_zone or abs(supply_zone - close) > atr * 2.0): return ('BUY', 'LONDON_OPEN_BREAKOUT: London Breakout Up', 'METHOD_LONDON_OPEN_BREAKOUT_BUY', 86.5)
            if ctx.get('break_bear') and is_strong_bearish and upper_wick < body_size * 0.5 and m15_bias == 'bearish' and trend == 'EXPANSION' and (not demand_zone or abs(close - demand_zone) > atr * 2.0): return ('SELL', 'LONDON_OPEN_BREAKOUT: London Breakout Down', 'METHOD_LONDON_OPEN_BREAKOUT_SELL', 86.5)

        # CATEGORY 4: Market Structure & BOS
        # 23-24. Shallow Pullback
        prev_bearish = prev_c['close'] < prev_c['open'] if prev_c else False
        prev_bullish = prev_c['close'] > prev_c['open'] if prev_c else False
        prev_body = abs(prev_c['close'] - prev_c['open']) if prev_c else 0
        if prev_bearish and prev_body < (atr * 0.5) and m15_bias == 'bullish':
            if is_bullish_close and is_strong_bullish and body_size > (prev_body * 2.0) and h1_bias == 'bullish' and trend == 'EXPANSION' and (not supply_zone or abs(supply_zone - close) > atr * 2.0):
                return ('BUY', 'SHALLOW_PULLBACK: Trend Bullish, quick red candle engulfed', 'METHOD_SHALLOW_PULLBACK_BUY', 88.0)
        elif prev_bullish and prev_body < (atr * 0.5) and m15_bias == 'bearish':
            if is_bearish_close and is_strong_bearish and body_size > (prev_body * 2.0) and h1_bias == 'bearish' and trend == 'EXPANSION' and (not demand_zone or abs(close - demand_zone) > atr * 2.0):
                return ('SELL', 'SHALLOW_PULLBACK: Trend Bearish, quick green candle engulfed', 'METHOD_SHALLOW_PULLBACK_SELL', 88.0)

        # 25-26. Continuation BOS
        if ctx.get('break_bull') and m15_bias == 'bullish' and h1_bias == 'bullish' and is_bullish_close and lower_wick > atr * 1.0:
            return ('BUY', 'CONTINUATION_BOS: Bullish BOS confirmed with rejection', 'METHOD_CONTINUATION_BOS_BUY', 87.0)
        if ctx.get('break_bear') and m15_bias == 'bearish' and h1_bias == 'bearish' and is_bearish_close and upper_wick > atr * 1.0:
            return ('SELL', 'CONTINUATION_BOS: Bearish BOS confirmed with rejection', 'METHOD_CONTINUATION_BOS_SELL', 87.0)

        # CATEGORY 5: Exhaustion & Mean Reversion
        # 27-28. Parabolic Exhaustion
        if not ctx.get('choppy'):
            # Simple check if price moved very fast
            if low < atr * 3.0 and is_bullish_close and lower_wick > body_size * 2.0 and lower_wick > atr * 1.5:
                return ('BUY', 'PARABOLIC_EXHAUSTION: Huge drop exhausted with massive wick', 'METHOD_PARABOLIC_EXHAUSTION_BUY', 85.0)
            if high > atr * 3.0 and is_bearish_close and upper_wick > body_size * 2.0 and upper_wick > atr * 1.5:
                return ('SELL', 'PARABOLIC_EXHAUSTION: Huge pump exhausted with massive wick', 'METHOD_PARABOLIC_EXHAUSTION_SELL', 85.0)

        # 29-30. News Spike Fade (Using ATR burst)
        if atr > 3.0 and body_size < atr * 0.3:
            if upper_wick > atr * 1.5 and is_bearish_close:
                return ('SELL', 'NEWS_SPIKE_FADE: Massive upper wick fade during volatility', 'METHOD_NEWS_SPIKE_FADE_SELL', 84.0)
            if lower_wick > atr * 1.5 and is_bullish_close:
                return ('BUY', 'NEWS_SPIKE_FADE: Massive lower wick fade during volatility', 'METHOD_NEWS_SPIKE_FADE_BUY', 84.0)

        return None

    def _decide(self, ctx: Dict[str, Any]) -> Tuple[str, str, str, float]:
        price = ctx.get('price', 0)
        close = ctx.get('last_close', 0)
        open_ = ctx.get('last_open', 0)
        high = ctx.get('last_high', 0)
        low = ctx.get('last_low', 0)
        momentum = ctx.get('momentum')
        body_ratio = float(ctx.get('body_ratio') or 0)
        m15_bias = ctx.get('m15_bias')
        h1_bias = ctx.get('h1_bias')
        fvgs = ctx.get('fvgs', [])
        atr = ctx.get('atr', 2.0)
        
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        body_size = max(body_top - body_bottom, 0.01)

        struct = ctx.get('structure', {})
        sweep_type = struct.get('sweep_type')

        # 1. Sniper Priority: V7 user methods (CRT D1/H4 Sweep) are highly accurate
        user_method_match = self._user_method_suite(ctx)
        if user_method_match:
            return user_method_match

        rr2_sell_match = self._rr2_group_sell(ctx)
        if rr2_sell_match:
            return rr2_sell_match

        # 2. New 10 Methods Execution (contains POI_REBOUND_OB_SELL etc)
        new_methods_match = self._new_user_methods(ctx)
        if new_methods_match:
            return new_methods_match

        # 3. Antigravity Experimental Methods (Injected by Autonomous Analysis)
        ag_match = self._antigravity_experimental_method(ctx)
        if ag_match:
            return ag_match
        # 4. Aggressive 30 Methods (Fase 2)
        aggro_match = self._aggressive_30_methods(ctx)
        if aggro_match:
            return aggro_match


        # 0. High-winrate sweep scalp first. In high_wr_only mode, skip all weaker legacy/sandbox methods.
        high_wr_match = self._high_wr_method_suite(ctx)
        if high_wr_match:
            return high_wr_match

        # TURNED OFF HIGH_WR_ONLY TO UNLOCK MORE TRADES
        high_wr_only = False
        if high_wr_only:
            return 'NO_TRADE', f'HIGH_WR_MODE: menunggu setup {self.signal_timeframe} valid dengan bias M15 + H1', 'WAITING_HIGH_WR', 0

        # 0b. Strict backtested sweep method fallback
        strict_sweep_match = self._strict_m15_sweep_reclaim(ctx)
        if strict_sweep_match and self._main_method_allowed(strict_sweep_match[2]):
            return strict_sweep_match

        # 1. Check Sandbox rules after strict filter
        sandbox_match = self._evaluate_sandbox_rules(ctx)
        if sandbox_match and self._main_method_allowed(sandbox_match[2]):
            return sandbox_match

        # 2. Check Dynamic DB Rules
        dynamic_match = self._evaluate_dynamic_rules(ctx)
        if dynamic_match and self._main_method_allowed(dynamic_match[2]):
            return dynamic_match
        break_type = struct.get('break_type')
        reclaim_valid = struct.get('reclaim_valid')
        sweep_type = struct.get('sweep_type')
        is_extreme = struct.get('is_extreme_volatility', False)

        candidates = []

        # [NATIVE PRICE ACTION PATTERNS]
        candles = ctx.get('candles', [])
        if len(candles) >= 5:
            c1 = candles[-1]
            c2 = candles[-2]
            
            c1_body = max(abs(c1['open'] - c1['close']), 0.01)
            c1_upper = c1['high'] - max(c1['open'], c1['close'])
            c1_lower = min(c1['open'], c1['close']) - c1['low']
            
            c2_body = max(abs(c2['open'] - c2['close']), 0.01)
            c2_upper = c2['high'] - max(c2['open'], c2['close'])
            c2_lower = min(c2['open'], c2['close']) - c2['low']

            # Context-Aware Variables
            c2_is_bearish = c2['close'] < c2['open']
            c2_is_bullish = c2['close'] > c2['open']
            choppy = ctx.get('choppy', False)

            # 1. Hammer / Pin Bar
            if c1_lower >= c1_body * 2 and c1_upper <= c1_body * 0.5 and c1_lower > (atr * 0.5):
                if c2_is_bearish:
                    candidates.append(('BUY', 'PATTERN: Hammer / Bullish Pin Bar', 'METHOD_PATTERN_HAMMER', 88.0))
            
            # 2. Shooting Star
            if c1_upper >= c1_body * 2 and c1_lower <= c1_body * 0.5 and c1_upper > (atr * 0.5):
                h1_bias = ctx.get('h1_bias')
                if c2_is_bullish and h1_bias != 'bullish':
                    candidates.append(('SELL', 'PATTERN: Shooting Star / Bearish Pin Bar', 'METHOD_PATTERN_SHOOTING_STAR', 88.0))
                
            # 3. Exhaustion Upper Wick
            if c2_upper >= c2_body * 1.5 and c1['close'] < c1['open'] and c2_upper > (atr * 0.5):
                if c2_is_bullish:
                    candidates.append(('SELL', 'PATTERN: Exhaustion Upper Wick & Bearish Close', 'METHOD_PATTERN_EXHAUST_UP', 86.0))
                
            # 4. Exhaustion Lower Wick
            if c2_lower >= c2_body * 1.5 and c1['close'] > c1['open'] and c2_lower > (atr * 0.5):
                if c2_is_bearish:
                    candidates.append(('BUY', 'PATTERN: Exhaustion Lower Wick & Bullish Close', 'METHOD_PATTERN_EXHAUST_DOWN', 86.0))
                
            # 5. Body Compression Breakout
            c3 = candles[-3]
            b1, b2, b3 = c1_body, c2_body, abs(c3['open']-c3['close'])
            if b2 < atr * 0.5 and b3 < atr * 0.5 and b1 > atr * 0.8:
                if not choppy:
                    if c1['close'] > c1['open']:
                        candidates.append(('BUY', 'PATTERN: Bullish Compression Breakout', 'METHOD_PATTERN_COMPRESS_BULL', 85.0))
                    elif c1['close'] < c1['open']:
                        candidates.append(('SELL', 'PATTERN: Bearish Compression Breakout', 'METHOD_PATTERN_COMPRESS_BEAR', 85.0))

        # [Model 1] Turtle Soup / Liquidity Sweep Reclaim
        # Swept a high/low but immediately reclaimed the level (Fakeout)
        if sweep_type == 'bearish' and reclaim_valid:
            h1_bias = ctx.get('h1_bias')
            h4_bias = ctx.get('h4_bias')
            # ATM: Strict H1/H4 alignment
            if h1_bias in ['bearish', 'neutral'] or h4_bias == 'bearish':
                if c1_body > (atr * 0.5):
                    candidates.append(('SELL', 'ICT TURTLE SOUP: Bearish Liquidity Sweep & Reclaim', 'METHOD_ICT_TURTLE_SOUP_SELL', 88.0))
        elif sweep_type == 'bullish' and reclaim_valid:
            h1_bias = ctx.get('h1_bias')
            h4_bias = ctx.get('h4_bias')
            # ATM: Strict H1/H4 alignment
            if h1_bias in ['bullish', 'neutral'] or h4_bias == 'bullish':
                if c1_body > (atr * 0.5):
                    candidates.append(('BUY', 'ICT TURTLE SOUP: Bullish Liquidity Sweep & Reclaim', 'METHOD_ICT_TURTLE_SOUP_BUY', 88.0))

        # [NEW] Momentum Ride / Falling Knife Catcher
        # Sell hard when dropping hard and breaking support, Buy hard when breaking resistance
        h1_bias = ctx.get('h1_bias')
        h4_bias = ctx.get('h4_bias')
        prev_high_20 = float(ctx.get('prev_high_20') or ctx.get('prev_high') or 0)
        prev_low_20 = float(ctx.get('prev_low_20') or ctx.get('prev_low') or 0)
        if c1_body > (atr * 1.5) and c2_body > (atr * 1.0):
            # Strong momentum over 2 candles
            if c1['close'] < c1['open'] and c2['close'] < c2['open']:
                # Heavy dump
                if close < prev_low_20 and h1_bias == 'bearish' and h4_bias == 'bearish':
                    candidates.append(('SELL', 'MOMENTUM RIDE: Strong H1/H4 Bearish Dump', 'METHOD_MOMENTUM_RIDE_SELL', 90.0))
            elif c1['close'] > c1['open'] and c2['close'] > c2['open']:
                # Heavy pump
                if close > prev_high_20 and h1_bias == 'bullish' and h4_bias == 'bullish':
                    candidates.append(('BUY', 'MOMENTUM RIDE: Strong H1/H4 Bullish Pump', 'METHOD_MOMENTUM_RIDE_BUY', 90.0))

        # [NEW] NY Killzone Reversal
        # Reversal keras di sesi NY (13:00 - 17:00 UTC)
        open_time_str = ctx.get('open_time', '')
        try:
            hour = int(open_time_str[11:13]) if len(open_time_str) >= 13 else -1
            if 13 <= hour <= 17:
                if sweep_type == 'bullish' and reclaim_valid and c1_body > atr * 0.8:
                    candidates.append(('BUY', 'NY KILLZONE REVERSAL: Strong Bullish Rejection at NY Open', 'METHOD_NY_KILLZONE_REVERSAL_BUY', 92.0))
                elif sweep_type == 'bearish' and reclaim_valid and c1_body > atr * 0.8:
                    candidates.append(('SELL', 'NY KILLZONE REVERSAL: Strong Bearish Rejection at NY Open', 'METHOD_NY_KILLZONE_REVERSAL_SELL', 92.0))
        except Exception:
            pass

        # [NEW] London Killzone Reversal
        # Reversal keras di sesi London Open (07:00 - 10:00 UTC)
        try:
            if 7 <= hour <= 10:
                if sweep_type == 'bullish' and reclaim_valid and c1_body > atr * 0.7:
                    candidates.append(('BUY', 'LONDON KILLZONE REVERSAL: Bullish Rejection at London Open', 'METHOD_LONDON_KILLZONE_REVERSAL_BUY', 91.0))
                elif sweep_type == 'bearish' and reclaim_valid and c1_body > atr * 0.7:
                    candidates.append(('SELL', 'LONDON KILLZONE REVERSAL: Bearish Rejection at London Open', 'METHOD_LONDON_KILLZONE_REVERSAL_SELL', 91.0))
        except Exception:
            pass

        # [NEW] Asian Session Trap
        # Jebakan false breakout di sesi Asia (23:00 - 02:00 UTC) — likuiditas rendah
        try:
            if hour >= 23 or hour <= 2:
                if sweep_type == 'bullish' and reclaim_valid and upper_wick > body_size * 2.0 and c1_body < atr * 0.5:
                    candidates.append(('BUY', 'ASIAN TRAP: False Bearish Sweep reversed in low-liquidity session', 'METHOD_ASIAN_TRAP_BUY', 85.0))
                elif sweep_type == 'bearish' and reclaim_valid and lower_wick > body_size * 2.0 and c1_body < atr * 0.5:
                    candidates.append(('SELL', 'ASIAN TRAP: False Bullish Sweep reversed in low-liquidity session', 'METHOD_ASIAN_TRAP_SELL', 85.0))
        except Exception:
            pass

        # [Model 2] ICT 2022 Mentorship Model
        # Sweep -> MSS -> FVG Retest
        for fvg in fvgs:
            if fvg['direction'] == 'Bearish' and high >= fvg['low'] and close < fvg['high']:
                # Price is inside Bearish FVG and rejected
                if upper_wick > body_size * 1.5:
                    candidates.append(('SELL', 'ICT UNICORN / FVG: Bearish FVG Retest', 'METHOD_ICT_UNICORN_SELL', 80.0))

            elif fvg['direction'] == 'Bullish' and low <= fvg['high'] and close > fvg['low']:
                # Price is inside Bullish FVG and rejected
                if lower_wick > body_size * 1.5:
                    candidates.append(('BUY', 'ICT UNICORN / FVG: Bullish FVG Retest', 'METHOD_ICT_UNICORN_BUY', 80.0))

        # [Model 3] AMD (Accumulation, Manipulation, Distribution)
        # If market was choppy (Accumulation), then Swept (Manipulation), we enter on reversal (Distribution)
        if struct.get('choppy') and sweep_type == 'bearish' and upper_wick > body_size * 2:
            candidates.append(('SELL', 'ICT AMD: Choppy -> Bearish Sweep -> Distribution', 'METHOD_ICT_AMD_SELL', 90.0))
        elif struct.get('choppy') and sweep_type == 'bullish' and lower_wick > body_size * 2:
            candidates.append(('BUY', 'ICT AMD: Choppy -> Bullish Sweep -> Distribution', 'METHOD_ICT_AMD_BUY', 90.0))

        if candidates:
            candidates = [c for c in candidates if not self._method_blocked(c[2]) and self._main_method_allowed(c[2])]
            if candidates:
                candidates.sort(key=lambda x: x[3], reverse=True)
                return candidates[0]

        return 'NO_TRADE', 'Belum ada metode yang terpicu', 'WAITING', 0

    def _method_lookback(self, pattern_key: str) -> int:
        key = str(pattern_key or '')
        import re
        m = re.search(r'_(?:SWEEP|BREAK)_(\d+)', key)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        if 'SWEEP_32' in key:
            return 32
        if 'BREAK_20' in key or 'M15_SWEEP' in key:
            return 20
        return 12

    def _pending_reference_level(self, direction: str, ctx: Dict[str, Any], pattern_key: str) -> Optional[float]:
        candles = ctx.get('candles') or []
        lookback = self._method_lookback(pattern_key)
        if len(candles) <= lookback:
            return None
        previous = candles[-lookback-1:-1]
        if len(previous) < lookback:
            return None
        prev_high = max(_cval(c, 'high') for c in previous)
        prev_low = min(_cval(c, 'low') for c in previous)
        key = str(pattern_key or '')
        if key.startswith('METHOD_CRT_H4'):
            return ctx.get('crt_h4_level')
        if key.startswith('METHOD_CRT_D1'):
            return ctx.get('crt_d1_level')
        if key.startswith('METHOD_H1_BREAK'):
            return ctx.get('h1_break_level')
        if 'BREAK' in key:
            return prev_high if direction == 'BUY' else prev_low
        return prev_low if direction == 'BUY' else prev_high

    def _pending_order_plan(self, direction: str, price: float, ctx: Dict[str, Any], pattern_key: str) -> Dict[str, Any]:
        adaptive_cfg = (self.config or {}).get('adaptive_brain', {})
        pending_cfg = adaptive_cfg.get('pending_orders', {}) or {}
        if not bool(pending_cfg.get('enabled', True)):
            return {
                'entry_type': 'MARKET',
                'pending_price': None,
                'pending_expire_time': None,
                'status': 'ACTIVE',
                'reference_level': None,
            }
        pending_allowed_prefixes = (
            'METHOD_HIGH_WR_M15_SWEEP_SCALP', 'METHOD_HW_SWEEP_', 'METHOD_HW_BREAK_',
            'METHOD_M1_', 'METHOD_M5_', 'METHOD_CRT_H4', 'METHOD_CRT_D1', 'METHOD_H1_BREAK'
        )
        if not str(pattern_key or '').startswith(pending_allowed_prefixes):
            return {
                'entry_type': 'MARKET',
                'pending_price': None,
                'pending_expire_time': None,
                'status': 'ACTIVE',
                'reference_level': None,
                'averaging_allowed': False,
            }
        reference = self._pending_reference_level(direction, ctx, pattern_key)
        if reference is None:
            return {
                'entry_type': 'MARKET',
                'pending_price': None,
                'pending_expire_time': None,
                'status': 'ACTIVE',
                'reference_level': None,
            }
        method_cfg = self._user_method_cfg()
        key = str(pattern_key or '')
        user_cfg = {}
        if key.startswith('METHOD_CRT_H4'):
            user_cfg = method_cfg.get('crt_h4', {}) or {}
        elif key.startswith('METHOD_CRT_D1'):
            user_cfg = method_cfg.get('crt_d1', {}) or {}
        elif key.startswith('METHOD_H1_BREAK'):
            user_cfg = method_cfg.get('h1_break', {}) or {}

        if key.startswith(('METHOD_CRT_H4', 'METHOD_CRT_D1', 'METHOD_H1_BREAK')):
            expiry_minutes = int(user_cfg.get('expiry_minutes', pending_cfg.get('expiry_minutes', 60)))
            averaging_allowed = bool(user_cfg.get('averaging', not key.startswith('METHOD_H1_BREAK')))
            if key.startswith('METHOD_H1_BREAK'):
                buffer_points = float(user_cfg.get('entry_buffer_points', user_cfg.get('buffer_min_points', 5.0)))
                if direction == 'BUY':
                    pending_price = float(reference) + buffer_points
                    if pending_price >= float(price):
                        pending_price = float(reference)
                    entry_type = 'BUY_LIMIT'
                else:
                    pending_price = float(reference) - buffer_points
                    if pending_price <= float(price):
                        pending_price = float(reference)
                    entry_type = 'SELL_LIMIT'
            else:
                pending_price = float(reference)
                entry_type = 'BUY_LIMIT' if direction == 'BUY' else 'SELL_LIMIT'

            expire_time = None
            try:
                base_dt = self._parse_candle_dt(ctx.get('last_time')) or datetime.now(timezone.utc)
                expire_time = (base_dt + timedelta(minutes=expiry_minutes)).isoformat()
            except Exception:
                expire_time = None
            return {
                'entry_type': entry_type,
                'pending_price': round(float(pending_price), 3),
                'pending_expire_time': expire_time,
                'status': 'PENDING_ENTRY',
                'reference_level': round(float(reference), 3),
                'averaging_allowed': averaging_allowed,
            }

        min_pullback = float(pending_cfg.get('min_pullback_points', 1.0))
        max_pullback = float(pending_cfg.get('max_pullback_points', 3.0))
        pullback_factor = float(pending_cfg.get('pullback_factor', 0.45))
        expiry_minutes = int(pending_cfg.get('expiry_minutes', 60))
        offset = max(min_pullback, min(max_pullback, abs(float(price) - float(reference)) * pullback_factor))
        if direction == 'BUY':
            pending_price = float(price) - offset
            entry_type = 'BUY_LIMIT'
        else:
            pending_price = float(price) + offset
            entry_type = 'SELL_LIMIT'
        expire_time = None
        try:
            raw_time = ctx.get('last_time')
            base_dt = None
            if raw_time:
                txt = str(raw_time).replace('Z', '+00:00')
                try:
                    base_dt = datetime.fromisoformat(txt)
                except Exception:
                    base_dt = None
            if base_dt is None:
                base_dt = datetime.now(timezone.utc)
            if base_dt.tzinfo is None:
                base_dt = base_dt.replace(tzinfo=timezone.utc)
            expire_time = (base_dt + timedelta(minutes=expiry_minutes)).isoformat()
        except Exception:
            expire_time = None
        return {
            'entry_type': entry_type,
            'pending_price': round(pending_price, 3),
            'pending_expire_time': expire_time,
            'status': 'PENDING_ENTRY',
            'reference_level': round(float(reference), 3),
            'averaging_allowed': True,
        }

    def _averaging_plan(self, direction: str, base_entry: float, order_plan: Dict[str, Any]) -> Dict[str, Any]:
        adaptive_cfg = (self.config or {}).get('adaptive_brain', {})
        avg_cfg = adaptive_cfg.get('averaging', {}) or {}
        if not bool(avg_cfg.get('enabled', False)):
            return {
                'enabled': False,
                'layers': [],
                'average_entry': round(float(base_entry), 3),
                'sl': None,
                'tp1': None,
                'tp2': None,
            }
        if order_plan.get('averaging_allowed') is False:
            return {
                'enabled': False,
                'layers': [],
                'average_entry': round(float(base_entry), 3),
                'sl': None,
                'tp1': None,
                'tp2': None,
            }
        if order_plan.get('entry_type') not in ('BUY_LIMIT', 'SELL_LIMIT'):
            return {
                'enabled': False,
                'layers': [],
                'average_entry': round(float(base_entry), 3),
                'sl': None,
                'tp1': None,
                'tp2': None,
            }

        max_layers = max(1, min(3, int(avg_cfg.get('max_layers', 3))))
        spacing = float(avg_cfg.get('layer_spacing_points', 2.0))
        sl_buffer = float(avg_cfg.get('sl_buffer_after_last_layer_points', 4.0))
        tp1_dist = float(avg_cfg.get('tp1_from_average_points', 1.5))
        tp2_dist = float(avg_cfg.get('tp2_from_average_points', 3.0))

        if direction == 'BUY':
            prices = [float(base_entry) - spacing * i for i in range(max_layers)]
            sl = prices[-1] - sl_buffer
            average_entry = sum(prices) / len(prices)
            tp1 = average_entry + tp1_dist
            tp2 = average_entry + tp2_dist
        else:
            prices = [float(base_entry) + spacing * i for i in range(max_layers)]
            sl = prices[-1] + sl_buffer
            average_entry = sum(prices) / len(prices)
            tp1 = average_entry - tp1_dist
            tp2 = average_entry - tp2_dist

        layers = []
        for idx, price in enumerate(prices, 1):
            layers.append({
                'layer': idx,
                'price': round(price, 3),
                'lot': 'same_lot',
            })

        return {
            'enabled': True,
            'layers': layers,
            'average_entry': round(average_entry, 3),
            'sl': round(sl, 3),
            'tp1': round(tp1, 3),
            'tp2': round(tp2, 3),
            'max_layers': max_layers,
            'spacing_points': spacing,
            'max_total_risk_percent': float(avg_cfg.get('max_total_risk_percent', 1.0)),
            'rule': 'controlled_averaging_no_martingale_same_lot',
        }


    def _choch_reversal_sell_sl_plan(self, price: float, ctx: Dict[str, Any]) -> Tuple[float, float, float]:
        """SL khusus METHOD_CHOCH_REVERSAL_SELL.

        Hanya untuk METHOD_CHOCH_REVERSAL_SELL.
        SL dibuat di atas swing/sweep high + ATR buffer.
        """
        struct = ctx.get('structure', {}) or {}
        atr = max(float(ctx.get('atr') or 2.0), 0.50)

        last_high = float(ctx.get('last_high') or price)
        prev_high = float(ctx.get('prev_high') or last_high)

        candidates = [last_high, prev_high]

        for key in ('nearest_resistance', 'liquidity_above', 'break_level', 'sweep_extreme'):
            value = struct.get(key)
            if value is not None:
                try:
                    candidates.append(float(value))
                except Exception:
                    pass

        inv_level = struct.get('invalidation_level')
        inv_label = str(struct.get('invalidation_label') or '').lower()
        if inv_level is not None and ('lower high' in inv_label or 'high' in inv_label):
            try:
                candidates.append(float(inv_level))
            except Exception:
                pass

        structure_high = max(candidates) if candidates else last_high
        buffer_points = max(atr * 0.55, 1.50)

        raw_sl = structure_high + buffer_points
        min_sl_dist = max(atr * 1.80, 8.00)

        method_cfg = (
            ((self.config or {}).get('adaptive_brain', {}) or {})
            .get('method_risk_overrides', {}) or {}
        ).get('METHOD_CHOCH_REVERSAL_SELL', {}) or {}

        max_sl_dist = float(method_cfg.get('max_sl_points', 14.0))
        sl_dist = max(raw_sl - float(price), min_sl_dist)
        sl_dist = min(sl_dist, max_sl_dist)

        sl = float(price) + sl_dist
        tp1 = float(price) - (sl_dist * self.tp1_rr)
        tp2 = float(price) - (sl_dist * self.tp2_rr)

        return round(sl, 3), round(tp1, 3), round(tp2, 3)

    def _build_signal(self, direction: str, price: float, ctx: Dict[str, Any], confidence: float,
                      reason: str, pattern_key: str, pattern: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Structural SL and TP based on ICT DOL
        struct = ctx.get('structure', {})
        atr = ctx.get('atr', 2.0)
        sl = price
        tp1 = None
        tp2 = price
        scalp_exit_cfg = ((self.config or {}).get('adaptive_brain', {}).get('pattern_ict_scalp_exit', {}) or {})
        pattern_ict_scalp = (
            bool(scalp_exit_cfg.get('enabled', True))
            and pattern_key.startswith(('METHOD_PATTERN_', 'METHOD_ICT_TURTLE_SOUP_', 'METHOD_ICT_UNICORN_', 'METHOD_ICT_AMD_'))
        )

        if pattern_ict_scalp:
            sl_dist = float(scalp_exit_cfg.get('sl_points', 5.0))
            tp1_dist = sl_dist * self.tp1_rr
            tp2_dist = sl_dist * self.tp2_rr
            if direction == 'BUY':
                sl = price - sl_dist
                tp1 = price + tp1_dist
                tp2 = price + tp2_dist
            else:
                sl = price + sl_dist
                tp1 = price - tp1_dist
                tp2 = price - tp2_dist
        elif pattern_key.startswith(('METHOD_HIGH_WR_M15_SWEEP_SCALP', 'METHOD_HW_SWEEP_', 'METHOD_HW_BREAK_', 'METHOD_M1_', 'METHOD_M5_', 'METHOD_CRT_H4', 'METHOD_CRT_D1', 'METHOD_H1_BREAK')):
            if self.signal_timeframe == 'M1':
                sl_dist = 6.0
            else:
                sl_dist = 8.0
            tp1_dist = min(sl_dist * self.tp1_rr, 5.0)  # Capped at 5 points
            tp2_dist = min(sl_dist * self.tp2_rr, 10.0) # Capped at 10 points
            if direction == 'BUY':
                sl = price - sl_dist
                tp1 = price + tp1_dist
                tp2 = price + tp2_dist
            else:
                sl = price + sl_dist
                tp1 = price - tp1_dist
                tp2 = price - tp2_dist
        elif pattern_key.startswith('METHOD_MOMENTUM_RIDE'):
            # Momentum Ride allows up to 1:4 RR
            sl_dist = 6.0
            tp1_dist = sl_dist * 2.0
            tp2_dist = sl_dist * 4.0
            if direction == 'BUY':
                sl = price - sl_dist
                tp1 = price + tp1_dist
                tp2 = price + tp2_dist
            else:
                sl = price + sl_dist
                tp1 = price - tp1_dist
                tp2 = price - tp2_dist
        elif pattern_key.startswith('METHOD_STRICT_M15_SWEEP_RECLAIM'):
            sl_dist = 8.0
            tp1_dist = min(sl_dist * self.tp1_rr, 5.0)
            tp2_dist = min(sl_dist * self.tp2_rr, 10.0)
            if direction == 'BUY':
                sl = price - sl_dist
                tp1 = price + tp1_dist
                tp2 = price + tp2_dist
            else:
                sl = price + sl_dist
                tp1 = price - tp1_dist
                tp2 = price - tp2_dist
        elif pattern_key == 'RR2_GROUP_SELL':
            sl_dist = 8.0
            tp1_dist = min(sl_dist * self.tp1_rr, 5.0)
            tp2_dist = min(sl_dist * self.tp2_rr, 10.0)
            sl = price + sl_dist
            tp1 = price - tp1_dist
            tp2 = price - tp2_dist
        elif pattern_key.startswith(('METHOD_BREAK_AND_RETEST', 'METHOD_DRAW_ON_LIQUIDITY', 'METHOD_FOLLOW_THE_TREND', 'METHOD_REVERSAL')):
            # Aggressive scalping methods use elastic ATR-based SL but fast TP (1:1 & 1:1.5 RR)
            sl_dist = max(atr * 1.5, 6.0)
            tp1_dist = sl_dist * 1.0
            tp2_dist = sl_dist * 1.5
            if direction == 'BUY':
                sl = price - sl_dist
                tp1 = price + tp1_dist
                tp2 = price + tp2_dist
            else:
                sl = price + sl_dist
                tp1 = price - tp1_dist
                tp2 = price - tp2_dist
        elif pattern_key == 'METHOD_CHOCH_REVERSAL_SELL':
            sl, tp1, tp2 = self._choch_reversal_sell_sl_plan(price, ctx)

        elif direction == 'BUY':
            # SL is nearest support or swing low
            support = struct.get('nearest_support') or ctx.get('prev_low') or (price - 8.0)
            sl_dist = price - support
            # ATR Rubber Band SL for Patterns
            if 'PATTERN' in reason:
                sl_dist = max(atr * 1.5, 6.0) # SL is 1.5x ATR, min 60 pips
            else:
                # Enforce 6.0 to 15.0 constraints for Pure ICT
                if sl_dist > 15.0:
                    return None  # ABORT, SL too wide
            sl_dist = max(sl_dist, 6.0)  # Min 60 pips
            sl = price - sl_dist

            # TP is Draw On Liquidity (Liquidity Above or Resistance)
            dol = struct.get('liquidity_above') or struct.get('nearest_resistance') or (price + 8.0)
            tp_dist = dol - price
            if 'PATTERN' in reason:
                tp_dist = sl_dist * 1.5 # Dynamic TP based on SL (1:1.5 RR)
            else:
                # Enforce 8.0 to 30.0 constraints
                tp_dist = max(tp_dist, 8.0)  # Min 80 pips
                tp_dist = min(tp_dist, 30.0) # Max 300 pips
                
            tp2 = price + tp_dist

        else: # SELL
            # SL is nearest resistance or swing high
            resistance = struct.get('nearest_resistance') or ctx.get('prev_high') or (price + 8.0)
            sl_dist = resistance - price
            # ATR Rubber Band SL for Patterns
            if 'PATTERN' in reason:
                sl_dist = max(atr * 1.5, 6.0)
            else:
                if sl_dist > 15.0:
                    return None  # ABORT, SL too wide
            sl_dist = max(sl_dist, 6.0)
            sl = price + sl_dist

            # TP is Draw On Liquidity (Liquidity Below or Support)
            dol = struct.get('liquidity_below') or struct.get('nearest_support') or (price - 8.0)
            tp_dist = price - dol
            if 'PATTERN' in reason:
                tp_dist = sl_dist * 1.5
            else:
                tp_dist = max(tp_dist, 8.0)
                tp_dist = min(tp_dist, 30.0)
                
            tp2 = price - tp_dist

        order_plan = self._pending_order_plan(direction, price, ctx, pattern_key)
        planned_entry = float(order_plan.get('pending_price') or price)
        avg_plan = self._averaging_plan(direction, planned_entry, order_plan)
        if avg_plan.get('enabled'):
            layer_prices = [float(x.get('price')) for x in avg_plan.get('layers', []) if x.get('price') is not None]
            if layer_prices:
                entry_low = min(layer_prices) - 0.15
                entry_high = max(layer_prices) + 0.15
            else:
                entry_low = planned_entry - 0.15
                entry_high = planned_entry + 0.15
            sl = float(avg_plan.get('sl'))
            tp1 = float(avg_plan.get('tp1'))
            tp2 = float(avg_plan.get('tp2'))
        else:
            if order_plan.get('entry_type') in ('BUY_LIMIT', 'SELL_LIMIT'):
                if pattern_key.startswith('METHOD_H1_BREAK'):
                    ref = float(order_plan.get('reference_level') or planned_entry)
                    buffer_points = float(self._user_method_cfg().get('h1_break', {}).get('sl_buffer_points', 5.0))
                    if direction == 'BUY':
                        sl = ref - buffer_points
                        risk = max(planned_entry - sl, 1.0)
                        tp1 = planned_entry + risk
                        tp2 = planned_entry + risk * 2.0
                    else:
                        sl = ref + buffer_points
                        risk = max(sl - planned_entry, 1.0)
                        tp1 = planned_entry - risk
                        tp2 = planned_entry - risk * 2.0
                elif pattern_key.startswith(('METHOD_CRT_H4', 'METHOD_CRT_D1')):
                    ref = float(order_plan.get('reference_level') or planned_entry)
                    buffer_points = 5.0
                    if direction == 'BUY':
                        sl = ref - buffer_points
                        tp1 = planned_entry + 5.0
                        tp2 = planned_entry + 10.0
                    else:
                        sl = ref + buffer_points
                        tp1 = planned_entry - 5.0
                        tp2 = planned_entry - 10.0
                else:
                    if self.signal_timeframe == 'M1':
                        sl_dist = 6.0
                    else:
                        sl_dist = 8.0
                    tp1_dist = min(sl_dist * self.tp1_rr, 5.0)
                    tp2_dist = min(sl_dist * self.tp2_rr, 10.0)
                    if direction == 'BUY':
                        sl = planned_entry - sl_dist
                        tp1 = planned_entry + tp1_dist
                        tp2 = planned_entry + tp2_dist
                    else:
                        sl = planned_entry + sl_dist
                        tp1 = planned_entry - tp1_dist
                        tp2 = planned_entry - tp2_dist
            entry_pad = 0.15 if order_plan.get('entry_type') in ('BUY_LIMIT', 'SELL_LIMIT') else 0.5
            entry_low = planned_entry - entry_pad
            entry_high = planned_entry + entry_pad
        invalid = sl
        if tp1 is None:
            # Fix abnormal RR: Calculate TP1 (1R protect) instead of copying TP2
            actual_sl_dist = abs(planned_entry - sl)
            tp1_dist = min(actual_sl_dist * self.tp1_rr, 5.0)
            if direction == 'BUY':
                tp1 = planned_entry + tp1_dist
                if tp1 >= tp2:
                    tp1 = planned_entry + (abs(tp2 - planned_entry) / 2.0)
            else:
                tp1 = planned_entry - tp1_dist
                if tp1 <= tp2:
                    tp1 = planned_entry - (abs(planned_entry - tp2) / 2.0)
        tp3 = None

        learned_note = ''
        wins = int(pattern.get('wins') or 0)
        losses = int(pattern.get('losses') or 0)
        score = float(pattern.get('score') or 0)
        if wins or losses or score:
            learned_note = f" | Memory: {wins}W/{losses}L, score {score:.0f}."

        method_tf = self.signal_timeframe
        method_class = self.signal_class
        if pattern_key.startswith('METHOD_CRT_H4'):
            method_tf, method_class = 'H4', 'CRT_H4_PENDING'
        elif pattern_key.startswith('METHOD_CRT_D1'):
            method_tf, method_class = 'D1', 'CRT_D1_PENDING'
        elif pattern_key.startswith('METHOD_H1_BREAK'):
            method_tf, method_class = 'H1', 'H1_BREAK_PENDING'

        return {
            'symbol': self.symbol,
            'direction': direction,
            'entry_low': round(entry_low, 3),
            'entry_high': round(entry_high, 3),
            'sl': round(sl, 3),
            'tp1': round(tp1, 3),
            'tp2': round(tp2, 3),
            'tp3': None,
            'invalid_level': round(invalid, 3),
            'confidence': round(confidence, 1),
            'reason': reason + learned_note,
            'status': order_plan.get('status', 'ACTIVE'),
            'signal_timeframe': method_tf,
            'signal_class': method_class,
            'entry_type': order_plan.get('entry_type', 'MARKET'),
            'pending_price': order_plan.get('pending_price'),
            'pending_expire_time': order_plan.get('pending_expire_time'),
            'reference_level': order_plan.get('reference_level'),
            'averaging_enabled': bool(avg_plan.get('enabled')),
            'averaging_plan': avg_plan if avg_plan.get('enabled') else None,
            'average_entry': avg_plan.get('average_entry') if avg_plan.get('enabled') else round(planned_entry, 3),
            'current_price': price,
            'pattern_key': pattern_key,
            'source': 'ADAPTIVE_BRAIN',
            'brain_context': {
                'prev_high': ctx.get('prev_high'),
                'prev_low': ctx.get('prev_low'),
                'atr': ctx.get('atr'),
                'momentum': ctx.get('momentum'),
                'choppy': ctx.get('choppy'),
                'm15_bias': ctx.get('m15_bias'),
                'h1_bias': ctx.get('h1_bias'),
                'signal_timeframe': method_tf,
                'signal_class': method_class,
                'h1_break': ctx.get('h1_break'),
                'crt_h4_level': ctx.get('crt_h4_level'),
                'crt_d1_level': ctx.get('crt_d1_level'),
                'intraday_context': ctx.get('intraday_context'),
            }
        }

    def _atr(self, candles: List[Dict[str, Any]], period: int = 14) -> float:
        if len(candles) < 2:
            return 1.5
        trs = []
        recent = candles[-period:]
        prev_close = _cval(candles[-period - 1], 'close') if len(candles) > period else _cval(candles[0], 'close')
        for c in recent:
            high = _cval(c, 'high')
            low = _cval(c, 'low')
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(max(tr, 0.01))
            prev_close = _cval(c, 'close')
        return mean(trs) if trs else 1.5

    def _bias(self, candles: List[Dict[str, Any]]) -> str:
        if not candles or len(candles) < 5:
            return 'unknown'
        closes = [_cval(c, 'close') for c in candles[-5:]]
        if closes[-1] > closes[0]:
            return 'bullish'
        if closes[-1] < closes[0]:
            return 'bearish'
        return 'flat'

    def _is_choppy(self, candles: List[Dict[str, Any]]) -> bool:
        if len(candles) < 8:
            return False
        recent = candles[-8:]
        ranges = [max(_cval(c, 'high') - _cval(c, 'low'), 0.01) for c in recent]
        avg_range = mean(ranges)
        high = max(_cval(c, 'high') for c in recent)
        low = min(_cval(c, 'low') for c in recent)
        total_range = max(high - low, 0.01)
        closes = [_cval(c, 'close') for c in recent]
        net_move = abs(closes[-1] - closes[0])
        return (net_move < avg_range * 0.8 and total_range < avg_range * 3.2)
