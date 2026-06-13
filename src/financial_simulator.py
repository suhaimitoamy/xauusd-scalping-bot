import sqlite3
import subprocess
import os

print("Memulai Simulasi Keuangan (Financial Simulator)...")
print("Target: Februari 2026 | Modal Awal: $2000 | Risiko: 2% (Strict RR 1:2)\n")

# Run simulator
cmd = ["python3", "src/run_simulator.py", "--month", "202602", "--keep-ghost", "--strict-rr"]
print("Menjalankan Core Simulator (mohon tunggu sekitar 1-2 menit)...")
subprocess.run(cmd, check=True)

print("\nCore Simulator selesai! Menghitung pergerakan saldo...")

db_path = "data/xauusd_bot_ghost.sqlite"
if not os.path.exists(db_path):
    print("Ghost DB tidak ditemukan!")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT * FROM signals ORDER BY created_at ASC")
signals = cur.fetchall()

balance = 2000.0
risk_percent = 0.02
history = []

win_count = 0
loss_count = 0

for sig in signals:
    res = sig['result']
    if res not in ('WIN', 'LOSS', 'FULL_WIN'):
        continue  # Ignore active/partial if any leaked through

    # Calculate Risk Amount ($)
    risk_amount = balance * risk_percent
    
    if res in ('WIN', 'FULL_WIN'):
        # Profit is 2x risk amount because RR is 1:2
        profit = risk_amount * 2.0
        balance += profit
        history.append(balance)
        win_count += 1
    elif res == 'LOSS':
        balance -= risk_amount
        history.append(balance)
        loss_count += 1

print("\n" + "="*50)
print("📊 LAPORAN KEUANGAN (FEBRUARI 2026)")
print("="*50)
print(f"Modal Awal   : $2000.00")
print(f"Saldo Akhir  : ${balance:.2f}")
print(f"Total Profit : ${(balance - 2000.0):.2f} ( {((balance - 2000.0)/2000.0)*100:.2f}% )")
print(f"Total Trade  : {win_count + loss_count} (W: {win_count} / L: {loss_count})")
print(f"Win Rate     : {(win_count / (win_count + loss_count) * 100) if (win_count + loss_count) > 0 else 0:.1f}%")
print("="*50)

conn.close()
