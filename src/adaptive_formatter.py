from __future__ import annotations

from typing import Any, Dict, List


def format_adaptive_signal(signal: Dict[str, Any], current_price: float = 0) -> str:
    if not signal:
        return "🧠 ADAPTIVE BRAIN\nStatus: NO DATA\nSource: ADAPTIVE BRAIN"

    direction = signal.get('direction', 'NO_TRADE')
    if direction == 'NO_TRADE':
        # Add POI info for NO_TRADE
        poi_info = ""
        try:
            import sqlite3
            conn = sqlite3.connect("data/xauusd_bot.sqlite")
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute("SELECT * FROM poi_levels WHERE status = 'VALID' ORDER BY created_at DESC LIMIT 2")
            pois = c.fetchall()
            
            c.execute("SELECT zone_type, low, high, timeframe FROM supply_demand_zones WHERE status = 'VALID' ORDER BY created_at DESC LIMIT 2")
            zones = c.fetchall()
            
            if pois or zones:
                poi_info += "\n🗺️ **Peta Area (POI & Zones):**\n"
                for p in pois:
                    poi_info += f"- POI {p['poi_type']}: {p['low']:.2f} - {p['high']:.2f}\n"
                for z in zones:
                    tz = "Supply" if "SUPPLY" in z['zone_type'].upper() else "Demand"
                    poi_info += f"- {tz} {z['timeframe']}: {z['low']:.2f} - {z['high']:.2f}\n"
            conn.close()
        except Exception:
            pass

        return (
            "🧠 XAUUSD ADAPTIVE BRAIN\n"
            "Status: NO TRADE\n"
            f"Harga: {current_price or signal.get('current_price', 'N/A')}\n"
            f"Alasan: {signal.get('reason', 'Menunggu konfirmasi')}\n"
            "Action: Tunggu SENTUH + BREAK + close confirm.\n"
            f"{poi_info}"
            "Source: ADAPTIVE BRAIN"
        )

    entry_type = signal.get('entry_type') or 'MARKET'
    pending_price = signal.get('pending_price')
    signal_tf = (signal.get('signal_timeframe') or 'M5').upper()
    signal_class = signal.get('signal_class') or ('M1_AGGRESSIVE' if signal_tf == 'M1' else 'M5_RECOMMENDED')
    if signal_tf == 'M1':
        tf_header = "⚠️ M1 SIGNAL - AGRESIF"
        tf_warning = "Warning: ini signal M1. Kelola lot dengan bijak."
    elif signal_tf == 'M5':
        tf_header = "✅ M5 SIGNAL - REKOMENDASI UTAMA"
        tf_warning = "Catatan: signal M5 lebih kuat dan jadi rekomendasi utama."
    elif signal_tf == 'H4':
        tf_header = "🟣 CRT H4 SIGNAL - USER METHOD"
        tf_warning = "Catatan: CRT H4 tanpa filter bias. Ikuti pending layer dan risk kecil."
    elif signal_tf == 'D1':
        tf_header = "🟠 CRT D1 SIGNAL - USER METHOD"
        tf_warning = "Catatan: CRT D1 tanpa filter bias. Ikuti pending layer dan risk kecil."
    elif signal_tf == 'H1':
        tf_header = "🔵 H1 BREAK SIGNAL - USER METHOD"
        tf_warning = "Catatan: H1 Break tanpa averaging. Pending order saja."
    else:
        tf_header = f"📌 {signal_tf} SIGNAL"
        tf_warning = "Kelola lot dengan bijak."
    emoji = "🟢" if direction == 'BUY' else "🔴"
    if entry_type in ('BUY_LIMIT', 'SELL_LIMIT'):
        avg_plan = signal.get('averaging_plan') or {}
        avg_lines = ""
        if signal.get('averaging_enabled') and avg_plan.get('layers'):
            rows = []
            for item in avg_plan.get('layers', []):
                rows.append(f"L{item.get('layer')}: {item.get('price')}")
            avg_lines = (
                "\nAveraging: ON controlled same-lot\n"
                f"Layers: {' | '.join(rows)}\n"
                f"Average Entry: {avg_plan.get('average_entry')}\n"
                f"Max Risk: {avg_plan.get('max_total_risk_percent', 1.0)}% total\n"
            )
        return (
            f"{tf_header}\n"
            f"{emoji} XAUUSD {entry_type} - ADAPTIVE BRAIN\n"
            f"Harga sekarang: {current_price or signal.get('current_price', 'N/A')}\n"
            f"Pending Entry 1: {pending_price}\n"
            f"Entry Area: {signal.get('entry_low')} - {signal.get('entry_high')}\n"
            f"SL: {signal.get('sl')}\n"
            f"TP1: {signal.get('tp1')}\n"
            f"TP2: {signal.get('tp2')}\n"
            f"Expired: {signal.get('pending_expire_time') or 'N/A'}\n"
            f"Reference: {signal.get('reference_level') or '-'}\n"
            f"{avg_lines}"
            "Rule: pending limit retest + controlled averaging, TP1 protect, TP2 final.\n"
            f"Confidence: {signal.get('confidence')}%\n"
            f"Pattern: {signal.get('pattern_key', '-')}\n"
            f"Alasan: {signal.get('reason', '-')}\n\n"
            f"Warning: {tf_warning}\n"
            "Action:\nPasang layer sesuai plan. Jangan martingale. Batal kalau expired atau struktur berubah.\n"
            "Source: ADAPTIVE BRAIN"
        )

    return (
        f"{tf_header}\n"
        f"{emoji} XAUUSD {direction} - ADAPTIVE BRAIN\n"
        f"Harga: {current_price or signal.get('current_price', 'N/A')}\n"
        f"Entry: {signal.get('entry_low')} - {signal.get('entry_high')}\n"
        f"SL: {signal.get('sl')}\n"
        f"TP1: {signal.get('tp1')}\n"
        f"TP2: {signal.get('tp2')}\n"
        "Rule: TP1=1R protect, TP2=2R final.\n"
        f"Confidence: {signal.get('confidence')}%\n"
        f"Pattern: {signal.get('pattern_key', '-')}\n"
        f"Alasan: {signal.get('reason', '-')}\n"
        f"Warning: {tf_warning}\n\n"
        "Learning:\n"
        "TP1 dihitung PARTIAL_WIN, TP2 dihitung WIN.\n"
        "Source: ADAPTIVE BRAIN"
    )


