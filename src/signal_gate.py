"""Pre-send signal gate for adaptive signals."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from src.market_memory import MarketMemory
from src.method_registry import get_main_methods, load_config, method_allowed


class SignalGate:
    def __init__(self, storage):
        self.storage = storage
        self.memory = MarketMemory(storage)
        try:
            self.config = load_config()
        except Exception:
            self.config = {}

    def check(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        if not signal or signal.get('direction') == 'NO_TRADE':
            return False, signal.get('reason', 'NO_TRADE') if signal else 'NO_SIGNAL'

        signal_tf = signal.get('signal_timeframe') or 'M5'
        active = self.memory.active_signal(signal_tf)
        if active:
            return False, f"BLOCK: masih ada signal {signal_tf} ACTIVE #{active.get('id')} {active.get('direction')}"

        pattern_key = signal.get('pattern_key') or ''
        if pattern_key and self.memory.is_pattern_in_cooldown(pattern_key):
            return False, f"BLOCK: pattern {pattern_key} masih cooldown"

        adaptive = (self.config or {}).get('adaptive_brain', {})
        whitelist = get_main_methods(self.config)
        if whitelist and not method_allowed(pattern_key, whitelist, backtest_all=False):
            return False, f"BLOCK: {pattern_key} tidak ada di LIVE whitelist"

        confidence = float(signal.get('confidence') or 0)
        if confidence <= 0:
            return False, "BLOCK: confidence invalid"

        return True, "ALLOW"
