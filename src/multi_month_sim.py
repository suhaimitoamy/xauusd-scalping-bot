import sqlite3
import subprocess
import os

months = ['202601', '202602', '202603', '202604', '202605']
balance = 2000.0
risk_percent = 0.02
total_wins = 0
total_losses = 0

print("="*60)
print(f"MULAI SIMULASI 5 BULAN (JAN - MEI 2026)")
print(f"Modal Awal: ${balance:.2f} | Risk per Trade: {risk_percent*100}% | RR 1:1.5")
print("="*60)

for month in months:
    print(f"\n🚀 MENJALANKAN BULAN: {month} ...")
    cmd = ["python3", "src/run_simulator.py", "--month", month, "--keep-ghost", "--strict-rr"]
    subprocess.run(cmd, check=True)
    
    db_path = "data/xauusd_bot_ghost.sqlite"
    if not os.path.exists(db_path):
        print(f"Error: DB Ghost tidak ditemukan untuk {month}")
        continue
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM signals ORDER BY created_at ASC")
    signals = cur.fetchall()
    
    m_wins = 0
    m_losses = 0
    start_m_balance = balance
    
    for sig in signals:
        res = sig['result']
        if res not in ('WIN', 'LOSS', 'FULL_WIN'):
            continue
            
        risk_amount = balance * risk_percent
        if res in ('WIN', 'FULL_WIN'):
            profit = risk_amount * 1.5 # RR is 1:1.5 for native patterns
            balance += profit
            m_wins += 1
            total_wins += 1
        elif res == 'LOSS':
            balance -= risk_amount
            m_losses += 1
            total_losses += 1
            
    conn.close()
    
    # Calculate WR for the month
    total_m_trades = m_wins + m_losses
    m_wr = (m_wins / total_m_trades * 100) if total_m_trades > 0 else 0
    m_profit = balance - start_m_balance
    
    print(f"--- HASIL BULAN {month} ---")
    print(f"Trades   : {total_m_trades} (W: {m_wins} / L: {m_losses})")
    print(f"Win Rate : {m_wr:.1f}%")
    print(f"Profit   : ${m_profit:.2f}")
    print(f"Saldo    : ${balance:.2f}")

print("\n" + "="*60)
print("🏆 REKAPITULASI TOTAL (5 BULAN)")
print("="*60)
print(f"Modal Awal   : $2000.00")
print(f"Saldo Akhir  : ${balance:.2f}")
print(f"Total Profit : ${(balance - 2000.0):.2f} ( {((balance - 2000.0)/2000.0)*100:.2f}% )")
total_trades = total_wins + total_losses
print(f"Total Trade  : {total_trades} (W: {total_wins} / L: {total_losses})")
print(f"Win Rate     : {(total_wins / total_trades * 100) if total_trades > 0 else 0:.1f}%")
print("="*60)
