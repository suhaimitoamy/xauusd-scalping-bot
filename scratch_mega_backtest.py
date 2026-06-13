import sqlite3
import os
import csv
import subprocess

DB_PATH = "data/xauusd_bot.sqlite"
CSV_OUT = "temp_mega_backtest.csv"
SIM_SCRIPT = "src/run_simulator.py"

def generate_csv():
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), 'tools'))
    try:
        from prepare_historical_data import extract_historical_zips
        return extract_historical_zips()
    except ImportError as e:
        print(f"Gagal memuat skrip ekstraksi: {e}")
        return False

def run_simulator():
    print(f"\nMenjalankan MEGA BACKTEST menggunakan {CSV_OUT}...\n")
    print("⚠️  Peringatan: Telegram otomatis DIMATIKAN oleh simulator agar tidak spam.")
    print("Silakan tunggu, proses ini bisa memakan waktu beberapa menit untuk 100rb+ candle...\n")
    
    cmd = ["python3", "-u", SIM_SCRIPT, "--file", CSV_OUT, "--new-test-run", "--fast", "--progress-every", "100000"]
    
    # Run the simulator and stream output to console so the user isn't stuck waiting blindly
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())

if __name__ == "__main__":
    if os.path.exists(CSV_OUT) and os.path.getsize(CSV_OUT) > 100 * 1024 * 1024:  # > 100 MB
        print(f"Menggunakan data raksasa CSV yang sudah ada ({CSV_OUT}) agar langsung ngebut...")
        run_simulator()
    else:
        if generate_csv():
            run_simulator()
