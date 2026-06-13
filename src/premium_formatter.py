import datetime


def _fmt(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return "N/A"


def format_premium_signal(signal_data, poi_data, ai_note="Tidak divalidasi oleh AI.", ai_used=True):
    direction = signal_data.get('direction', 'NO_TRADE') if signal_data else 'NO_TRADE'
    source = "RULE ENGINE + AI ADVISOR" if ai_used else "RULE ENGINE"
    now_wib = (datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=7)).strftime("%H:%M WIB")
    if direction == 'NO_TRADE':
        return (
            f"📍 XAUUSD Update {now_wib}\n\n"
            f"Status: NO TRADE\n"
            f"Alasan: {signal_data.get('reason', 'Tunggu setup valid') if signal_data else 'Tunggu setup valid'}\n\n"
            f"Action:\nTunggu area pantau dan konfirmasi M5.\n\n"
            f"Source: {source}"
        )
    emoji = '🟢' if direction == 'BUY' else '🔴'
    title = 'BUY SETUP' if direction == 'BUY' else 'SELL SETUP'
    reason = signal_data.get('reason', '')
    
    # Bersihkan reason dari AI note ganda
    if "AI Review:" in reason:
        reason = reason.split("AI Review:")[0].strip()
    
    if ai_used and ai_note and ai_note != "Tidak divalidasi oleh AI.":
        note = str(ai_note).replace('AI Review:', '').replace('AI Note:', '').strip()
        if len(note) > 240:
            note = note[:240].rstrip() + '...'
    else:
        note = "Tidak tersedia."

    return (
        f"{emoji} XAUUSD {title}\n\n"
        f"Harga: {_fmt(signal_data.get('entry_low'))} - {_fmt(signal_data.get('entry_high'))}\n"
        f"SL: {_fmt(signal_data.get('sl'))}\n"
        f"TP1: {_fmt(signal_data.get('tp1'))}\n"
        f"TP2: {_fmt(signal_data.get('tp2'))}\n"
        f"Confidence: {signal_data.get('confidence', 0)}%\n\n"
        f"Alasan:\n{reason}\n\n"
        f"Status:\nEntry valid kalau harga masih dekat area pantau. Jangan kejar kalau sudah jauh.\n\n"
        f"AI Note:\n{note}\n\n"
        f"Source: {source}"
    )
