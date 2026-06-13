import sys
import sqlite3

# Analyze recent SL hits
conn = sqlite3.connect('/storage/emulated/0/Download/aplikasi/xauusd-scalping-bot/data/xauusd_bot.sqlite')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 10")
trades = cur.fetchall()

sl_count = 0
for t in trades:
    if t['status'] == 'CLOSED_LOSS' or t['result'] == 'LOSS':
        sl_count += 1
        print(f"SL HIT: {t['reason'][:30]}... - {t['direction']} at {t['created_at']}")

print(f"\nTotal SLs in last 10 trades: {sl_count}")
