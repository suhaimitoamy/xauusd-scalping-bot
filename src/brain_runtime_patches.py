from __future__ import annotations

import os
from functools import wraps


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def apply_patches() -> None:
    """Apply safe runtime patches without editing the large strategy file directly.

    - Backtest mode can test all methods via BACKTEST_ALL_METHODS=true.
    - FAIR_TEST_METHOD can force a single target method where whitelist checks are used.
    - Live mode keeps whitelist strict, with BUY/SELL suffix compatibility.
    - Context gets h4_bias/d1_bias and time aliases for session methods.
    - Telegram trade events use one consistent template.
    - The old automatic full method report is stopped after every trade event.
    - DB compatibility view `fvgs` is created from `active_fvgs` when needed.
    """
    patch_brain_engine()
    patch_signal_tracker()
    patch_storage_compat()


def patch_brain_engine() -> None:
    try:
        from src.market_brain import BrainEngine
        from src.method_registry import equivalent_method_names, is_backtest_all_enabled
    except Exception:
        return

    if getattr(BrainEngine, "_amy_runtime_patched", False):
        return

    def _patched_main_method_allowed(self, pattern_key: str) -> bool:
        target_method = os.environ.get("FAIR_TEST_METHOD") or os.environ.get("METHOD_UNDER_TEST")
        if target_method:
            return bool(equivalent_method_names(pattern_key) & equivalent_method_names(target_method))
        if is_backtest_all_enabled(getattr(self, "config", None) or {}):
            return True
        adaptive = (getattr(self, "config", None) or {}).get("adaptive_brain", {})
        main_methods = set(adaptive.get("main_methods") or getattr(self, "main_methods", set()) or [])
        if not main_methods:
            return True
        key_equiv = equivalent_method_names(pattern_key)
        allowed_equiv = set()
        for item in main_methods:
            allowed_equiv.update(equivalent_method_names(item))
        return bool(key_equiv & allowed_equiv)

    BrainEngine._main_method_allowed = _patched_main_method_allowed

    if hasattr(BrainEngine, "_read_market_context"):
        original_read_context = BrainEngine._read_market_context

        @wraps(original_read_context)
        def _patched_read_market_context(self, price, m5, m15, h1):
            ctx = original_read_context(self, price, m5, m15, h1)
            try:
                h4 = ctx.get("h4_candles") or []
                d1 = ctx.get("d1_candles") or []
                if "h4_bias" not in ctx:
                    ctx["h4_bias"] = self._bias(h4)
                if "d1_bias" not in ctx:
                    ctx["d1_bias"] = self._bias(d1)
                last_time = ctx.get("last_time")
                if last_time:
                    ctx.setdefault("timestamp", last_time)
                    ctx.setdefault("open_time", last_time)
            except Exception:
                pass
            return ctx

        BrainEngine._read_market_context = _patched_read_market_context

    BrainEngine._amy_runtime_patched = True


def patch_signal_tracker() -> None:
    try:
        import src.signal_tracker as tracker
        from src.telegram_notifier import send_telegram_message, telegram_is_configured
        from src.telegram_templates import format_trade_event
    except Exception:
        return

    if getattr(tracker, "_amy_runtime_patched", False):
        return

    def notify_telegram_event(event_type, signal, current_price):
        if not telegram_is_configured():
            return
        send_telegram_message(format_trade_event(event_type, signal, current_price))

    def review_signal_without_big_report(storage, signal, sid, current_price):
        try:
            from src.ai_trainer import AdaptiveTrainer
            trainer_msg = AdaptiveTrainer(storage, signal.get('symbol', 'XAU/USD')).review_closed_signal(sid, current_price)
            tracker.logger.info(trainer_msg)
            if telegram_is_configured():
                send_telegram_message(trainer_msg)
        except Exception as e:
            tracker.logger.error(f"Adaptive trainer error: {e}")

    tracker.notify_telegram_event = notify_telegram_event
    tracker._review_signal = review_signal_without_big_report
    tracker._amy_runtime_patched = True


def patch_storage_compat() -> None:
    try:
        from src.storage import Storage
        from src.db_compat import ensure_runtime_compat
    except Exception:
        return

    if getattr(Storage, "_amy_runtime_patched", False):
        return

    original_init = Storage.__init__

    @wraps(original_init)
    def _patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        try:
            ensure_runtime_compat(self)
        except Exception:
            pass

    Storage.__init__ = _patched_init
    Storage._amy_runtime_patched = True
