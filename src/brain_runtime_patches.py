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
    - Context gets improved H1/H4/D1 bias and time aliases for session methods.
    - CRT H1 SELL is wired as a watchlist/backtest method.
    - Telegram trade events use one consistent template.
    - The old automatic full method report is stopped after every trade event.
    - DB compatibility view `fvgs` is created from `active_fvgs` when needed.
    """
    patch_brain_engine()
    patch_signal_tracker()
    patch_storage_compat()


def _safe_bias(engine, candles):
    try:
        if candles and len(candles) >= 10:
            return engine._bias(candles)
    except Exception:
        pass
    return "neutral"


def _ema_bias(candles):
    try:
        if not candles or len(candles) < 20:
            return "neutral"
        closes = [float(c.get("close") or 0) for c in candles if c.get("close") is not None]
        if len(closes) < 20:
            return "neutral"
        def ema(data, period):
            k = 2 / (period + 1)
            value = data[0]
            for price in data[1:]:
                value = (price * k) + (value * (1 - k))
            return value
        ema20 = ema(closes, 20)
        ema50 = ema(closes, 50) if len(closes) >= 50 else None
        last = closes[-1]
        if ema50 is not None:
            if last > ema20 > ema50:
                return "bullish"
            if last < ema20 < ema50:
                return "bearish"
        if last > ema20:
            return "bullish"
        if last < ema20:
            return "bearish"
    except Exception:
        pass
    return "neutral"


def _combined_htf_bias(h1_bias, h4_bias, d1_bias):
    values = [str(x or "").lower() for x in (h1_bias, h4_bias, d1_bias)]
    bulls = values.count("bullish")
    bears = values.count("bearish")
    if bears >= 2 and bulls == 0:
        return "BEARISH"
    if bulls >= 2 and bears == 0:
        return "BULLISH"
    if bears > bulls:
        return "BEARISH"
    if bulls > bears:
        return "BULLISH"
    return "MIXED"


def patch_brain_engine() -> None:
    try:
        from src.market_brain import BrainEngine
        from src.method_registry import equivalent_method_names, is_backtest_all_enabled
        from src.crt_h1_method import evaluate_crt_h1_sell
        from src.rr_guard import calculate_rr
        from src.market_structure import analyze_structure
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
                # Simulator lama kadang cuma kirim 12 H1. Ambil ulang H1 lebih panjang dari DB.
                extended_h1 = h1 or []
                try:
                    more_h1 = self.storage.get_recent_candles(self.symbol, "H1", 96)
                    if more_h1 and len(more_h1) > len(extended_h1):
                        extended_h1 = more_h1
                except Exception:
                    pass

                h4 = ctx.get("h4_candles") or []
                d1 = ctx.get("d1_candles") or []
                h1_bias = _safe_bias(self, extended_h1)
                h4_bias = _safe_bias(self, h4)
                d1_bias = _safe_bias(self, d1)

                if h1_bias == "neutral":
                    h1_bias = _ema_bias(extended_h1)
                if h4_bias == "neutral":
                    h4_bias = _ema_bias(h4)
                if d1_bias == "neutral":
                    d1_bias = _ema_bias(d1)

                ctx["h1_candles"] = extended_h1
                ctx["h1_bias"] = h1_bias
                ctx["h4_bias"] = h4_bias
                ctx["d1_bias"] = d1_bias
                ctx["htf_bias"] = _combined_htf_bias(h1_bias, h4_bias, d1_bias)
                ctx["context_quality"] = {
                    "m5_count": len(m5 or []),
                    "m15_count": len(m15 or []),
                    "h1_count": len(extended_h1 or []),
                    "h4_count": len(h4 or []),
                    "d1_count": len(d1 or []),
                    "h1_extended_from_db": len(extended_h1 or []) > len(h1 or []),
                }

                try:
                    ctx["structure"] = analyze_structure(m5 or [], m15 or [], extended_h1 or [])
                except Exception:
                    pass

                last_time = ctx.get("last_time")
                if last_time:
                    ctx.setdefault("timestamp", last_time)
                    ctx.setdefault("open_time", last_time)
            except Exception:
                pass
            return ctx

        BrainEngine._read_market_context = _patched_read_market_context

    if hasattr(BrainEngine, "_decide"):
        original_decide = BrainEngine._decide

        @wraps(original_decide)
        def _patched_decide(self, ctx):
            crt_result = evaluate_crt_h1_sell(ctx)
            if crt_result:
                _, _, pattern_key, _ = crt_result
                if self._main_method_allowed(pattern_key) and not self._method_blocked(pattern_key):
                    return crt_result
            return original_decide(self, ctx)

        BrainEngine._decide = _patched_decide

    if hasattr(BrainEngine, "_build_signal"):
        original_build_signal = BrainEngine._build_signal

        @wraps(original_build_signal)
        def _patched_build_signal(self, direction, price, ctx, confidence, reason, pattern_key, pattern):
            signal = original_build_signal(self, direction, price, ctx, confidence, reason, pattern_key, pattern)
            if not signal:
                return signal
            if pattern_key == "METHOD_CRT_H1_SELL" and direction == "SELL":
                crt = ctx.get("crt_h1") or {}
                crh = crt.get("crh")
                if crh:
                    buffer_points = float(((self.config or {}).get("adaptive_brain", {}).get("crt_h1", {}) or {}).get("sl_buffer_points", 2.0))
                    sl = float(crh) + buffer_points
                    entry = float(price)
                    risk = max(sl - entry, 1.0)
                    tp1 = entry - risk
                    tp2 = entry - (risk * 2.0)
                    signal.update({
                        "entry_type": "MARKET",
                        "entry_low": round(entry - 0.5, 3),
                        "entry_high": round(entry + 0.5, 3),
                        "pending_price": None,
                        "sl": round(sl, 3),
                        "tp1": round(tp1, 3),
                        "tp2": round(tp2, 3),
                        "invalid_level": round(sl, 3),
                        "signal_timeframe": "H1",
                        "signal_class": "CRT_H1",
                        "crt_h1": crt,
                    })
                    rr = calculate_rr(signal)
                    signal["rr"] = rr.get("rr")
                    signal["risk_points"] = rr.get("risk")
                    signal["reward_points"] = rr.get("reward")
            return signal

        BrainEngine._build_signal = _patched_build_signal

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
