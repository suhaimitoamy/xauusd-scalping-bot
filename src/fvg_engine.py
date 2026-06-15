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

    recent_bodies = [abs(c['close'] - c['open']) for c in candles[-6:-1]]
    mean_body = sum(recent_bodies) / len(recent_bodies) if recent_bodies else 0

    c2_body = abs(c2['close'] - c2['open'])
    c2_max = max(c2['open'], c2['close'])
    c2_min = min(c2['open'], c2['close'])
    c2_upper_wick = c2['high'] - c2_max
    c2_lower_wick = c2_min - c2['low']

    perc_body = 0.36
    body_clean = (c2_upper_wick < c2_body * perc_body) and (c2_lower_wick < c2_body * perc_body)
    is_displacement = c2_body > mean_body

    if not (body_clean and is_displacement):
        return fvgs

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
                'source_candle_time': c2['open_time'],
                'timeframe': timeframe,
            })

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
                'source_candle_time': c2['open_time'],
                'timeframe': timeframe,
            })

    return fvgs


def update_all_fvg_status(storage, current_price, symbol):
    """
    Fetches active fvgs, checks if price touched them (PARTIAL), crossed them
    (MITIGATED), or invalidated them. Returns new partial-touch alerts.
    """
    active_fvgs = storage.get_active_fvgs(symbol)
    alerts = []

    for fvg in active_fvgs:
        old_status = fvg['status']
        new_status = old_status
        low, high = fvg['low'], fvg['high']

        if fvg['direction'] == 'Bullish':
            if current_price < low:
                new_status = 'INVALID'
            elif current_price <= high:
                new_status = 'PARTIAL' if current_price >= low else 'MITIGATED'

        elif fvg['direction'] == 'Bearish':
            if current_price > high:
                new_status = 'INVALID'
            elif current_price >= low:
                new_status = 'PARTIAL' if current_price <= high else 'MITIGATED'

        if old_status == 'UNFILLED' and new_status == 'PARTIAL':
            alerts.append(fvg)

        if new_status != old_status:
            storage.update_fvg_status(fvg['id'], new_status)
            if new_status == 'INVALID':
                from src.telegram_notifier import send_telegram_message, telegram_is_configured
                if telegram_is_configured():
                    msg = f"🚨 WARNING: FVG {fvg['direction']} di {low} - {high} BREAK/JEBOL!\nZona pertahanan telah jebol (Inversion FVG)."
                    send_telegram_message(msg)

    return alerts


def get_nearest_fvg(current_price, fvgs, direction=None):
    if not fvgs:
        return None

    valid_fvgs = [f for f in fvgs if f.get('status') in ['UNFILLED', 'PARTIAL', 'VALID', 'ACTIVE']]
    if direction:
        valid_fvgs = [f for f in valid_fvgs if str(f.get('direction', '')).lower() == direction.lower()]

    if not valid_fvgs:
        return None

    valid_fvgs.sort(key=lambda x: min(abs(current_price - x['low']), abs(current_price - x['high'])))
    return valid_fvgs[0]


def get_nearest_ifvg(storage, current_price, symbol, direction=None):
    """
    Returns nearest invalidated FVG / IFVG using active_fvgs compatibility.
    A Bullish FVG that is INVALID becomes Bearish IFVG.
    A Bearish FVG that is INVALID becomes Bullish IFVG.
    """
    try:
        rows = storage.fetchall(
            "SELECT * FROM active_fvgs WHERE symbol = ? AND status = 'INVALID' ORDER BY last_touched_at DESC LIMIT 50",
            (symbol,),
        )
    except TypeError:
        rows = storage.fetchall(
            f"SELECT * FROM active_fvgs WHERE symbol = '{symbol}' AND status = 'INVALID' ORDER BY last_touched_at DESC LIMIT 50"
        )
    except Exception:
        rows = []

    if not rows:
        return None

    valid_ifvgs = []
    for f in rows:
        f_dir = 'Bearish' if f['direction'] == 'Bullish' else 'Bullish'
        if direction and f_dir.lower() != direction.lower():
            continue
        valid_ifvgs.append({
            'direction': f_dir,
            'low': f['low'],
            'high': f['high'],
        })

    if not valid_ifvgs:
        return None

    valid_ifvgs.sort(key=lambda x: min(abs(current_price - x['low']), abs(current_price - x['high'])))
    return valid_ifvgs[0]


def get_bpr(storage, symbol, timeframe=None):
    active_fvgs = storage.get_active_fvgs(symbol, timeframe)
    bull_fvgs = [f for f in active_fvgs if f['direction'] == 'Bullish']
    bear_fvgs = [f for f in active_fvgs if f['direction'] == 'Bearish']

    bprs = []
    for bull in bull_fvgs:
        for bear in bear_fvgs:
            overlap_low = max(bull['low'], bear['low'])
            overlap_high = min(bull['high'], bear['high'])
            if overlap_low < overlap_high:
                bprs.append({'low': overlap_low, 'high': overlap_high})
    return bprs


def format_fvg_map(storage, symbol, current_price):
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
        return fvg.get('status', 'N/A')

    m15_bull = get_nearest_fvg(current_price, m15_fvgs, 'Bullish')
    m15_bear = get_nearest_fvg(current_price, m15_fvgs, 'Bearish')
    m5_bull = get_nearest_fvg(current_price, m5_fvgs, 'Bullish')
    m5_bear = get_nearest_fvg(current_price, m5_fvgs, 'Bearish')
    h1_nearest = get_nearest_fvg(current_price, h1_fvgs)

    header = "XAUUSD — ACTIVE FVG MAP\nSource: RULE ENGINE\n\n"
    if not any([m15_bull, m15_bear, m5_bull, m5_bear, h1_nearest]):
        return header + "Tidak ada FVG aktif yang relevan saat ini."

    h1_direction = h1_nearest['direction'] if h1_nearest else 'N/A'
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
        f"Nearest FVG: {_format_fvg_str(h1_nearest)} ({h1_direction})\n"
        f"Status: {_format_status_str(h1_nearest)}\n\n"
        f"Current Price: {current_price:.2f}"
    )
    return header + body


def scan_and_store_fvgs(storage, symbol, timeframe, candles):
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
            'raw_json': json.dumps(f, ensure_ascii=False),
        }
        storage.upsert_fvg(data)
        saved.append(data)
    return saved