def format_recent_events(events: List[Dict[str, Any]]) -> str:
    if not events:
        return "RECENT EVENTS:\n- Belum ada event adaptive brain."
    lines = ["RECENT EVENTS:"]
    for ev in events[:20]:
        level = ev.get('level')
        price = ev.get('price')
        level_txt = f" at {float(level):.3f}" if level is not None else ""
        price_txt = f" | price {float(price):.3f}" if price is not None else ""
        lines.append(f"- {ev.get('event_type')} {ev.get('direction') or ''}{level_txt}{price_txt}")
    return "\n".join(lines)


def format_brain_status(memory, symbol: str = 'XAU/USD') -> str:
    events = memory.recent_events(symbol, 8)
    patterns = memory.recent_patterns(8)
    active = memory.active_signal()
    lines = ["🧠 BRAIN STATUS", "Source: LOCAL DB"]
    if active:
        et = active.get('entry_type') or 'MARKET'
        pp = active.get('pending_price')
        if et in ('BUY_LIMIT', 'SELL_LIMIT'):
            lines.append(f"Active Signal: #{active.get('id')} [{active.get('signal_timeframe') or 'M5'}] {et} {active.get('status')} @ {pp}")
        else:
            lines.append(f"Active Signal: #{active.get('id')} [{active.get('signal_timeframe') or 'M5'}] {active.get('direction')} {active.get('status')}")
    else:
        lines.append("Active Signal: none")
    lines.append("\nRecent Events:")
    if events:
        for e in events[:6]:
            lines.append(f"- {e.get('event_type')} {e.get('direction') or ''} {e.get('level') or ''}")
    else:
        lines.append("- none")
    lines.append("\nLearned Patterns:")
    if patterns:
        for p in patterns[:6]:
            lines.append(f"- {p.get('pattern_key')}: score {p.get('score')} | {p.get('wins')}W/{p.get('losses')}L")
    else:
        lines.append("- none")
    return "\n".join(lines)
