import sqlite3
import subprocess
import os

print("="*60)
print("🚀 TEST 15 HARI FEBRUARI (15.000 Candle) + FILTER AMY GOLD")
print("="*60)

cmd = ["python3", "src/run_simulator.py", "--month", "202602", "--limit", "15000", "--keep-ghost", "--strict-rr"]
subprocess.run(cmd, check=True)

db_path = "data/xauusd_bot_ghost.sqlite"
if not os.path.exists(db_path):
    print("Error: DB Ghost tidak ditemukan")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM signals ORDER BY created_at ASC")
signals = cur.fetchall()

balance = 2000.0
risk_percent = 0.02
m_wins = 0
m_losses = 0

for sig in signals:
    res = sig['result']
    if res not in ('WIN', 'LOSS', 'FULL_WIN'):
        continue
        
    risk_amount = balance * risk_percent
    if res in ('WIN', 'FULL_WIN'):
        profit = risk_amount * 1.5
        balance += profit
        m_wins += 1
    elif res == 'LOSS':
        balance -= risk_amount
        m_losses += 1

conn.close()

total_m_trades = m_wins + m_losses
m_wr = (m_wins / total_m_trades * 100) if total_m_trades > 0 else 0
m_profit = balance - 2000.0

print("\n" + "="*60)
print("🏆 HASIL TEST 15 HARI FEBRUARI 2026")
print("="*60)
print(f"Modal Awal   : $2000.00")
print(f"Saldo Akhir  : ${balance:.2f}")
print(f"Total Profit : ${m_profit:.2f} ( {(m_profit/2000.0)*100:.2f}% )")
print(f"Total Trade  : {total_m_trades} (W: {m_wins} / L: {m_losses})")
print(f"Win Rate     : {m_wr:.1f}%")
print("="*60)
