from src.formatter import setup_logger
logger = setup_logger("StructureEvents")


def process_and_alert_structure(storage, new_structure, symbol, current_price, bot_state=None):
    from src.telegram_notifier import send_telegram_message, telegram_is_configured
    sweep_type = new_structure.get('sweep_type')
    break_type = new_structure.get('break_type')
    conn = storage.get_connection(); cur = conn.cursor()
    try:
        if sweep_type:
            level = new_structure.get('swept_level')
            cur.execute("SELECT 1 FROM structure_events WHERE event_type IN ('SENTUH','SWEEP') AND level=? AND direction=? ORDER BY id DESC LIMIT 1", (level, sweep_type))
            if not cur.fetchone():
                side = 'Low' if sweep_type == 'bullish' else 'High'
                msg = (f"⚡ XAUUSD SENTUH {side}\n\n"
                       f"Level: {level}\nHarga: {current_price}\n\n"
                       f"Action:\nTunggu BREAK balik arah + close confirm.\n\nSource: ADAPTIVE EVENT WATCH")
                storage.save_structure_event('SENTUH', symbol, 'M5', level, current_price, sweep_type, new_structure)
                if telegram_is_configured(): send_telegram_message(msg)
        if break_type:
            level = new_structure.get('break_level')
            direction = 'bullish' if 'BULLISH' in str(break_type).upper() else 'bearish'
            cur.execute("SELECT 1 FROM structure_events WHERE event_type='BREAK' AND level=? AND direction=? ORDER BY id DESC LIMIT 1", (level, direction))
            if not cur.fetchone():
                if direction == 'bullish':
                    emoji, title, action = '📈', 'BOS BULLISH', 'WAIT RETEST BUY'
                    area = f"{float(level)-1.5:.2f} - {float(level)+0.5:.2f}" if level else 'N/A'
                    invalid = f"M5 close kuat di bawah {float(level)-1.5:.2f}" if level else 'N/A'
                else:
                    emoji, title, action = '📉', 'BOS BEARISH', 'WAIT RETEST SELL'
                    area = f"{float(level)-0.5:.2f} - {float(level)+1.5:.2f}" if level else 'N/A'
                    invalid = f"M5 close kuat di atas {float(level)+1.5:.2f}" if level else 'N/A'
                msg = (f"{emoji} XAUUSD {title}\n\n"
                       f"Level break: {level}\nHarga sekarang: {current_price}\n\n"
                       f"Artinya:\nStruktur M5 mulai {direction}.\n\n"
                       f"Action:\n{action}.\nTunggu pullback ke area {area}.\n\n"
                       f"Invalid:\n{invalid}")
                storage.save_structure_event('BREAK', symbol, 'M5', level, current_price, direction, new_structure)
                if bot_state is not None:
                    bot_state['retest_area'] = level
                    bot_state['retest_mode'] = 'WAIT_RETEST_BUY' if direction == 'bullish' else 'WAIT_RETEST_SELL'
                if telegram_is_configured(): send_telegram_message(msg)
    finally:
        conn.close()
