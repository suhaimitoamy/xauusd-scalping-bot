import sys
import sqlite3
import csv
import subprocess
import os

if len(sys.argv) < 2:
    print("Cara penggunaan: python3 run_bulan.py YYYY-MM")
    print("Contoh: python3 run_bulan.py 2025-01")
    sys.exit(1)

target_month = sys.argv[1] # e.g. 2025-01
DB_PATH = "data/xauusd_bot.sqlite"
TEMP_CSV = f"data_temp_{target_month}.csv"

print(f"\nMenyiapkan data untuk bulan {target_month}...")

# 1. Tarik data dari database
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute('''
    SELECT open_time, open, high, low, close, volume_tick 
    FROM candles 
    WHERE timeframe = 'M1' AND open_time LIKE ?
    ORDER BY open_time ASC
''', (f"{target_month}%",))

rows = cur.fetchall()
conn.close()

if not rows:
    print(f"❌ Tidak ada data candle historis untuk bulan {target_month} di database!")
    sys.exit(1)

# 2. Jadikan file CSV kecil
print(f"Mengekstrak {len(rows)} candle ke dalam {TEMP_CSV}...")
with open(TEMP_CSV, 'w', newline='') as fout:
    writer = csv.writer(fout)
    for row in rows:
        iso_str = row[0]
        date_str = iso_str[0:10].replace('-', '.') # 2022.01.03
        time_str = iso_str[11:16]                  # 00:00
        writer.writerow([date_str, time_str, row[1], row[2], row[3], row[4], row[5]])

# 3. Jalankan Simulator!
print(f"\n🚀 Memulai Simulasi untuk {target_month}...")
cmd = [
    "python3", "-u", "src/run_simulator.py", 
    "--file", TEMP_CSV, 
    "--keep-ghost", 
    "--append-ghost"
]
subprocess.run(cmd)

# 4. Bersihkan file CSV
if os.path.exists(TEMP_CSV):
    os.remove(TEMP_CSV)

print(f"\n✅ Simulasi {target_month} SELESAI. Hasil tersimpan di xauusd_bot_ghost.sqlite!")
