"""
Price Action Validator Engine for XAUUSD Scalping Signal Bot.
Validates if the price response at a POI is genuine or weak.
"""
import logging

logger = logging.getLogger(__name__)

def validate_price_action(direction, candles, poi_low, poi_high):
    """
    Validates price action at a POI using 10 specific checks.
    Returns (is_valid, reason_message)
    """
    if len(candles) < 3:
        return False, "Data candle tidak cukup untuk validasi PA"

    c1 = candles[-3]
    c2 = candles[-2]
    c3 = candles[-1]  # Latest closed candle

    # Helper lambda to calculate candle parts
    def get_parts(c):
        body = abs(c['close'] - c['open'])
        range_ = c['high'] - c['low']
        upper_wick = c['high'] - max(c['open'], c['close'])
        lower_wick = min(c['open'], c['close']) - c['low']
        is_bullish = c['close'] > c['open']
        return body, range_, upper_wick, lower_wick, is_bullish

    body3, range3, uw3, lw3, bull3 = get_parts(c3)
    body2, range2, uw2, lw2, bull2 = get_parts(c2)

    # 10. Choppy candle filter
    # If the last 3 candles are all dojis or very small bodies
    choppy_count = 0
    for c in (c1, c2, c3):
        b, r, _, _, _ = get_parts(c)
        if r > 0 and (b / r) < 0.3:
            choppy_count += 1
    if choppy_count >= 3:
        return False, "PA Lemah: Market sedang choppy (banyak doji) di area POI"

    # 8. Failed Breakout (Close confirmation through POI)
    if direction == 'BUY':
        if c3['close'] < poi_low:
            return False, "PA Lemah: Candle menembus dan close di bawah POI (Breakout Failure)"
    else:
        if c3['close'] > poi_high:
            return False, "PA Lemah: Candle menembus dan close di atas POI (Breakout Failure)"

    # Identify Rejection and Engulfing/Momentum
    is_valid_rejection = False
    is_valid_engulfing = False
    is_valid_momentum = False

    if direction == 'BUY':
        # 1 & 2 & 9. Rejection candle & Wick Ratio
        # A strong lower wick that touches or pierces the POI
        if c3['low'] <= poi_high and lw3 > body3 and range3 > 0 and (lw3 / range3) >= 0.4:
            is_valid_rejection = True
        elif c2['low'] <= poi_high and lw2 > body2 and range2 > 0 and (lw2 / range2) >= 0.4:
            is_valid_rejection = True

        # 3. Engulfing candle
        if bull3 and not bull2 and body3 > body2 and c3['close'] > c2['high']:
            is_valid_engulfing = True

        # 4 & 7. Displacement / Momentum
        if bull3 and range3 > 0 and (body3 / range3) > 0.6 and body3 >= 1.5:
            is_valid_momentum = True

    elif direction == 'SELL':
        # 1 & 2 & 9. Rejection candle & Wick Ratio
        # A strong upper wick that touches or pierces the POI
        if c3['high'] >= poi_low and uw3 > body3 and range3 > 0 and (uw3 / range3) >= 0.4:
            is_valid_rejection = True
        elif c2['high'] >= poi_low and uw2 > body2 and range2 > 0 and (uw2 / range2) >= 0.4:
            is_valid_rejection = True

        # 3. Engulfing candle
        if not bull3 and bull2 and body3 > body2 and c3['close'] < c2['low']:
            is_valid_engulfing = True

        # 4 & 7. Displacement / Momentum
        if not bull3 and range3 > 0 and (body3 / range3) > 0.6 and body3 >= 1.5:
            is_valid_momentum = True

    # 6. Inside bar / Compression
    is_compression = False
    if range2 > 0 and range3 > 0 and c3['high'] <= c2['high'] and c3['low'] >= c2['low']:
        is_compression = True

    # Combine logic
    if is_compression and not (is_valid_engulfing or is_valid_momentum):
        return False, "PA Lemah: Harga sedang kompresi/inside bar, tunggu konfirmasi breakout"

    if is_valid_rejection or is_valid_engulfing or is_valid_momentum:
        reasons = []
        if is_valid_rejection: reasons.append("Pinbar/Rejection")
        if is_valid_engulfing: reasons.append("Engulfing")
        if is_valid_momentum: reasons.append("Momentum/Displacement")
        return True, "PA Valid: " + " + ".join(reasons)

    return False, "PA Lemah: Tidak ada pantulan (wick) atau momentum balik yang kuat di POI"
