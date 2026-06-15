from __future__ import annotations

from typing import Any, Dict, Tuple


def _to_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def entry_price(signal: Dict[str, Any]) -> float | None:
    pending = _to_float(signal.get("pending_price"))
    if pending is not None:
        return pending
    low = _to_float(signal.get("entry_low"))
    high = _to_float(signal.get("entry_high"))
    if low is not None and high is not None:
        return (low + high) / 2.0
    return _to_float(signal.get("entry"))


def calculate_rr(signal: Dict[str, Any]) -> Dict[str, Any]:
    direction = str(signal.get("direction") or "").upper()
    entry = entry_price(signal)
    sl = _to_float(signal.get("sl"))
    tp2 = _to_float(signal.get("tp2"))

    result = {
        "valid": False,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp2": tp2,
        "risk": None,
        "reward": None,
        "rr": 0.0,
        "reason": "RR data incomplete",
    }

    if direction not in {"BUY", "SELL"}:
        result["reason"] = "Direction invalid"
        return result
    if entry is None or sl is None or tp2 is None:
        return result

    if direction == "BUY":
        risk = entry - sl
        reward = tp2 - entry
    else:
        risk = sl - entry
        reward = entry - tp2

    result["risk"] = round(risk, 5)
    result["reward"] = round(reward, 5)

    if risk <= 0:
        result["reason"] = f"Risk invalid: {risk:.3f}"
        return result
    if reward <= 0:
        result["reason"] = f"Reward invalid: {reward:.3f}"
        return result

    rr = reward / risk
    result["rr"] = round(rr, 4)
    result["valid"] = True
    result["reason"] = "OK"
    return result


def validate_rr(signal: Dict[str, Any], min_rr: float = 2.0) -> Tuple[bool, str, Dict[str, Any]]:
    rr = calculate_rr(signal)
    if not rr["valid"]:
        return False, f"RR_INVALID: {rr['reason']}", rr
    if rr["rr"] < float(min_rr):
        return False, f"RR_INVALID: RR {rr['rr']:.2f} < {float(min_rr):.2f}", rr
    return True, f"RR_OK: {rr['rr']:.2f}", rr


def attach_rr(signal: Dict[str, Any]) -> Dict[str, Any]:
    rr = calculate_rr(signal)
    signal["rr"] = rr.get("rr")
    signal["risk_points"] = rr.get("risk")
    signal["reward_points"] = rr.get("reward")
    signal["rr_valid"] = rr.get("valid")
    return signal
