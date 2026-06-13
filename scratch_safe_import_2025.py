import sqlite3
import os
import shutil

DB_PATH = 'data/xauusd_bot.sqlite'
BACKUP_PATH = 'data/xauusd_bot_backup_before_2025.sqlite'
FILE_2025 = '/storage/emulated/0/Download/DAT_MT_XAUUSD_M1_2025.csv'

def safe_import():
    print("Membuat backup database...")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"Backup berhasil: {BACKUP_PATH}")

    if not os.path.exists(FILE_2025):
        print("File CSV 2025 tidak ditemukan!")
        return

    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cur = conn.cursor()
    
    print(f"\nMemproses {os.path.basename(FILE_2025)}...")
    
    batch = []
    with open(FILE_2025, 'r') as f:
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
                    continue # Skip header or invalid lines
                
                batch.append((
                    'XAUUSD', 'M1', open_time, open_time, 
                    o, h, l, c, v, 1
                ))
    
    print(f"Ditemukan {len(batch)} baris di file.")
    
    cur.execute("SELECT COUNT(*) FROM candles WHERE timeframe = 'M1'")
    count_before = cur.fetchone()[0]
    
    print("Menyuntikkan data ke SQLite... (Mohon tunggu, ini mungkin memakan waktu puluhan detik)")
    
    chunk_size = 5000
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i:i + chunk_size]
        cur.execute("BEGIN TRANSACTION")
        cur.executemany("""
            INSERT OR IGNORE INTO candles 
            (symbol, timeframe, open_time, close_time, open, high, low, close, volume_tick, is_closed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, chunk)
        conn.commit()
        print(f"-> Berhasil menyimpan baris {i} sampai {i + len(chunk)}...")
        
    cur.execute("SELECT COUNT(*) FROM candles WHERE timeframe = 'M1'")
    count_after = cur.fetchone()[0]
    
    inserted = count_after - count_before
    skipped = len(batch) - inserted
    
    conn.close()
    
    print("\n✅ SUNTIKAN 2025 SELESAI!")
    print(f"Total data baru ditambahkan: {inserted} baris")
    print(f"Total data dilewati (duplikat): {skipped} baris")
    print(f"Total isi memori bot saat ini: {count_after} candle M1")

if __name__ == "__main__":
    safe_import()
