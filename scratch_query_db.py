import sqlite3
import json

conn = sqlite3.connect('/storage/emulated/0/Download/aplikasi/xauusd-scalping-bot/data/xauusd_bot.sqlite')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get recent trades
cur.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 5")
trades = [dict(r) for r in cur.fetchall()]
print("Recent Trades:")
for t in trades:
    print(t)

# Get methods performance
cur.execute("SELECT method_name, SUM(CASE WHEN result='TP' THEN 1 ELSE 0 END) as tp_count, SUM(CASE WHEN result='SL' THEN 1 ELSE 0 END) as sl_count FROM trades GROUP BY method_name")
methods = [dict(r) for r in cur.fetchall()]
print("\nMethods Performance:")
for m in methods:
    print(m)

