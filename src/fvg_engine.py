import json
from datetime import datetime, timezone


def detect_fvgs(candles, timeframe):
    """
    Detects Fair Value Gaps (FVG) from the latest closed candles.
    Uses strict rules from PineScript (ICT yang di sempurnakan):
    1. Middle candle must have a body larger than the SMA(body, 5).
    2. Middle candle upper and lower wicks must be < 36% of the body.
    """
    fvgs = []
    if len(candles) < 7:
        return fvgs

    c1 = candles[-3]
    c2 = candles[-2]
    c3 = candles[-1]

    # Calculate mean body of the 5 candles ending at c2 (indexes -6 to -2)
    recent_bodies = [abs(c['close'] - c['open']) for c in candles[-6:-1]]
    mean_body = sum(recent_bodies) / len(recent_bodies) if recent_bodies else 0

    c2_body = abs(c2['close'] - c2['open'])
    c2_max = max(c2['open'], c2['close'])
    c2_min = min(c2['open'], c2['close'])
    c2_upper_wick = c2['high'] - c2_max
    c2_lower_wick = c2_min - c2['low']

    # ICT strict body/wick validation
    perc_Body = 0.36
    L_body = (c2_upper_wick < c2_body * perc_Body) and (c2_lower_wick < c2_body * perc_Body)
    is_displacement = c2_body > mean_body

    if not (L_body and is_displacement):
        return fvgs

    # Bullish FVG
    if c1['high'] < c3['low'] and c2['close'] > c2['open']:
        gap = c3['low'] - c1['high']
        if gap >= 0.5:
            low = c1['high']
            high = c3['low']
            fvgs.append({
                'direction': 'Bullish',
                'low': low,
                'high': high,
                'mid': (low + high) / 2,
                'source_candle_time': c2['open_time']
            })

    # Bearish FVG
    if c1['low'] > c3['high'] and c2['close'] < c2['open']:
        gap = c1['low'] - c3['high']
        if gap >= 0.5:
            low = c3['high']
            high = c1['low']
            fvgs.append({
                'direction': 'Bearish',
                'low': low,
                'high': high,
                'mid': (low + high) / 2,
                'source_candle_time': c2['open_time']
            })

    return fvgs


def update_all_fvg_status(storage, current_price, symbol):
    """
    Fetches active fvgs, checks if price touched them (PARTIAL), crossed them (MITIGATED), or invalidated them.
    Updates their status in the DB.
    Returns a list of alerts if a new PARTIAL status is triggered.
    """
    active_fvgs = storage.get_active_fvgs(symbol)
    alerts = []

    for fvg in active_fvgs:
        old_status = fvg['status']
        new_status = old_status
        low, high = fvg['low'], fvg['high']

        # Bullish FVG Logic
        if fvg['direction'] == 'Bullish':
            if current_price < low:
                new_status = 'INVALID'  # Price broke through completely
            elif current_price <= high:
                new_status = 'PARTIAL' if current_price >= low else 'MITIGATED'

        # Bearish FVG Logic
        elif fvg['direction'] == 'Bearish':
            if current_price > high:
                new_status = 'INVALID'  # Price broke through completely
            elif current_price >= low:
                new_status = 'PARTIAL' if current_price <= high else 'MITIGATED'

        if old_status == 'UNFILLED' and new_status == 'PARTIAL':
            alerts.append(fvg)

        if new_status != old_status:
            storage.update_fvg_status(fvg['id'], new_status)
            if new_status == 'INVALID':
                from src.telegram_notifier import send_telegram_message, telegram_is_configured
                if telegram_is_configured():
                    msg = f"🚨 **WARNING:** FVG {fvg['direction']} di {low} - {high} BREAK/JEBOL!\nZona pertahanan telah jebol (Inversion FVG)."
                    send_telegram_message(msg)

    return alerts


def get_nearest_fvg(current_price, fvgs, direction=None):
    """
    Returns the nearest active FVG to current price.
    """
    if not fvgs:
        return None

    valid_fvgs = [f for f in fvgs if f['status'] in ['UNFILLED', 'PARTIAL']]
    if direction:
        valid_fvgs = [
            f for f in valid_fvgs if f['direction'].lower() == direction.lower()]

    if not valid_fvgs:
        return None

    # Sort by distance to price
    valid_fvgs.sort(key=lambda x: min(
        abs(current_price - x['low']), abs(current_price - x['high'])))
    return valid_fvgs[0]


