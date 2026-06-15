from __future__ import annotations

from typing import Any, Dict


def _fmt(value, default="-"):
    if value is None or value == "":
        return default
    try:
        if isinstance(value, float):
            return f"{value:.3f}"
    except Exception:
        pass
    return str(value)


def _base_lines(signal: Dict[str, Any], current_price: Any) -> list[str]:
    tf = (signal.get("signal_timeframe") or "M5").upper()
    method = signal.get("pattern_key") or signal.get("signal_class") or "-"
    direction = (signal.get("direction") or "-").upper()
    entry_type = signal.get("entry_type") or "MARKET"
    avg = signal.get("average_entry")
    lines = [
        f"XAUUSD [{tf}] {direction}",
        f"Method: {method}",
        f"Entry Type: {entry_type}",
        f"Current: {_fmt(current_price)}",
        f"Entry Area: {_fmt(signal.get('entry_low'))} - {_fmt(signal.get('entry_high'))}",
    ]
    if signal.get("pending_price") is not None:
        lines.append(f"Pending Price: {_fmt(signal.get('pending_price'))}")
    if avg is not None:
        lines.append(f"Average Entry: {_fmt(avg)}")
    lines.extend([
        f"SL: {_fmt(signal.get('sl'))}",
        f"TP1 Protect: {_fmt(signal.get('tp1'))}",
        f"TP2 Final: {_fmt(signal.get('tp2'))}",
    ])
    if signal.get("averaging_enabled"):
        plan = signal.get("averaging_plan") or {}
        layers = plan.get("layers") or []
        if layers:
            layer_text = " | ".join([f"L{x.get('layer')}:{_fmt(x.get('price'))}" for x in layers])
            lines.append(f"Averaging: ON controlled same-lot ({layer_text})")
    return lines


def format_trade_event(event_type: str, signal: Dict[str, Any], current_price: Any) -> str:
    event_type = str(event_type or "").upper()
    if event_type == "ENTRY_FILLED":
        title = "✅ ENTRY FILLED"
        status = "Pending tersentuh, trade sekarang ACTIVE."
    elif event_type == "TP1_HIT":
        title = "🎯 TP1 HIT — PROTECTED"
        status = "TP1 kena. SL digeser ke BE/protected. Belum final; target utama tetap TP2."
    elif event_type == "TP2_HIT":
        title = "🏁 TP2 HIT — FINAL WIN"
        status = "TP2 kena. Trade selesai sebagai WIN."
    elif event_type == "TP3_HIT":
        title = "🏆 TP3 HIT — FULL WIN"
        status = "TP3 kena. Trade selesai sebagai FULL WIN."
    elif event_type == "SL_HIT":
        title = "🛑 SL HIT — LOSS"
        status = "SL kena sebelum TP1. Trade selesai sebagai LOSS."
    elif event_type == "PROTECTED":
        title = "🛡️ BE HIT — PARTIAL WIN"
        status = "Harga balik ke BE setelah TP1. Trade selesai sebagai PARTIAL_WIN."
    elif event_type == "EXPIRED":
        title = "⏳ PENDING EXPIRED"
        status = "Pending order expired. Trade tidak jadi aktif."
    elif event_type == "INVALIDATED":
        title = "⚠️ SIGNAL INVALIDATED"
        status = "Struktur berubah. Sinyal dibatalkan."
    else:
        title = f"📌 {event_type}"
        status = "Update trade."

    lines = [title, ""]
    lines.extend(_base_lines(signal, current_price))
    lines.extend(["", f"Status: {status}"])
    reason = signal.get("reason")
    if reason:
        lines.append(f"Reason: {reason}")
    lines.append("Source: XAUUSD BOT")
    return "\n".join(lines)
