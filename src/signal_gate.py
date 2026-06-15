"""Pre-send signal gate for adaptive signals."""
from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from src.market_memory import MarketMemory
from src.method_registry import get_main_methods, load_config, method_allowed, equivalent_method_names
from src.rr_guard import attach_rr, validate_rr


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

        attach_rr(signal)
        pattern_key = signal.get('pattern_key') or ''

        target_method = os.environ.get('FAIR_TEST_METHOD') or os.environ.get('METHOD_UNDER_TEST')
        backtest_mode = os.environ.get('BACKTEST_ALL_METHODS', '').lower() in {'1', 'true', 'yes', 'on'}
        fair_test_mode = os.environ.get('FAIR_TEST', '').lower() in {'1', 'true', 'yes', 'on'} or bool(target_method)
        live_mode = not backtest_mode and not fair_test_mode

        if target_method:
            if not (equivalent_method_names(pattern_key) & equivalent_method_names(target_method)):
                return False, f"BLOCK: fair-test hanya untuk {target_method}, bukan {pattern_key}"

        signal_tf = signal.get('signal_timeframe') or 'M5'
        active = self.memory.active_signal(signal_tf)
        if active:
            return False, f"BLOCK: masih ada signal {signal_tf} ACTIVE #{active.get('id')} {active.get('direction')}"

        if pattern_key and self.memory.is_pattern_in_cooldown(pattern_key):
            return False, f"BLOCK: pattern {pattern_key} masih cooldown"

        adaptive = (self.config or {}).get('adaptive_brain', {})
        whitelist = get_main_methods(self.config)
        if whitelist and live_mode and not method_allowed(pattern_key, whitelist, backtest_all=False):
            return False, f"BLOCK: {pattern_key} tidak ada di LIVE whitelist"

        rr_cfg = adaptive.get('rr_guard', {}) if isinstance(adaptive, dict) else {}
        rr_enabled = bool(rr_cfg.get('enabled', True))
        min_rr = float(rr_cfg.get('min_rr', 2.0))

        if rr_enabled:
            ok, msg, rr = validate_rr(signal, min_rr=min_rr)
            signal['rr_gate_status'] = 'PASS' if ok else 'FAIL'
            signal['rr_gate_message'] = msg
            # Backtest/fair-test tidak boleh diblokir oleh RR Guard.
            # Tujuannya agar metode tetap muncul di hasil, lalu metode RR jelek bisa diaudit.
            if live_mode and not ok:
                return False, msg

        confidence = float(signal.get('confidence') or 0)
        if confidence <= 0:
            return False, "BLOCK: confidence invalid"

        return True, "ALLOW"
