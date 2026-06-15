import sys
import sqlite3
import csv
import subprocess
import os

if len(sys.argv) < 2:
    print("Cara penggunaan: python3 run_bulan.py YYYY-MM")
    print("Contoh: python3 run_bulan.py 2025-01")
    sys.exit(1)

target_month = sys.argv[1]  # e.g. 2025-01
month_key = target_month.replace('-', '')  # e.g. 202501, supaya run_simulator bisa baca dataset_key
DB_PATH = "data/xauusd_bot.sqlite"
GHOST_DB_PATH = "data/xauusd_bot_ghost.sqlite"
BACKTEST_DB_PATH = "data/backtest_results.sqlite"
BACKTEST_REPORT_PATH = "reports/BACKTEST_RESULTS_REPORT.md"
TEMP_CSV = f"data_temp_{month_key}.csv"

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
        date_str = iso_str[0:10].replace('-', '.')  # 2022.01.03
        time_str = iso_str[11:16]                   # 00:00
        writer.writerow([date_str, time_str, row[1], row[2], row[3], row[4], row[5]])

# 3. Jalankan Simulator
print(f"\n🚀 Memulai Simulasi untuk {target_month}...")
cmd = [
    sys.executable, "-u", "src/run_simulator.py",
    "--file", TEMP_CSV,
    "--keep-ghost",
    "--append-ghost"
]
result = subprocess.run(cmd)

if result.returncode != 0:
    print(f"\n❌ Simulasi {target_month} gagal. Hasil tidak disimpan ke DB backtest permanen.")
    if os.path.exists(TEMP_CSV):
        os.remove(TEMP_CSV)
    sys.exit(result.returncode)

# 4. Simpan hasil ghost bulan ini ke DB backtest permanen
print(f"\n💾 Menyimpan hasil {target_month} ke {BACKTEST_DB_PATH}...")
export_cmd = [
    sys.executable, "tools/save_backtest_results.py", target_month,
    "--source-db", GHOST_DB_PATH,
    "--dest-db", BACKTEST_DB_PATH,
    "--report", BACKTEST_REPORT_PATH,
]
export_result = subprocess.run(export_cmd)

if export_result.returncode != 0:
    print(f"\n❌ Export hasil {target_month} ke DB permanen gagal.")
    if os.path.exists(TEMP_CSV):
        os.remove(TEMP_CSV)
    sys.exit(export_result.returncode)

# 5. Bersihkan file CSV sementara
if os.path.exists(TEMP_CSV):
    os.remove(TEMP_CSV)

print(f"\n✅ Simulasi {target_month} SELESAI.")
print(f"✅ Detail sementara simulator: {GHOST_DB_PATH}")
print(f"✅ Hasil permanen backtest: {BACKTEST_DB_PATH}")
print(f"✅ Report permanen: {BACKTEST_REPORT_PATH}")
print("\nCek hasil:")
print(f"  python3 query_backtest_results.py {target_month}")
print("  python3 query_backtest_results.py")
