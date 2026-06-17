"""
Liquidity map:
- BSL from swing highs above price
- SSL from swing lows below price
- Equal High / Equal Low
- Previous Day High / Low if D1 candles are available
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


def _equal_levels(levels, tolerance=0.80):
    found = []
    for i, a in enumerate(levels):
        cluster = [a]
        for b in levels[i + 1:]:
            if abs(a - b) <= tolerance:
                cluster.append(b)
        if len(cluster) >= 2:
            avg = sum(cluster) / len(cluster)
            if not any(abs(avg - x) <= tolerance for x in found):
                found.append(avg)
    return found


def build_liquidity_map(m15_candles=None, h1_candles=None, d1_candles=None, current_price=None):
    candles = m15_candles or h1_candles or []
    if not candles:
        return {
            "nearest_bsl": None,
            "nearest_ssl": None,
            "equal_high": None,
            "equal_low": None,
            "previous_day_high": None,
            "previous_day_low": None,
            "price_position": "unknown",
        }

    if current_price is None:
        current_price = _v(candles[-1], "close")

    highs, lows = get_swings(candles[-120:])

    high_levels = [_v(h, "high") for h in highs]
    low_levels = [_v(l, "low") for l in lows]

    bsl = sorted([x for x in high_levels if x > current_price], key=lambda x: abs(x - current_price))
    ssl = sorted([x for x in low_levels if x < current_price], key=lambda x: abs(x - current_price))

    eqh = sorted([x for x in _equal_levels(high_levels) if x > current_price], key=lambda x: abs(x - current_price))
    eql = sorted([x for x in _equal_levels(low_levels) if x < current_price], key=lambda x: abs(x - current_price))

    pdh = None
    pdl = None
    if d1_candles and len(d1_candles) >= 2:
        previous_day = d1_candles[-2]
        pdh = _v(previous_day, "high")
        pdl = _v(previous_day, "low")

    nearest_bsl = bsl[0] if bsl else None
    nearest_ssl = ssl[0] if ssl else None

    if nearest_bsl and nearest_ssl:
        price_position = "closer_to_ssl" if abs(current_price - nearest_ssl) < abs(nearest_bsl - current_price) else "closer_to_bsl"
    elif nearest_bsl:
        price_position = "below_bsl"
    elif nearest_ssl:
        price_position = "above_ssl"
    else:
        price_position = "no_near_liquidity"

    return {
        "nearest_bsl": nearest_bsl,
        "nearest_ssl": nearest_ssl,
        "equal_high": eqh[0] if eqh else None,
        "equal_low": eql[0] if eql else None,
        "previous_day_high": pdh,
        "previous_day_low": pdl,
        "price_position": price_position,
        "current_price": current_price,
    }


def format_liquidity_map(ctx):
    def f(x):
        return "N/A" if x is None else f"{float(x):.2f}"

    return "\n".join([
        "💧 LIQUIDITY MAP",
        f"Nearest BSL: {f(ctx.get('nearest_bsl'))}",
        f"Nearest SSL: {f(ctx.get('nearest_ssl'))}",
        f"Equal High: {f(ctx.get('equal_high'))}",
        f"Equal Low: {f(ctx.get('equal_low'))}",
        f"PDH: {f(ctx.get('previous_day_high'))}",
        f"PDL: {f(ctx.get('previous_day_low'))}",
        f"Price Position: {ctx.get('price_position')}",
    ])
