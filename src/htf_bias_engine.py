"""
HTF bias engine for mapping.
Reads HH/HL and LH/LL, plus invalidation level.
"""

from __future__ import annotations


def _v(candle, key, default=0.0):
    try:
        return float(candle.get(key, default) or default)
    except Exception:
        return default


def get_swings(candles, left=2, right=2):
    highs, lows = [], []
    if not candles:
        return highs, lows

    for i in range(left, len(candles) - right):
        h = _v(candles[i], "high")
        l = _v(candles[i], "low")
        is_high = True
        is_low = True

        for j in range(1, left + 1):
            if _v(candles[i - j], "high") >= h:
                is_high = False
            if _v(candles[i - j], "low") <= l:
                is_low = False

        for j in range(1, right + 1):
            if _v(candles[i + j], "high") >= h:
                is_high = False
            if _v(candles[i + j], "low") <= l:
                is_low = False

        if is_high:
            highs.append(candles[i])
        if is_low:
            lows.append(candles[i])

    return highs, lows


def analyze_single_tf(candles, label):
    if len(candles or []) < 10:
        return {
            "timeframe": label,
            "bias": "neutral",
            "sequence": "INSUFFICIENT",
            "invalidation_level": None,
            "invalidation_label": "N/A",
            "last_swing_high": None,
            "last_swing_low": None,
        }

    highs, lows = get_swings(candles)
    last_close = _v(candles[-1], "close")

    last_high = _v(highs[-1], "high") if highs else None
    last_low = _v(lows[-1], "low") if lows else None

    bias = "neutral"
    sequence = "MIXED"
    invalid_level = None
    invalid_label = "N/A"

    if len(highs) >= 2 and len(lows) >= 2:
        h2, h1 = _v(highs[-2], "high"), _v(highs[-1], "high")
        l2, l1 = _v(lows[-2], "low"), _v(lows[-1], "low")

        if h1 > h2 and l1 > l2:
            bias = "bullish"
            sequence = "HH + HL"
            invalid_level = l1
            invalid_label = "Higher Low"
        elif h1 < h2 and l1 < l2:
            bias = "bearish"
            sequence = "LH + LL"
            invalid_level = h1
            invalid_label = "Lower High"
        elif h1 > h2 and l1 < l2:
            bias = "expanding"
            sequence = "HH + LL"
        elif h1 < h2 and l1 > l2:
            bias = "choppy"
            sequence = "LH + HL"

    invalidated = False
    if bias == "bullish" and invalid_level is not None:
        invalidated = last_close < invalid_level
    if bias == "bearish" and invalid_level is not None:
        invalidated = last_close > invalid_level

    return {
        "timeframe": label,
        "bias": bias,
        "sequence": sequence,
        "invalidation_level": invalid_level,
        "invalidation_label": invalid_label,
        "invalidated": invalidated,
        "last_swing_high": last_high,
        "last_swing_low": last_low,
        "last_close": last_close,
    }


def analyze_htf_bias(h1_candles=None, h4_candles=None, d1_candles=None):
    h1 = analyze_single_tf(h1_candles or [], "H1")
    h4 = analyze_single_tf(h4_candles or [], "H4")
    d1 = analyze_single_tf(d1_candles or [], "D1")

    votes = [d1["bias"], h4["bias"], h1["bias"]]
    bullish = votes.count("bullish")
    bearish = votes.count("bearish")

    if bullish >= 2:
        final_bias = "bullish"
    elif bearish >= 2:
        final_bias = "bearish"
    else:
        final_bias = "mixed"

    return {
        "final_bias": final_bias,
        "D1": d1,
        "H4": h4,
        "H1": h1,
    }


def format_htf_bias(ctx):
    d1 = ctx.get("D1", {})
    h4 = ctx.get("H4", {})
    h1 = ctx.get("H1", {})
    return "\n".join([
        "🧭 HTF BIAS",
        f"Final: {ctx.get('final_bias')}",
        f"D1: {d1.get('bias')} ({d1.get('sequence')}) | Invalidasi: {d1.get('invalidation_label')} {d1.get('invalidation_level')}",
        f"H4: {h4.get('bias')} ({h4.get('sequence')}) | Invalidasi: {h4.get('invalidation_label')} {h4.get('invalidation_level')}",
        f"H1: {h1.get('bias')} ({h1.get('sequence')}) | Invalidasi: {h1.get('invalidation_label')} {h1.get('invalidation_level')}",
    ])
