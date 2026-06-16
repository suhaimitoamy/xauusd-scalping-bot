"""
Advanced market structure analysis for XAUUSD Scalping Signal Bot.

Fokus file ini:
- BOS / MSS / CHOCH valid atau invalid
- Support / resistance break valid atau invalid
- Sweep + reclaim valid atau invalid
- Trend invalidation:
  bullish invalid jika Higher Low jebol
  bearish invalid jika Lower High jebol
- Telegram alert format market structure
"""
import os
import time

_LAST_STRUCTURE_ALERTS = {}


def _v(candle, key, default=0.0):
    try:
        return float(candle.get(key, default) or default)
    except Exception:
        return default


def _fmt(value):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def _candle_power(candle):
    open_ = _v(candle, "open")
    high = _v(candle, "high")
    low = _v(candle, "low")
    close = _v(candle, "close")

    body_top = max(open_, close)
    body_bottom = min(open_, close)
    body = max(abs(close - open_), 0.01)
    full_range = max(high - low, 0.01)

    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "body": body,
        "range": full_range,
        "body_ratio": body / full_range,
        "upper_wick": high - body_top,
        "lower_wick": body_bottom - low,
        "bullish": close > open_,
        "bearish": close < open_,
    }


def get_swings(candles, left=2, right=2):
    highs = []
    lows = []

    if not candles:
        return highs, lows

    for i in range(left, len(candles) - right):
        is_high = True
        is_low = True

        for j in range(1, left + 1):
            if _v(candles[i - j], "high") >= _v(candles[i], "high"):
                is_high = False
            if _v(candles[i - j], "low") <= _v(candles[i], "low"):
                is_low = False

        for j in range(1, right + 1):
            if _v(candles[i + j], "high") >= _v(candles[i], "high"):
                is_high = False
            if _v(candles[i + j], "low") <= _v(candles[i], "low"):
                is_low = False

        if is_high:
            highs.append(candles[i])
        if is_low:
            lows.append(candles[i])

    return highs, lows


def calculate_bias(candles):
    if len(candles or []) < 10:
        return "neutral"

    highs, lows = get_swings(candles)

    if len(highs) >= 2 and len(lows) >= 2:
        h2, h1 = _v(highs[-2], "high"), _v(highs[-1], "high")
        l2, l1 = _v(lows[-2], "low"), _v(lows[-1], "low")

        hh = h1 > h2
        hl = l1 > l2
        lh = h1 < h2
        ll = l1 < l2

        if hh and hl:
            return "bullish"
        if lh and ll:
            return "bearish"
        if hh and ll:
            return "expanding"
        if lh and hl:
            return "choppy"

    closes = [_v(c, "close") for c in candles[-5:]]
    avg_close = sum(closes) / max(len(closes), 1)
    return "bullish" if _v(candles[-1], "close") > avg_close else "bearish"


def is_choppy(candles):
    if len(candles or []) < 5:
        return False

    weak_count = 0
    for c in candles[-5:]:
        body = abs(_v(c, "open") - _v(c, "close"))
        rng = max(_v(c, "high") - _v(c, "low"), 0.01)
        if body / rng < 0.35:
            weak_count += 1

    return weak_count >= 3


def _atr_like(candles, period=14):
    recent = candles[-period:] if len(candles or []) >= period else candles
    ranges = [max(_v(c, "high") - _v(c, "low"), 0.0) for c in recent]
    return sum(ranges) / len(ranges) if ranges else 0.0


def _trend_invalidation(highs, lows, m15_bias, h1_bias):
    bias = h1_bias if h1_bias in ("bullish", "bearish") else m15_bias

    if bias == "bullish" and len(lows) >= 2:
        return _v(lows[-1], "low"), "Higher Low"

    if bias == "bearish" and len(highs) >= 2:
        return _v(highs[-1], "high"), "Lower High"

    return None, "N/A"


