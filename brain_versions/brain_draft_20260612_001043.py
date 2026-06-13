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
            if win_rate < 40.0:
                sig = _no_trade(f'Auto-Block: {pattern_key} dihentikan sementara (WR {win_rate:.1f}% dari {total_trades} trade). Bot butuh reset memori.', 0, pattern_key)
                sig['current_price'] = price
                sig['brain_context'] = context
                self.memory.save_decision(sig)
                return sig
        
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
        h1_break
