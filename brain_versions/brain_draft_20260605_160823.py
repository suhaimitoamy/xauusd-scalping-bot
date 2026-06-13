"""Adaptive trading brain for XAUUSD.

This file is intentionally small and editable by the AI Trainer.
Public API that must stay stable:
    BrainEngine(storage, symbol='XAU/USD', config=None)
    BrainEngine.analyze(current_price, m5_candles, m15_candles, h1_candles, data_health=None)
"""
from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

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
        self.min_confidence = float(adaptive_cfg.get('min_confidence', 42))
        self.max_recent_events = int(adaptive_cfg.get('max_recent_events', 30))
        self.sl_atr_mult = float(adaptive_cfg.get('sl_atr_mult', 1.15))
        self.tp1_rr = float(adaptive_cfg.get('tp1_rr', 1.0))
        self.tp2_rr = float(adaptive_cfg.get('tp2_rr', 2.0))
        self.tp3_rr = 0.0
        self.pips_per_price_point = float(adaptive_cfg.get('pips_per_price_point', 10))
        self.max_sl_pips = float(adaptive_cfg.get('max_sl_pips', 100))
        self.max_sl_price_distance = self.max_sl_pips / max(self.pips_per_price_point, 0.01)

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

        active = self.memory.active_signal()
        if active:
            sig = _no_trade(f"Ada signal ACTIVE #{active.get('id')} {active.get('direction')}. Brain menahan signal baru.")
            self.memory.save_decision(sig)
            return sig

        price = float(current_price)
        context = self._read_market_context(price, m5_candles, m15_candles or [], h1_candles or [])
        self._record_context_events(context, price)

        direction, reason, pattern_key, base_conf = self._decide(context)
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
        if confidence < self.min_confidence:
            sig = _no_trade(f'Confidence adaptive masih rendah: {confidence:.0f}%', confidence, pattern_key)
            sig['current_price'] = price
            sig['brain_context'] = context
            self.memory.save_decision(sig)
            return sig

        signal = self._build_signal(direction, price, context, confidence, reason, pattern_key, pattern)
        self.memory.save_decision(signal)
        return signal

    def _read_market_context(self, price: float, m5: List[Dict[str, Any]], m15: List[Dict[str, Any]], h1: List[Dict[str, Any]]) -> Dict[str, Any]:
        last = m5[-1]
        lookback = m5[-8:-1] if len(m5) >= 8 else m5[:-1]
        highs = [_cval(c, 'high') for c in lookback]
        lows = [_cval(c, 'low') for c in lookback]
        prev_high = max(highs) if highs else _cval(last, 'high')
        prev_low = min(lows) if lows else _cval(last, 'low')
        close = _cval(last, 'close', price)
        open_ = _cval(last, 'open', close)
        high = _cval(last, 'high', close)
        low = _cval(last, 'low', close)
        atr = self._atr(m5,
