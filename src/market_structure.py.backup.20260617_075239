"""
Market structure analysis for XAUUSD Scalping Signal Bot.
Handles liquidity sweeps, reclaims, and momentum.
"""


def get_swings(candles, left=2, right=2):
    highs = []
    lows = []
    for i in range(left, len(candles) - right):
        is_high = True
        is_low = True
        for j in range(1, left + 1):
            if candles[i - j]['high'] >= candles[i]['high']:
                is_high = False
            if candles[i - j]['low'] <= candles[i]['low']:
                is_low = False
        for j in range(1, right + 1):
            if candles[i + j]['high'] >= candles[i]['high']:
                is_high = False
            if candles[i + j]['low'] <= candles[i]['low']:
                is_low = False

        if is_high:
            highs.append(candles[i])
        if is_low:
            lows.append(candles[i])
    return highs, lows


def calculate_bias(candles):
    if len(candles) < 10:
        return 'neutral'
    highs, lows = get_swings(candles)

    if len(highs) >= 2 and len(lows) >= 2:
        h2, h1 = highs[-2]['high'], highs[-1]['high']
        l2, l1 = lows[-2]['low'], lows[-1]['low']

        hh = h1 > h2
        hl = l1 > l2
        lh = h1 < h2
        ll = l1 < l2

        if hh and hl:
            return 'bullish'
        if lh and ll:
            return 'bearish'
        if hh and ll:
            return 'expanding'
        if lh and hl:
            return 'choppy'

    # Fallback to simple momentum if swings are inconclusive
    closes = [c['close'] for c in candles[-5:]]
    if candles[-1]['close'] > sum(closes) / len(closes):
        return 'bullish'
    return 'bearish'


def is_choppy(candles):
    if len(candles) < 5:
        return False
    doji_count = 0
    for c in candles[-5:]:
        body = abs(c['open'] - c['close'])
        wick = c['high'] - c['low']
        if wick > 0 and body / wick < 0.3:
            doji_count += 1
    return doji_count >= 3


def analyze_structure(m5_candles, m15_candles, h1_candles):
    result = {
        'recent_swing_highs': [],
        'recent_swing_lows': [],
        'nearest_resistance': None,
        'nearest_support': None,
        'liquidity_above': None,
        'liquidity_below': None,
        'sweep_type': None,
        'swept_level': None,
        'sweep_extreme': None,
        'reclaim_level': None,
        'reclaim_valid': False,
        'break_type': None,
        'break_level': None,
        'm5_momentum': 'neutral',
        'm15_bias': 'neutral',
        'h1_bias': 'neutral',
        'middle_of_range': False,
        'choppy': False,
        'atr': 0.0,
        'is_extreme_volatility': False
    }

    if len(m5_candles) < 10:
        return result

    m15_bias = calculate_bias(m15_candles)
    h1_bias = calculate_bias(h1_candles)

    # Exclude current unclosed candle from swing calculation if it's the very
    # last
    highs, lows = get_swings(m5_candles[:-1])

    last_candle = m5_candles[-1]
    curr_price = last_candle['close']

    result['recent_swing_highs'] = [h['high'] for h in highs]
    result['recent_swing_lows'] = [l['low'] for l in lows]

    # Nearest support / resistance
    sup = [l['low'] for l in lows if l['low'] < curr_price]
    res = [h['high'] for h in highs if h['high'] > curr_price]

    result['nearest_support'] = max(sup) if sup else None
    result['nearest_resistance'] = min(res) if res else None
    result['liquidity_below'] = result['nearest_support']
    result['liquidity_above'] = result['nearest_resistance']

    # Check momentum
    body = abs(last_candle['open'] - last_candle['close'])
    rng = last_candle['high'] - last_candle['low']
    if rng > 0 and (body / rng) >= 0.5:
        result['m5_momentum'] = 'bullish' if last_candle['close'] > last_candle['open'] else 'bearish'

    result['m15_bias'] = m15_bias
    result['h1_bias'] = h1_bias
    result['choppy'] = is_choppy(m5_candles)

    # Calculate Volatility (ATR-like from last 14 candles)
    ranges = [(c['high'] - c['low']) for c in m5_candles[-14:]]
    avg_range = sum(ranges) / len(ranges) if ranges else 0
    result['atr'] = avg_range
    result['is_extreme_volatility'] = avg_range > 15.0  # > 150 pips per 5 minutes is EXTREME!

    # Middle of range calculation
    if result['nearest_support'] and result['nearest_resistance']:
        r_range = result['nearest_resistance'] - result['nearest_support']
        pos = (curr_price - result['nearest_support']
               ) / r_range if r_range > 0 else 0
        result['middle_of_range'] = 0.4 <= pos <= 0.6
    else:
        result['middle_of_range'] = False

    # Detect Sweep & Reclaim
    if lows:
        recent_low = lows[-1]['low']
        if last_candle['low'] < recent_low and last_candle['close'] > recent_low:
            result['sweep_type'] = 'bullish'
            result['reclaim_valid'] = True
            result['swept_level'] = recent_low
            result['sweep_extreme'] = last_candle['low']
            result['reclaim_level'] = last_candle['close']

    if highs and not result['sweep_type']:
        recent_high = highs[-1]['high']
        if last_candle['high'] > recent_high and last_candle['close'] < recent_high:
            result['sweep_type'] = 'bearish'
            result['reclaim_valid'] = True
            result['swept_level'] = recent_high
            result['sweep_extreme'] = last_candle['high']
            result['reclaim_level'] = last_candle['close']

    # Detect BOS / MSS
    if highs:
        if last_candle['close'] > highs[-1]['high']:
            result['break_type'] = 'BOS_BULLISH'
            if m15_bias == 'bearish' or h1_bias == 'bearish':
                result['break_type'] = 'MSS_BULLISH'
            result['break_level'] = highs[-1]['high']

    if lows and not result.get('break_type'):
        if last_candle['close'] < lows[-1]['low']:
            result['break_type'] = 'BOS_BEARISH'
            if m15_bias == 'bullish' or h1_bias == 'bullish':
                result['break_type'] = 'MSS_BEARISH'
            result['break_level'] = lows[-1]['low']

    # Market Phase Detection
    # Determine basic market phase based on price relative to recent swings
    phase = 'RANGING'
    if result['break_type']:
        phase = 'EXPANSION'
    elif result['middle_of_range']:
        phase = 'RANGING'
    elif m15_bias == 'bullish' and curr_price > (result['nearest_support'] or 0):
        phase = 'TRENDING' if curr_price > (
            result['nearest_resistance'] or 0) else 'PULLBACK'
    elif m15_bias == 'bearish' and curr_price < (result['nearest_resistance'] or float('inf')):
        phase = 'TRENDING' if curr_price < (
            result['nearest_support'] or float('inf')) else 'PULLBACK'

    if result['choppy']:
        phase = 'CHOPPY'

    result['trend'] = phase

    # Modes: WAIT_RETEST if price just expanded far from a break level
    if result['break_type']:
        dist = abs(curr_price - result['break_level'])
        # If distance from break is > 30 points (approx 30 pips for Gold), wait
        # for pullback
        if dist > 3.0:
            result['retest_mode'] = f"WAIT_PULLBACK_TO_{result['break_level']}"
        else:
            result['retest_mode'] = f"ACTIVE_RETEST_{result['break_type']}"
    else:
        result['retest_mode'] = 'NONE'

    return result
