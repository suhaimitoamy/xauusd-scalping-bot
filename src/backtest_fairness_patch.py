from __future__ import annotations

import os
import re
from functools import wraps


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_backtest_like() -> bool:
    return any(_truthy(os.environ.get(x, "")) for x in ("BACKTEST_ALL_METHODS", "FAIR_TEST", "DRY_RUN")) or bool(
        os.environ.get("FAIR_TEST_METHOD") or os.environ.get("METHOD_UNDER_TEST")
    )


def _f(ctx, key, default=0.0):
    try:
        return float(ctx.get(key) if ctx.get(key) is not None else default)
    except Exception:
        return default


def strict_follow_trend_ok(ctx, direction: str) -> bool:
    direction = str(direction or "").upper()
    m15 = str(ctx.get("m15_bias") or "").lower()
    h1 = str(ctx.get("h1_bias") or "").lower()
    h4 = str(ctx.get("h4_bias") or "").lower()
    d1 = str(ctx.get("d1_bias") or "").lower()
    htf = str(ctx.get("htf_bias") or "").upper()
    momentum = str(ctx.get("momentum") or "").lower()
    structure = ctx.get("structure") or {}
    if bool(ctx.get("choppy")) or bool(structure.get("choppy")):
        return False

    open_ = _f(ctx, "last_open")
    close = _f(ctx, "last_close")
    high = _f(ctx, "last_high")
    low = _f(ctx, "last_low")
    atr = max(_f(ctx, "atr", 1.5), 0.01)
    prev_high = _f(ctx, "prev_high")
    prev_low = _f(ctx, "prev_low")
    body = abs(close - open_)
    rng = max(high - low, 0.01)
    body_ratio = body / rng

    if body_ratio < 0.55 or body < max(0.7, atr * 0.35):
        return False

    if direction == "BUY":
        aligned = m15 == "bullish" and h1 == "bullish" and htf != "BEARISH" and h4 != "bearish" and d1 != "bearish" and momentum != "bearish"
        strong_close = close > open_ and close >= high - (rng * 0.30)
        not_stretched = not prev_high or close <= prev_high + (atr * 0.75)
        return bool(aligned and strong_close and not_stretched)

    if direction == "SELL":
        aligned = m15 == "bearish" and h1 == "bearish" and htf != "BULLISH" and h4 != "bullish" and d1 != "bullish" and momentum != "bullish"
        strong_close = close < open_ and close <= low + (rng * 0.30)
        not_stretched = not prev_low or close >= prev_low - (atr * 0.75)
        return bool(aligned and strong_close and not_stretched)

    return False


def apply_backtest_fairness_patch() -> None:
    try:
        from src.market_brain import BrainEngine
    except Exception:
        return

    if getattr(BrainEngine, "_amy_backtest_fairness_patched", False):
        return

    if hasattr(BrainEngine, "_decide"):
        original_decide = BrainEngine._decide

        @wraps(original_decide)
        def fair_decide(self, ctx):
            result = original_decide(self, ctx)
            try:
                direction, reason, pattern_key, confidence = result
                if str(pattern_key or "").startswith("METHOD_FOLLOW_THE_TREND_"):
                    if not strict_follow_trend_ok(ctx, direction):
                        return ("NO_TRADE", "FOLLOW_THE_TREND diperketat: trend/filter belum valid", "WAITING", 0)
                    if is_backtest_like():
                        confidence = 70.0
                    return (direction, reason + " | STRICT_FOLLOW_TREND", pattern_key, confidence)
            except Exception:
                pass
            return result

        BrainEngine._decide = fair_decide

    if hasattr(BrainEngine, "_build_signal"):
        original_build_signal = BrainEngine._build_signal

        @wraps(original_build_signal)
        def fair_build_signal(self, direction, price, ctx, confidence, reason, pattern_key, pattern):
            original_confidence = confidence
            patched_pattern = pattern
            if is_backtest_like():
                confidence = 70.0
                patched_pattern = dict(pattern or {})
                patched_pattern["wins"] = 0
                patched_pattern["losses"] = 0
                patched_pattern["score"] = 0
            signal = original_build_signal(self, direction, price, ctx, confidence, reason, pattern_key, patched_pattern)
            if signal and is_backtest_like():
                signal["confidence"] = 70.0
                signal["confidence_mode"] = "BACKTEST_NEUTRAL"
                signal["original_confidence"] = round(float(original_confidence or 0), 1)
                signal["reason"] = re.sub(r"\s*\| Memory:.*$", "", str(signal.get("reason") or ""))
            return signal

        BrainEngine._build_signal = fair_build_signal

    BrainEngine._amy_backtest_fairness_patched = True
