"""
Order Block engine for mapping assistant.

This does not open trades.
It only maps Bullish/Bearish OB and status:
- FRESH
- TOUCHED
- MITIGATED
- INVALID
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def _v(candle, key, default=0.0):
    try:
        return float(candle.get(key, default) or default)
    except Exception:
        return default


def _time(candle):
    return (
        candle.get("open_time")
        or candle.get("time")
        or candle.get("timestamp")
        or candle.get("close_time")
        or ""
    )


def _body(candle):
    return abs(_v(candle, "close") - _v(candle, "open"))


def _mean_body(candles):
    bodies = [_body(c) for c in candles if c]
    return sum(bodies) / len(bodies) if bodies else 0.0


def _last_swing_high(candles, lookback=10):
    recent = candles[-lookback:] if len(candles) >= lookback else candles
    return max(_v(c, "high") for c in recent) if recent else None


def _last_swing_low(candles, lookback=10):
    recent = candles[-lookback:] if len(candles) >= lookback else candles
    return min(_v(c, "low") for c in recent) if recent else None


def detect_order_blocks(candles, timeframe="M15", symbol="XAU/USD", lookback=80):
    result = []
    if len(candles or []) < 20:
        return result

    data = candles[-lookback:] if len(candles) > lookback else candles
    avg_body = _mean_body(data[-20:])

    for i in range(10, len(data) - 2):
        prev = data[i - 1]
        impulse = data[i]
        before = data[max(0, i - 10):i]

        impulse_body = _body(impulse)
        if impulse_body < max(avg_body * 1.25, 0.50):
            continue

        prev_high = _last_swing_high(before, 10)
        prev_low = _last_swing_low(before, 10)

        # Bullish OB: last bearish candle before bullish displacement + break high
        if _v(prev, "close") < _v(prev, "open") and _v(impulse, "close") > _v(impulse, "open"):
            if prev_high is not None and _v(impulse, "close") > prev_high:
                result.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "direction": "Bullish",
                    "type": "Bullish OB",
                    "low": _v(prev, "low"),
                    "high": _v(prev, "high"),
                    "status": "VALID",
                    "strength": "HIGH" if impulse_body >= avg_body * 1.8 else "MEDIUM",
                    "reason": "bearish candle before bullish displacement + break swing high",
                    "source_candle_time": _time(prev),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

        # Bearish OB: last bullish candle before bearish displacement + break low
        if _v(prev, "close") > _v(prev, "open") and _v(impulse, "close") < _v(impulse, "open"):
            if prev_low is not None and _v(impulse, "close") < prev_low:
                result.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "direction": "Bearish",
                    "type": "Bearish OB",
                    "low": _v(prev, "low"),
                    "high": _v(prev, "high"),
                    "status": "VALID",
                    "strength": "HIGH" if impulse_body >= avg_body * 1.8 else "MEDIUM",
                    "reason": "bullish candle before bearish displacement + break swing low",
                    "source_candle_time": _time(prev),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

    # Keep unique latest zones
    unique = {}
    for ob in result:
        key = (ob["direction"], round(ob["low"], 2), round(ob["high"], 2), ob["source_candle_time"])
        unique[key] = ob

    return list(unique.values())[-20:]


def evaluate_ob_status(ob, current_price, last_close=None):
    low = float(ob.get("low"))
    high = float(ob.get("high"))
    direction = str(ob.get("direction", "")).lower()

    if last_close is None:
        last_close = current_price

    if direction == "bullish":
        if last_close < low:
            return "INVALID", "close di bawah Bullish OB low"
        if low <= current_price <= high:
            return "TOUCHED", "price masuk ke Bullish OB"
        if current_price > high:
            return "FRESH", "price masih di atas OB"
    elif direction == "bearish":
        if last_close > high:
            return "INVALID", "close di atas Bearish OB high"
        if low <= current_price <= high:
            return "TOUCHED", "price masuk ke Bearish OB"
        if current_price < low:
            return "FRESH", "price masih di bawah OB"

    return "UNKNOWN", "status tidak terbaca"


def nearest_order_block(order_blocks, current_price, direction=None):
    obs = order_blocks or []
    if direction:
        obs = [x for x in obs if str(x.get("direction", "")).lower() == direction.lower()]
    if not obs:
        return None
    obs = sorted(obs, key=lambda x: min(abs(current_price - float(x["low"])), abs(current_price - float(x["high"]))))
    return obs[0]


def format_ob_alert(ob, current_price):
    status, reason = evaluate_ob_status(ob, current_price)
    icon = "🧱"
    return "\n".join([
        f"{icon} ORDER BLOCK — {status}",
        f"Type: {ob.get('type') or ob.get('direction') + ' OB'}",
        f"Zone: {float(ob.get('low')):.2f} - {float(ob.get('high')):.2f}",
        f"Current Price: {float(current_price):.2f}",
        f"Strength: {ob.get('strength', 'N/A')}",
        f"Reason: {ob.get('reason', reason)}",
        f"Invalidasi: {'close di bawah OB low ' + str(round(float(ob.get('low')), 2)) if str(ob.get('direction')).lower() == 'bullish' else 'close di atas OB high ' + str(round(float(ob.get('high')), 2))}",
    ])


def save_order_blocks(storage, order_blocks):
    saved = 0
    for ob in order_blocks:
        raw = json.dumps(ob, ensure_ascii=False)
        try:
            storage.execute(
                """
                INSERT INTO active_order_blocks
                (symbol, timeframe, direction, type, low, high, status, strength, reason, created_at, source_candle_time, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, source_candle_time)
                DO UPDATE SET
                    direction=excluded.direction,
                    type=excluded.type,
                    low=excluded.low,
                    high=excluded.high,
                    status=excluded.status,
                    strength=excluded.strength,
                    reason=excluded.reason,
                    raw_json=excluded.raw_json
                """,
                (
                    ob.get("symbol"),
                    ob.get("timeframe"),
                    ob.get("direction"),
                    ob.get("type"),
                    ob.get("low"),
                    ob.get("high"),
                    ob.get("status", "VALID"),
                    ob.get("strength", "MEDIUM"),
                    ob.get("reason", ""),
                    ob.get("created_at"),
                    ob.get("source_candle_time"),
                    raw,
                ),
            )
            saved += 1
        except Exception:
            pass
    return saved
