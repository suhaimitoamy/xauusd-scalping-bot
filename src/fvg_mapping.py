"""
FVG mapping helper.
Uses existing active_fvgs table if available.
"""

from __future__ import annotations


def nearest_fvg(storage, symbol, current_price, timeframe=None, direction=None):
    try:
        rows = storage.get_active_fvgs(symbol, timeframe)
    except Exception:
        rows = []

    if direction:
        rows = [r for r in rows if str(r.get("direction", "")).lower() == direction.lower()]

    rows = [r for r in rows if str(r.get("status", "")).upper() not in ("INVALID", "DELETED")]
    if not rows:
        return None

    return sorted(rows, key=lambda r: min(abs(current_price - float(r["low"])), abs(current_price - float(r["high"]))))[0]


def evaluate_fvg_status(fvg, current_price, last_close=None):
    if not fvg:
        return "NONE", "tidak ada FVG"

    low = float(fvg.get("low"))
    high = float(fvg.get("high"))
    direction = str(fvg.get("direction", "")).lower()

    if last_close is None:
        last_close = current_price

    if direction == "bullish":
        if last_close < low:
            return "INVALID / IFVG BEARISH", "Bullish FVG jebol ke bawah"
        if low <= current_price <= high:
            return "PARTIAL", "price masuk Bullish FVG"
        return "FRESH", "Bullish FVG belum disentuh"

    if direction == "bearish":
        if last_close > high:
            return "INVALID / IFVG BULLISH", "Bearish FVG jebol ke atas"
        if low <= current_price <= high:
            return "PARTIAL", "price masuk Bearish FVG"
        return "FRESH", "Bearish FVG belum disentuh"

    return "UNKNOWN", "arah FVG tidak jelas"


def format_fvg_map(fvg, current_price):
    if not fvg:
        return "🟦 FVG MAP\nTidak ada FVG aktif terdekat."

    status, reason = evaluate_fvg_status(fvg, current_price)

    return "\n".join([
        f"🟦 FVG — {status}",
        f"Type: {fvg.get('direction')} FVG",
        f"TF: {fvg.get('timeframe')}",
        f"Zone: {float(fvg.get('low')):.2f} - {float(fvg.get('high')):.2f}",
        f"Current Price: {float(current_price):.2f}",
        f"Reason: {reason}",
        f"Invalidasi: {'close di bawah ' + str(round(float(fvg.get('low')), 2)) if str(fvg.get('direction')).lower() == 'bullish' else 'close di atas ' + str(round(float(fvg.get('high')), 2))}",
    ])
