import os
import sys
import sqlite3
import csv
import subprocess
from datetime import datetime

DB_PATH = "data/xauusd_bot.sqlite"
GHOST_PATH = "data/xauusd_bot_ghost.sqlite"
TEMP_CSV = "temp_month.csv"
SIM_SCRIPT = "src/run_simulator.py"

def generate_months():
    months = []
    for year in [2022, 2023, 2024, 2025, 2026]:
        for m in range(1, 13):
            if year == 2026 and m > 6:
                break
            months.append(f"{year}-{m:02d}")
    return months

def export_month_to_csv(month_prefix):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Format open_time is '2022-01-...'
    cur.execute('''
        SELECT open_time, open, high, low, close, volume_tick 
        FROM candles 
        WHERE timeframe = 'M1' AND open_time LIKE ?
        ORDER BY open_time ASC
    ''', (f"{month_prefix}%",))
    
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        return 0
        
    with open(TEMP_CSV, 'w', newline='') as fout:
        writer = csv.writer(fout)
        for row in rows:
            iso_str = row[0]
            date_str = iso_str[0:10].replace('-', '.') # 2022.01.03
            time_str = iso_str[11:16]                  # 00:00
            writer.writerow([date_str, time_str, row[1], row[2], row[3], row[4], row[5]])
            
    return len(rows)

def run_monthly_batch():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Memulai eksekusi Mega Backtest per bulan...")
    
    # 1. Start fresh Ghost DB
    if os.path.exists(GHOST_PATH):
        os.remove(GHOST_PATH)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Ghost DB lama dihapus.")
        
    months = generate_months()
    total_months = len(months)
    
    for i, m in enumerate(months):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Memproses Bulan {m} ({i+1}/{total_months})...")
        num_rows = export_month_to_csv(m)
        
        if num_rows == 0:
            print(f"  -> Tidak ada data untuk bulan {m}, di-skip.")
            continue
            
        print(f"  -> {num_rows} candle diekstrak. Menjalankan simulator...")
        
        cmd = ["python3", "-u", SIM_SCRIPT, "--file", TEMP_CSV, "--keep-ghost", "--append-ghost"]
        # Use subprocess to run and wait
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # We don't want to print everything, just keep the output silent or print errors
        for line in process.stdout:
            # You can print the line if you want to see progress
            pass
            
        process.wait()
        
        if process.returncode != 0:
            print(f"  -> ❌ ERROR saat menjalankan bulan {m}.")
        else:
            print(f"  -> ✅ Bulan {m} selesai dan tersimpan ke Ghost DB.")

    # Cleanup temp csv
    if os.path.exists(TEMP_CSV):
        os.remove(TEMP_CSV)
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] SEMUA BATCH SELESAI!")

if __name__ == "__main__":
    run_monthly_batch()
