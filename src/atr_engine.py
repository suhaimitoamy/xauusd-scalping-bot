def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return 0.0

    tr_list = []
    for i in range(1, len(candles)):
        current = candles[i]
        previous = candles[i - 1]

        hl = current['high'] - current['low']
        hc = abs(current['high'] - previous['close'])
        lc = abs(current['low'] - previous['close'])

        tr = max(hl, hc, lc)
        tr_list.append(tr)

    recent_trs = tr_list[-period:]
    return sum(recent_trs) / len(recent_trs) if recent_trs else 0.0