def _validate_break(direction, level, candle_power, atr_value, choppy, m15_bias, h1_bias):
    close = candle_power["close"]
    high = candle_power["high"]
    low = candle_power["low"]
    body_ratio = candle_power["body_ratio"]

    threshold = max(atr_value * 0.12, 0.30)
    reasons = []

    if direction == "bullish":
        close_distance = close - level
        wick_only = high > level and close <= level
        body_ok = candle_power["bullish"]
        htf_against = m15_bias == "bearish" and h1_bias == "bearish"
    else:
        close_distance = level - close
        wick_only = low < level and close >= level
        body_ok = candle_power["bearish"]
        htf_against = m15_bias == "bullish" and h1_bias == "bullish"

    valid = (
        close_distance >= threshold
        and body_ratio >= 0.45
        and body_ok
        and not choppy
    )

    if valid:
        reasons.append("close menembus level dengan body jelas")
    if wick_only:
        reasons.append("hanya wick, close balik ke dalam level")
    if close_distance < threshold:
        reasons.append("jarak close dari level belum cukup")
    if body_ratio < 0.45:
        reasons.append("body candle lemah")
    if choppy:
        reasons.append("market choppy")
    if htf_against:
        reasons.append("melawan bias M15 dan H1")

    return valid, close_distance, reasons[:4]


def _build_telegram_message(result):
    ev = result.get("structure_event") or {}
    if not ev:
        return ""

    status = ev.get("status", "INVALID")
    icon = "✅" if status == "VALID" else "⚠️"

    lines = [
        f"{icon} MARKET STRUCTURE — {status}",
        f"Event: {ev.get('message', ev.get('type', 'STRUCTURE'))}",
        f"Level: {_fmt(ev.get('level'))}",
        f"Current Price: {_fmt(result.get('current_price'))}",
        f"Support: {_fmt(result.get('nearest_support'))}",
        f"Resistance: {_fmt(result.get('nearest_resistance'))}",
        f"M15 Bias: {result.get('m15_bias')}",
        f"H1 Bias: {result.get('h1_bias')}",
        f"Phase: {result.get('trend')}",
        f"Invalidasi: {result.get('invalidation_label')} di {_fmt(result.get('invalidation_level'))}",
    ]

    if ev.get("close_distance") is not None:
        lines.append(f"Close Distance: {_fmt(ev.get('close_distance'))}")

    reasons = ev.get("reasons") or []
    if reasons:
        lines.append("Alasan: " + "; ".join(reasons))

    lines.append(f"Retest Mode: {result.get('retest_mode')}")

    return "\n".join(lines)


def _send_telegram_structure_alert(result):
    if os.getenv("STRUCTURE_TELEGRAM_ALERTS", "true").lower() in ("false", "0", "off", "no"):
        return False

    ev = result.get("structure_event") or {}
    if not ev:
        return False

    level = ev.get("level") or 0
    key = f"{ev.get('type')}:{ev.get('status')}:{round(float(level), 2)}"
    cooldown = int(os.getenv("STRUCTURE_ALERT_COOLDOWN_SECONDS", "900") or 900)
    now = time.time()

    if now - _LAST_STRUCTURE_ALERTS.get(key, 0) < cooldown:
        return False

    message = _build_telegram_message(result)
    if not message:
        return False

    try:
        from src.telegram_notifier import send_telegram_message, telegram_is_configured

        if not telegram_is_configured():
            return False

        ok = send_telegram_message(message)
        if ok:
            _LAST_STRUCTURE_ALERTS[key] = now
        return ok
    except Exception:
        return False


