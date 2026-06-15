import sys
import sqlite3
import csv
import subprocess
import os

if len(sys.argv) < 2:
    print("Cara penggunaan: python3 run_bulan.py YYYY-MM")
    print("Contoh: python3 run_bulan.py 2025-01")
    sys.exit(1)

target_month = sys.argv[1]
fair_method = (os.environ.get("FAIR_TEST_METHOD") or os.environ.get("METHOD_UNDER_TEST") or "").strip().upper()
result_key = target_month if not fair_method else f"{target_month}__{fair_method}"
month_key = target_month.replace('-', '')
DB_PATH = "data/xauusd_bot.sqlite"
GHOST_DB_PATH = "data/xauusd_bot_ghost.sqlite"
BACKTEST_DB_PATH = "data/backtest_results.sqlite"
BACKTEST_REPORT_PATH = "reports/BACKTEST_RESULTS_REPORT.md"
TEMP_CSV = f"data_temp_{month_key}.csv"

print(f"\nMenyiapkan data untuk bulan {target_month}...")
if fair_method:
    print(f"FAIR TEST METHOD: {fair_method}")

subprocess.run([
    sys.executable, "tools/snapshot_config.py",
    "--run-month", result_key,
    "--mode", "fair_test_method" if fair_method else "backtest_all_methods",
    "--notes", "Snapshot otomatis sebelum run_bulan"
])

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

print(f"Mengekstrak {len(rows)} candle ke dalam {TEMP_CSV}...")
with open(TEMP_CSV, 'w', newline='') as fout:
    writer = csv.writer(fout)
    for row in rows:
        iso_str = row[0]
        date_str = iso_str[0:10].replace('-', '.')
        time_str = iso_str[11:16]
        writer.writerow([date_str, time_str, row[1], row[2], row[3], row[4], row[5]])

print(f"\n🚀 Memulai Simulasi {'FAIR TEST' if fair_method else 'ALL METHODS'} untuk {target_month}...")
env = os.environ.copy()
env["BACKTEST_ALL_METHODS"] = "true"
env["DRY_RUN"] = "true"
env["BACKTEST_NEUTRAL_CONFIDENCE"] = "true"
if fair_method:
    env["FAIR_TEST"] = "true"
    env["FAIR_TEST_METHOD"] = fair_method

runner_code = (
    "import sys;"
    "sys.path.insert(0,'src');"
    "from src.backtest_fairness_patch import apply_backtest_fairness_patch;"
    "apply_backtest_fairness_patch();"
    "import runpy;"
    "sys.argv=['src/run_simulator.py']+sys.argv[1:];"
    "runpy.run_path('src/run_simulator.py', run_name='__main__')"
)
cmd = [
    sys.executable, "-u", "-c", runner_code,
    "--file", TEMP_CSV,
    "--keep-ghost",
    "--append-ghost",
    "--new-test-run"
]
result = subprocess.run(cmd, env=env)

if result.returncode != 0:
    print(f"\n❌ Simulasi {target_month} gagal. Hasil tidak disimpan ke DB backtest permanen.")
    if os.path.exists(TEMP_CSV):
        os.remove(TEMP_CSV)
    sys.exit(result.returncode)

print(f"\n💾 Menyimpan hasil {result_key} ke {BACKTEST_DB_PATH}...")
export_cmd = [
    sys.executable, "tools/save_backtest_results.py", result_key,
    "--source-db", GHOST_DB_PATH,
    "--dest-db", BACKTEST_DB_PATH,
    "--report", BACKTEST_REPORT_PATH,
]
export_result = subprocess.run(export_cmd)

if export_result.returncode != 0:
    print(f"\n❌ Export hasil {result_key} ke DB permanen gagal.")
    if os.path.exists(TEMP_CSV):
        os.remove(TEMP_CSV)
    sys.exit(export_result.returncode)

subprocess.run([sys.executable, "tools/backtest_report_v2.py"])
subprocess.run([sys.executable, "manage_methods.py", "sync"])

if os.path.exists(TEMP_CSV):
    os.remove(TEMP_CSV)

print(f"\n✅ Simulasi {'FAIR TEST' if fair_method else 'ALL METHODS'} {result_key} SELESAI.")
print(f"✅ Detail sementara simulator: {GHOST_DB_PATH}")
print(f"✅ Hasil permanen backtest: {BACKTEST_DB_PATH}")
print(f"✅ Report permanen: {BACKTEST_REPORT_PATH}")
print("\nCek hasil:")
print(f"  python3 query_backtest_results.py {result_key}")
print("  python3 query_backtest_results.py")
print("  cat reports/BACKTEST_RESULTS_REPORT.md")
