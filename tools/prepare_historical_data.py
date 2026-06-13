import os
import sqlite3
import csv
import zipfile
import glob

DOWNLOAD_DIR = "/storage/emulated/0/Download"
DB_PATH = "data/xauusd_bot.sqlite"
CSV_OUT = "temp_mega_backtest.csv"

def extract_historical_zips():
    rows_written = 0
    with open(CSV_OUT, 'w', newline='') as fout:
        # Tulis data dari SQLite secara keseluruhan (2022-2026)
        if os.path.exists(DB_PATH):
            print("Membaca seluruh data historis dari database lokal (2022-2026)...")
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
            print(f"Berhasil mengekstrak {db_written} candle dari database ke CSV.")
            rows_written = db_written
            
    print(f"File {CSV_OUT} siap dengan total {rows_written} candle!")
    return True

if __name__ == '__main__':
    extract_historical_zips()