def analyze_structure(m5_candles, m15_candles, h1_candles):
    result = {
        "recent_swing_highs": [],
        "recent_swing_lows": [],
        "nearest_resistance": None,
        "nearest_support": None,
        "liquidity_above": None,
        "liquidity_below": None,
        "sweep_type": None,
        "swept_level": None,
        "sweep_extreme": None,
        "reclaim_level": None,
        "reclaim_valid": False,
        "break_type": None,
        "break_level": None,
        "break_valid": False,
        "break_status": None,
        "break_reason": [],
        "m5_momentum": "neutral",
        "m15_bias": "neutral",
        "h1_bias": "neutral",
        "middle_of_range": False,
        "choppy": False,
        "atr": 0.0,
        "is_extreme_volatility": False,
        "trend": "RANGING",
        "retest_mode": "NONE",
        "structure_event": None,
        "telegram_alert": None,
        "current_price": None,
        "invalidation_level": None,
        "invalidation_label": "N/A",
        "trend_invalidated": False,
    }

    if len(m5_candles or []) < 10:
        return result

    m15_candles = m15_candles or []
    h1_candles = h1_candles or []

    m15_bias = calculate_bias(m15_candles)
    h1_bias = calculate_bias(h1_candles)

    highs, lows = get_swings(m5_candles[:-1])
    last = m5_candles[-1]
    power = _candle_power(last)

    current_price = power["close"]
    atr_value = _atr_like(m5_candles)
    choppy = is_choppy(m5_candles)

    result["current_price"] = current_price
    result["recent_swing_highs"] = [_v(h, "high") for h in highs]
    result["recent_swing_lows"] = [_v(l, "low") for l in lows]
    result["m15_bias"] = m15_bias
    result["h1_bias"] = h1_bias
    result["choppy"] = choppy
    result["atr"] = atr_value
    result["is_extreme_volatility"] = atr_value > 15.0

    support_candidates = [_v(l, "low") for l in lows if _v(l, "low") < current_price]
    resistance_candidates = [_v(h, "high") for h in highs if _v(h, "high") > current_price]

    result["nearest_support"] = max(support_candidates) if support_candidates else None
    result["nearest_resistance"] = min(resistance_candidates) if resistance_candidates else None
    result["liquidity_below"] = result["nearest_support"]
    result["liquidity_above"] = result["nearest_resistance"]

    invalidation_level, invalidation_label = _trend_invalidation(highs, lows, m15_bias, h1_bias)
    result["invalidation_level"] = invalidation_level
    result["invalidation_label"] = invalidation_label

    main_bias = h1_bias if h1_bias in ("bullish", "bearish") else m15_bias

    if invalidation_level is not None:
        bullish_invalid = main_bias == "bullish" and current_price < invalidation_level
        bearish_invalid = main_bias == "bearish" and current_price > invalidation_level

        if bullish_invalid or bearish_invalid:
            result["trend_invalidated"] = True
            result["structure_event"] = {
                "type": "TREND_INVALIDATION",
                "message": f"Trend {main_bias} invalid: {invalidation_label} jebol",
                "direction": "bearish" if bullish_invalid else "bullish",
                "level": invalidation_level,
                "valid": True,
                "status": "VALID",
                "reasons": [f"close melewati level invalidasi {invalidation_label}"],
            }

    if power["body_ratio"] >= 0.5:
        if power["bullish"]:
            result["m5_momentum"] = "bullish"
        elif power["bearish"]:
            result["m5_momentum"] = "bearish"

    if result["nearest_support"] and result["nearest_resistance"]:
        market_range = result["nearest_resistance"] - result["nearest_support"]
        position = (current_price - result["nearest_support"]) / market_range if market_range > 0 else 0
        result["middle_of_range"] = 0.4 <= position <= 0.6

    if lows and not result["structure_event"]:
        recent_low = _v(lows[-1], "low")
        if power["low"] < recent_low and power["close"] > recent_low:
            reclaim_valid = power["bullish"] and power["lower_wick"] >= power["body"] * 0.5 and not choppy
            result["sweep_type"] = "bullish"
            result["swept_level"] = recent_low
            result["sweep_extreme"] = power["low"]
            result["reclaim_level"] = power["close"]
            result["reclaim_valid"] = reclaim_valid
            result["structure_event"] = {
                "type": "SUPPORT_SWEEP_RECLAIM",
                "message": "Support disweep lalu reclaim: " + ("VALID" if reclaim_valid else "INVALID"),
                "direction": "bullish",
                "level": recent_low,
                "valid": reclaim_valid,
                "status": "VALID" if reclaim_valid else "INVALID",
                "reasons": ["close kembali di atas support"] if reclaim_valid else ["reclaim lemah atau market choppy"],
            }

    if highs and not result["structure_event"]:
        recent_high = _v(highs[-1], "high")
        if power["high"] > recent_high and power["close"] < recent_high:
            reclaim_valid = power["bearish"] and power["upper_wick"] >= power["body"] * 0.5 and not choppy
            result["sweep_type"] = "bearish"
            result["swept_level"] = recent_high
            result["sweep_extreme"] = power["high"]
            result["reclaim_level"] = power["close"]
            result["reclaim_valid"] = reclaim_valid
            result["structure_event"] = {
                "type": "RESISTANCE_SWEEP_RECLAIM",
                "message": "Resistance disweep lalu reclaim: " + ("VALID" if reclaim_valid else "INVALID"),
                "direction": "bearish",
                "level": recent_high,
                "valid": reclaim_valid,
                "status": "VALID" if reclaim_valid else "INVALID",
                "reasons": ["close kembali di bawah resistance"] if reclaim_valid else ["reclaim lemah atau market choppy"],
            }

    if highs:
        break_level = _v(highs[-1], "high")
        if power["close"] > break_level:
            valid, close_distance, reasons = _validate_break(
                "bullish", break_level, power, atr_value, choppy, m15_bias, h1_bias
            )
            is_mss = m15_bias == "bearish" or h1_bias == "bearish"

            result["break_type"] = "MSS_BULLISH" if is_mss else "BOS_BULLISH"
            result["break_level"] = break_level
            result["break_valid"] = valid
            result["break_status"] = "VALID" if valid else "INVALID"
            result["break_reason"] = reasons

            label = "CHOCH/MSS bullish" if is_mss else "Resistance di-break"
            result["structure_event"] = {
                "type": result["break_type"],
                "message": f"{label}: {result['break_status']}",
                "direction": "bullish",
                "level": break_level,
                "valid": valid,
                "status": result["break_status"],
                "close_distance": close_distance,
                "reasons": reasons,
            }

    if lows and not result["break_type"]:
        break_level = _v(lows[-1], "low")
        if power["close"] < break_level:
            valid, close_distance, reasons = _validate_break(
                "bearish", break_level, power, atr_value, choppy, m15_bias, h1_bias
            )
            is_mss = m15_bias == "bullish" or h1_bias == "bullish"

            result["break_type"] = "MSS_BEARISH" if is_mss else "BOS_BEARISH"
            result["break_level"] = break_level
            result["break_valid"] = valid
            result["break_status"] = "VALID" if valid else "INVALID"
            result["break_reason"] = reasons

            label = "CHOCH/MSS bearish" if is_mss else "Support di-break"
            result["structure_event"] = {
                "type": result["break_type"],
                "message": f"{label}: {result['break_status']}",
                "direction": "bearish",
                "level": break_level,
                "valid": valid,
                "status": result["break_status"],
                "close_distance": close_distance,
                "reasons": reasons,
            }

    if result["trend_invalidated"]:
        result["trend"] = "TREND_INVALIDATED"
    elif result["break_type"] and result["break_valid"]:
        result["trend"] = "EXPANSION"
    elif result["break_type"] and not result["break_valid"]:
        result["trend"] = "FAKE_BREAK"
    elif result["sweep_type"] and result["reclaim_valid"]:
        result["trend"] = "LIQUIDITY_SWEEP_RECLAIM"
    elif choppy:
        result["trend"] = "CHOPPY"
    elif result["middle_of_range"]:
        result["trend"] = "RANGING"
    elif main_bias in ("bullish", "bearish"):
        result["trend"] = "TRENDING"
    else:
        result["trend"] = "RANGING"

    if result["break_type"]:
        if result["break_valid"]:
            distance = abs(current_price - result["break_level"])
            if distance > max(atr_value * 0.75, 3.0):
                result["retest_mode"] = f"WAIT_PULLBACK_TO_{_fmt(result['break_level'])}"
            else:
                result["retest_mode"] = f"ACTIVE_RETEST_{result['break_type']}"
        else:
            result["retest_mode"] = f"NO_RETEST_INVALID_BREAK_{_fmt(result['break_level'])}"
    else:
        result["retest_mode"] = "NONE"

    if result["structure_event"]:
        result["telegram_alert"] = _build_telegram_message(result)
        _send_telegram_structure_alert(result)

    return result
