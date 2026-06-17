"""
Premium / Discount map.
"""

from __future__ import annotations


def _v(candle, key, default=0.0):
    try:
        return float(candle.get(key, default) or default)
    except Exception:
        return default


def build_range_map(candles, current_price=None, lookback=48):
    if not candles:
        return {
            "range_high": None,
            "range_low": None,
            "equilibrium": None,
            "position": "unknown",
            "current_price": current_price,
        }

    recent = candles[-lookback:] if len(candles) > lookback else candles
    highs = [_v(c, "high") for c in recent]
    lows = [_v(c, "low") for c in recent]

    range_high = max(highs)
    range_low = min(lows)
    eq = (range_high + range_low) / 2

    if current_price is None:
        current_price = _v(candles[-1], "close")

    swing = max(range_high - range_low, 0.01)

    if current_price > eq + swing * 0.10:
        position = "premium"
    elif current_price < eq - swing * 0.10:
        position = "discount"
    else:
        position = "equilibrium"

    return {
        "range_high": range_high,
        "range_low": range_low,
        "equilibrium": eq,
        "position": position,
        "current_price": current_price,
    }


def format_range_map(ctx):
    def f(x):
        return "N/A" if x is None else f"{float(x):.2f}"

    return "\n".join([
        "📍 RANGE MAP",
        f"Range High: {f(ctx.get('range_high'))}",
        f"Range Low: {f(ctx.get('range_low'))}",
        f"EQ: {f(ctx.get('equilibrium'))}",
        f"Current Price: {f(ctx.get('current_price'))}",
        f"Position: {ctx.get('position')}",
    ])