def get_nearest_ifvg(storage, current_price, symbol, direction=None):
    """
    Returns the nearest IFVG (Invalidated FVG / Inversion FVG).
    A Bullish FVG that is INVALID becomes a Bearish IFVG (Resistance).
    A Bearish FVG that is INVALID becomes a Bullish IFVG (Support).
    """
    rows = storage.fetchall(
        f"SELECT * FROM fvgs WHERE symbol = '{symbol}' AND status = 'INVALID' ORDER BY last_touched_at DESC LIMIT 50"
    )
    if not rows:
        return None
        
    valid_ifvgs = []
    for f in rows:
        # Inverse the direction
        f_dir = 'Bearish' if f['direction'] == 'Bullish' else 'Bullish'
        if direction and f_dir.lower() != direction.lower():
            continue
        valid_ifvgs.append({
            'direction': f_dir,
            'low': f['low'],
            'high': f['high']
        })
        
    if not valid_ifvgs:
        return None
        
    valid_ifvgs.sort(key=lambda x: min(
        abs(current_price - x['low']), abs(current_price - x['high'])))
    return valid_ifvgs[0]


def get_bpr(storage, symbol, timeframe=None):
    """
    Returns BPRs (Balanced Price Ranges) which are the overlaps of active Bullish and Bearish FVGs.
    """
    active_fvgs = storage.get_active_fvgs(symbol, timeframe)
    bull_fvgs = [f for f in active_fvgs if f['direction'] == 'Bullish']
    bear_fvgs = [f for f in active_fvgs if f['direction'] == 'Bearish']
    
    bprs = []
    for bull in bull_fvgs:
        for bear in bear_fvgs:
            overlap_low = max(bull['low'], bear['low'])
            overlap_high = min(bull['high'], bear['high'])
            if overlap_low < overlap_high:
                bprs.append({
                    'low': overlap_low,
                    'high': overlap_high,
                })
    return bprs


def format_fvg_map(storage, symbol, current_price):
    """
    Outputs the CLI string as required (M15, M5, H1 nearest fvgs).
    """
    m15_fvgs = storage.get_active_fvgs(symbol, 'M15')
    m5_fvgs = storage.get_active_fvgs(symbol, 'M5')
    h1_fvgs = storage.get_active_fvgs(symbol, 'H1')

    def _format_fvg_str(fvg):
        if not fvg:
            return "Tidak ada"
        return f"{fvg['low']:.2f} - {fvg['high']:.2f}"

    def _format_status_str(fvg):
        if not fvg:
            return "N/A"
        return fvg['status']

    # Nearest M15
    m15_bull = get_nearest_fvg(current_price, m15_fvgs, 'Bullish')
    m15_bear = get_nearest_fvg(current_price, m15_fvgs, 'Bearish')

    # Nearest M5
    m5_bull = get_nearest_fvg(current_price, m5_fvgs, 'Bullish')
    m5_bear = get_nearest_fvg(current_price, m5_fvgs, 'Bearish')

    # Nearest H1
    h1_nearest = get_nearest_fvg(current_price, h1_fvgs)

    all_empty = not any([m15_bull, m15_bear, m5_bull, m5_bear, h1_nearest])

    header = "XAUUSD — ACTIVE FVG MAP\nSource: RULE ENGINE\n\n"

    if all_empty:
        return header + "Tidak ada FVG aktif yang relevan saat ini."

    body = (
        f"M15:\n"
        f"Nearest Bullish FVG: {_format_fvg_str(m15_bull)}\n"
        f"Status: {_format_status_str(m15_bull)}\n"
        f"Nearest Bearish FVG: {_format_fvg_str(m15_bear)}\n"
        f"Status: {_format_status_str(m15_bear)}\n\n"
        f"M5:\n"
        f"Nearest Bullish FVG: {_format_fvg_str(m5_bull)}\n"
        f"Status: {_format_status_str(m5_bull)}\n"
        f"Nearest Bearish FVG: {_format_fvg_str(m5_bear)}\n"
        f"Status: {_format_status_str(m5_bear)}\n\n"
        f"H1:\n"
        f"Nearest FVG: {
            _format_fvg_str(h1_nearest)} ({
            h1_nearest['direction'] if h1_nearest else 'N/A'})\n"
        f"Status: {_format_status_str(h1_nearest)}\n\n"
        f"Current Price: {current_price:.2f}"
    )

    return header + body


def scan_and_store_fvgs(storage, symbol, timeframe, candles):
    """Detect latest FVGs and persist them into active_fvgs."""
    now = datetime.now(timezone.utc).isoformat()
    saved = []
    for f in detect_fvgs(candles, timeframe):
        data = {
            'symbol': symbol,
            'timeframe': timeframe,
            'direction': f.get('direction'),
            'low': f.get('low'),
            'high': f.get('high'),
            'mid': f.get('mid'),
            'status': 'UNFILLED',
            'created_at': now,
            'last_touched_at': now,
            'strength': 70,
            'source_candle_time': f.get('source_candle_time'),
            'raw_json': f,
        }
        storage.upsert_fvg(data)
        saved.append(data)
    return saved
