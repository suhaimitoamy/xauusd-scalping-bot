import sys, os, time, sqlite3

def check_for_new_sl():
    conn = sqlite3.connect('data/xauusd_bot.sqlite')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Check for un-reviewed SLs
    cur.execute("""
        SELECT b.id as bt_id, s.id, s.signal_class, s.result 
        FROM brain_training b
        JOIN signals s ON b.signal_id = s.id
        WHERE s.status LIKE 'CLOSED%' AND s.result = 'LOSS'
        AND b.raw_json LIKE '%"pending_ai"%'
        ORDER BY b.id ASC LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def main():
    print("🔭 Antigravity SL Monitor started...")
    while True:
        try:
            sl_trade = check_for_new_sl()
            if sl_trade:
                msg = f"[!] BINGO! New SL detected: #{sl_trade['id']} - {sl_trade['signal_class']}\nWake up Antigravity to fix this method!"
                print(msg)
                
                # Send to Telegram
                from src.telegram_notifier import send_telegram_message
                send_telegram_message(msg)
                
                # Update DB so we don't alert the same SL again
                conn = sqlite3.connect('data/xauusd_bot.sqlite')
                conn.execute(
                    "UPDATE brain_training SET raw_json = REPLACE(raw_json, '\"pending_ai\"', '\"pending_ai_notified\"') WHERE id = ?", 
                    (sl_trade['bt_id'],)
                )
                conn.commit()
                conn.close()
                
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(5)

if __name__ == "__main__":
    main()
