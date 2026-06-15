from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _f(candle: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(candle.get(key, default) or default)
    except Exception:
        return default


def _trend_is_bearish(ctx: Dict[str, Any]) -> bool:
    values = [
        str(ctx.get("htf_bias") or "").lower(),
        str(ctx.get("h1_bias") or "").lower(),
        str(ctx.get("h4_bias") or "").lower(),
        str(ctx.get("d1_bias") or "").lower(),
    ]
    bearish_count = sum(1 for v in values if v == "bearish")
    bullish_count = sum(1 for v in values if v == "bullish")
    return bearish_count >= 1 and bullish_count == 0


def evaluate_crt_h1_sell(ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
    """CRT H1 SELL.

    User rule:
    - Trade only with bearish trend.
    - Mark CRH/CRL from a red H1 candle.
    - The next H1 candle may sweep above CRH.
    - Valid rejection means the candle closes back inside CRH-CRL.
    - If the trigger candle is green, its close must not exceed 50% of the CRT range.
    """
    h1: List[Dict[str, Any]] = list(ctx.get("h1_candles") or [])
    if len(h1) < 2:
        return None
    if not _trend_is_bearish(ctx):
        return None

    crt = h1[-2]
    trigger = h1[-1]

    crt_open = _f(crt, "open")
    crt_close = _f(crt, "close")
    crh = _f(crt, "high")
    crl = _f(crt, "low")
    if not (crh > crl > 0):
        return None

    # CRT reference candle must be red for bearish setup.
    if not (crt_close < crt_open):
        return None

    trg_open = _f(trigger, "open")
    trg_close = _f(trigger, "close")
    trg_high = _f(trigger, "high")
    trigger_green = trg_close > trg_open

    midpoint = crl + ((crh - crl) / 2.0)

    swept_crh = trg_high > crh
    closed_inside_range = crl <= trg_close < crh
    close_not_above_50 = trg_close <= midpoint

    if not swept_crh:
        return None
    if not closed_inside_range:
        return None
    if trigger_green and not close_not_above_50:
        return None
    if not close_not_above_50:
        return None

    ctx["crt_h1"] = {
        "direction": "SELL",
        "crh": round(crh, 3),
        "crl": round(crl, 3),
        "midpoint": round(midpoint, 3),
        "crt_time": crt.get("open_time") or crt.get("time") or crt.get("timestamp"),
        "trigger_time": trigger.get("open_time") or trigger.get("time") or trigger.get("timestamp"),
        "trigger_green": trigger_green,
        "trigger_close": round(trg_close, 3),
        "trigger_high": round(trg_high, 3),
    }

    reason = (
        "CRT H1 SELL: trend bearish, candle H1 merah sebagai CRT, "
        "candle berikutnya sweep CRH lalu close balik ke dalam range dan tidak melewati 50% range."
    )
    return ("SELL", reason, "METHOD_CRT_H1_SELL", 88.0)
