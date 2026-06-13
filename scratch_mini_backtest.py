import sqlite3
import os
import csv
import subprocess
from datetime import datetime, timezone, timedelta

DB_PATH = "data/xauusd_bot.sqlite"
CSV_OUT = "temp_3days.csv"
SIM_SCRIPT = "src/run_simulator.py"

def generate_csv():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database {DB_PATH} tidak ditemukan.")
        return False
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Ambil waktu 3 hari yang lalu
    three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    
    print(f"Mengambil data M1 dari {three_days_ago} sampai sekarang...")
    cur.execute('''
        SELECT open_time, open, high, low, close, volume_tick 
        FROM candles 
        WHERE timeframe = 'M1' AND open_time >= ? 
        ORDER BY open_time ASC
    ''', (three_days_ago,))
    
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        print("Tidak ada data M1 yang cukup dalam 3 hari terakhir.")
        return False
        
    print(f"Berhasil mengekstrak {len(rows)} candle. Menyimpan ke {CSV_OUT}...")
    
    with open(CSV_OUT, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            # open_time format: 2026-06-12T08:50:41Z
            iso_str = row[0].replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(iso_str)
            except ValueError:
                # Fallback if format is different
                dt = datetime.strptime(row[0][:19], "%Y-%m-%dT%H:%M:%S")
                
            date_str = dt.strftime("%Y.%m.%d")
            time_str = dt.strftime("%H:%M")
            # Format: Date, Time, Open, High, Low, Close, Volume
            writer.writerow([date_str, time_str, row[1], row[2], row[3], row[4], row[5]])
            
    return True

def run_simulator():
    print(f"\nMenjalankan Mini Backtest menggunakan {CSV_OUT}...\n")
    # Menggunakan --append-ghost agar tidak menghapus hasil eksperimen sebelumnya
    # --fast reduces output clutter
    cmd = ["python3", SIM_SCRIPT, "--file", CSV_OUT, "--append-ghost", "--fast"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("=== HASIL MINI BACKTEST ===")
    # Ambil 20 baris terakhir dari output untuk menampilkan summary PnL
    output_lines = result.stdout.strip().split('\n')
    for line in output_lines[-25:]:
        print(line)
        
    if result.stderr:
        print("Error/Warning:", result.stderr)

if __name__ == "__main__":
    if generate_csv():
        run_simulator()
