import os
import sqlite3
import csv
import zipfile
import glob

DOWNLOAD_DIR = "/storage/emulated/0/Download"
DB_PATH = "data/xauusd_bot.sqlite"
CSV_OUT = "temp_mega_backtest.csv"

def extract_historical_zips():
    zips = sorted(glob.glob(os.path.join(DOWNLOAD_DIR, "HISTDATA_COM_MT_XAUUSD_M120*.zip")))
    rows_written = 0
    
    with open(CSV_OUT, 'w', newline='') as fout:
        # 1. Tulis data historis dari ZIP
        for zip_path in zips:
            print(f"Mengurai ZIP: {zip_path}...")
            with zipfile.ZipFile(zip_path, 'r') as z:
                # Cari file CSV di dalam zip
                csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                if not csv_files:
                    continue
                
                with z.open(csv_files[0]) as f:
                    content = f.read().decode('utf-8').splitlines()
                    for line in content:
                        if not line.strip(): continue
                        fout.write(line + "\n")
                        rows_written += 1
                        
        print(f"Berhasil menulis {rows_written} candle historis.")
        
        # 2. Tulis data live dari SQLite (2025-2026)
        if os.path.exists(DB_PATH):
            print("Menggabungkan data terbaru dari database lokal...")
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('''
                SELECT open_time, open, high, low, close, volume_tick 
                FROM candles 
                WHERE timeframe = 'M1' 
                ORDER BY open_time ASC
            ''')
            rows = cur.fetchall()
            conn.close()
            
            db_written = 0
            writer = csv.writer(fout)
            for row in rows:
                iso_str = row[0]
                date_str = iso_str[0:10].replace('-', '.') # 2026.06.12
                time_str = iso_str[11:16]                  # 08:50
                writer.writerow([date_str, time_str, row[1], row[2], row[3], row[4], row[5]])
                db_written += 1
            print(f"Berhasil menggabungkan {db_written} candle dari database.")
            
    print(f"File {CSV_OUT} siap dengan total {rows_written + db_written} candle!")
    return True

if __name__ == '__main__':
    extract_historical_zips()
