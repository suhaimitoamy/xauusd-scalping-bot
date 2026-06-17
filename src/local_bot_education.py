"""
Local bot-only Telegram education replies.

Tujuan:
- Tidak memakai AI.
- Menjawab pertanyaan edukasi dari data signal terakhir.
- Follow-up seperti "kenapa" dijawab dari konteks signal terakhir.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


FOLLOWUP_WORDS = {
    "kenapa", "why", "alasan", "alasannya", "kok", "gimana", "bagaimana",
    "jelaskan", "jelasin", "jelasinn", "detail", "detailnya",
}

BUY_SELL_WORDS = {
    "buy", "sell", "beli", "jual", "enaknya", "arah", "entry", "posisi",
}


def _fmt(value, nd=3):
    if value is None or value == "":
        return "N/A"
    try:
        return f"{float(value):.{nd}f}"
    except Exception:
        return str(value)


def _parse_raw(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("raw_context_json") or "{}"
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _latest_signal(storage, symbol="XAU/USD") -> Optional[Dict[str, Any]]:
    rows = storage.fetchall(
        """
        SELECT * FROM signals
        WHERE symbol = ?
          AND direction IN ('BUY','SELL')
        ORDER BY id DESC
        LIMIT 1
        """,
        (symbol,),
    )
    return rows[0] if rows else None


def _latest_price(storage, symbol="XAU/USD"):
    try:
        rows = storage.fetchall(
            "SELECT price FROM ticks WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,),
        )
        if rows:
            return rows[0].get("price")
    except Exception:
        pass
    try:
        rows = storage.fetchall(
            """
            SELECT close FROM candles
            WHERE symbol=? AND is_closed=1
            ORDER BY open_time DESC LIMIT 1
            """,
            (symbol,),
        )
        if rows:
            return rows[0].get("close")
    except Exception:
        pass
    return None


def _nearest_zone(storage, table, symbol, zone_col=None):
    try:
        if zone_col:
            rows = storage.fetchall(
                f"""
                SELECT * FROM {table}
                WHERE symbol=?
                ORDER BY id DESC LIMIT 1
                """,
                (symbol,),
            )
        else:
            rows = storage.fetchall(
                f"""
                SELECT * FROM {table}
                WHERE symbol=?
                ORDER BY id DESC LIMIT 1
                """,
                (symbol,),
            )
        return rows[0] if rows else None
    except Exception:
        return None


def _question_type(text: str) -> str:
    t = (text or "").lower().strip()
    words = set(t.replace("?", " ").replace(",", " ").split())

    if words & FOLLOWUP_WORDS:
        return "WHY"
    if words & BUY_SELL_WORDS:
        return "BUYSELL"
    return "GENERAL"


def build_signal_education(storage, symbol="XAU/USD", question: str = "") -> str:
    signal = _latest_signal(storage, symbol)
    price = _latest_price(storage, symbol)

    if not signal:
        return "\n".join([
            "🤖 Dijawab oleh Bot Lokal",
            "Source: BOT DATA ONLY",
            "",
            "Belum ada signal BUY/SELL terakhir yang bisa dijelaskan.",
        ])

    raw = _parse_raw(signal)
    ctx = raw.get("brain_context") or raw.get("context") or {}
    pattern = raw.get("pattern_key") or signal.get("pattern_key") or ctx.get("pattern_key") or "N/A"

    direction = signal.get("direction")
    entry_low = signal.get("entry_low")
    entry_high = signal.get("entry_high")
    sl = signal.get("sl")
    tp1 = signal.get("tp1")
    tp2 = signal.get("tp2")
    invalid = signal.get("invalid_level") or sl
    reason = signal.get("reason") or raw.get("reason") or "Signal dibuat berdasarkan rule bot."

    m15_bias = ctx.get("m15_bias") or "N/A"
    h1_bias = ctx.get("h1_bias") or "N/A"
    atr = ctx.get("atr")
    momentum = ctx.get("momentum") or "N/A"
    choppy = ctx.get("choppy")
    signal_tf = signal.get("signal_timeframe") or raw.get("signal_timeframe") or "N/A"
    signal_class = signal.get("signal_class") or raw.get("signal_class") or "N/A"

    supply = _nearest_zone(storage, "supply_demand_zones", symbol)
    ob = _nearest_zone(storage, "active_order_blocks", symbol)
    fvg = _nearest_zone(storage, "active_fvgs", symbol)

    lines = [
        "🤖 Dijawab oleh Bot Lokal",
        "Source: BOT DATA ONLY",
        "",
        "📘 EDUKASI SIGNAL",
        "",
        f"Rekomendasi: {direction}",
        f"Current Price: {_fmt(price)}",
        f"Entry: {_fmt(entry_low)} - {_fmt(entry_high)}",
        f"SL: {_fmt(sl)}",
        f"TP1: {_fmt(tp1)}",
        f"TP2: {_fmt(tp2)}",
        f"Invalidasi: {_fmt(invalid)}",
        f"Pattern: {pattern}",
        f"Timeframe: {signal_tf}",
        f"Class: {signal_class}",
        "",
        "Alasan:",
        f"1. {reason}",
        f"2. Bias M15: {m15_bias} | Bias H1: {h1_bias}",
        f"3. Momentum M5: {momentum} | ATR: {_fmt(atr)} | Choppy: {choppy}",
    ]

    if direction == "SELL":
        lines.append("4. Setup SELL dianggap valid selama harga tidak menembus SL / invalidasi.")
        lines.append("5. TP diarahkan ke area bawah sesuai target bot.")
    elif direction == "BUY":
        lines.append("4. Setup BUY dianggap valid selama harga tidak menembus SL / invalidasi.")
        lines.append("5. TP diarahkan ke area atas sesuai target bot.")

    if supply:
        ztype = supply.get("zone_type") or supply.get("type") or "zone"
        low = supply.get("low")
        high = supply.get("high")
        lines.append(f"6. Zone terakhir: {ztype} {_fmt(low)} - {_fmt(high)}")

    if ob:
        ob_type = ob.get("type") or ob.get("direction") or "OB"
        lines.append(f"7. OB terakhir: {ob_type} {_fmt(ob.get('low'))} - {_fmt(ob.get('high'))}")

    if fvg:
        fvg_type = fvg.get("direction") or "FVG"
        lines.append(f"8. FVG terakhir: {fvg_type} {_fmt(fvg.get('low'))} - {_fmt(fvg.get('high'))}")

    lines.extend([
        "",
        "Status:",
        f"{direction} masih valid selama harga tidak close kuat melewati invalidasi {_fmt(invalid)}.",
    ])

    return "\n".join(lines)


def answer_education_message(text: str, storage, symbol="XAU/USD") -> str:
    qtype = _question_type(text)

    if qtype in ("WHY", "BUYSELL", "GENERAL"):
        return build_signal_education(storage, symbol, text)

    return build_signal_education(storage, symbol, text)
