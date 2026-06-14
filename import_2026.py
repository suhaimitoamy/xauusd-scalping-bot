import sqlite3
import glob
import os

DB_PATH = 'data/xauusd_bot.sqlite'
csv_files = glob.glob('data/DAT_MT_XAUUSD_M1_2026*.csv')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

for csv_file in sorted(csv_files):
    print(f"Mengimpor {csv_file}...")
    batch = []
    with open(csv_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 7:
                date_part = parts[0].replace('.', '-')
                time_part = parts[1]
                open_time = f"{date_part}T{time_part}:00+00:00"
                try:
                    o, h, l, c = map(float, parts[2:6])
                    v = int(parts[6])
                except ValueError:
                    continue
                batch.append((
                    'XAUUSD', 'M1', open_time, open_time, 
                    o, h, l, c, v, 1
                ))
    
    chunk_size = 10000
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i:i + chunk_size]
        cur.execute("BEGIN TRANSACTION")
        cur.executemany("""
            INSERT OR IGNORE INTO candles 
            (symbol, timeframe, open_time, close_time, open, high, low, close, volume_tick, is_closed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, chunk)
        conn.commit()
    print(f"Selesai {csv_file} -> {len(batch)} baris.")

conn.close()
print("Selesai import!")
