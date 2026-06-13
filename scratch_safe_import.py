import sqlite3
import glob
import os
import shutil

DB_PATH = 'data/xauusd_bot.sqlite'
BACKUP_PATH = 'data/xauusd_bot_backup.sqlite'

def safe_import():
    print("Membuat backup database...")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"Backup berhasil: {BACKUP_PATH}")

    # Mencari file DAT/CSV untuk 2026
    files = glob.glob('/storage/emulated/0/Download/DAT_MT_XAUUSD_M1_2026*.csv')
    if not files:
        print("File CSV tidak ditemukan!")
        return

    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cur = conn.cursor()
    
    total_inserted = 0
    total_skipped = 0

    for file in sorted(files):
        print(f"\nMemproses {os.path.basename(file)}...")
        
        batch = []
        with open(file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 7:
                    date_part = parts[0].replace('.', '-') # 2026.02.01 -> 2026-02-01
                    time_part = parts[1] # 18:06
                    
                    open_time = f"{date_part}T{time_part}:00+00:00"
                    
                    o, h, l, c = map(float, parts[2:6])
                    v = int(parts[6])
                    
                    batch.append((
                        'XAUUSD', 'M1', open_time, open_time, 
                        o, h, l, c, v, 1
                    ))
        
        print(f"Ditemukan {len(batch)} baris di file.")
        
        # Eksekusi insert massal dengan aman (INSERT OR IGNORE)
        cur.execute("BEGIN TRANSACTION")
        
        # Kita pakai execute lalu periksa rowcount untuk tahu berapa yg gagal (karena ignore)
        # Tapi executemany lebih cepat.
        
        # Ambil jumlah baris sebelum insert
        cur.execute("SELECT COUNT(*) FROM candles WHERE timeframe = 'M1'")
        count_before = cur.fetchone()[0]
        
        cur.executemany("""
            INSERT OR IGNORE INTO candles 
            (symbol, timeframe, open_time, close_time, open, high, low, close, volume_tick, is_closed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
        
        cur.execute("SELECT COUNT(*) FROM candles WHERE timeframe = 'M1'")
        count_after = cur.fetchone()[0]
        
        inserted = count_after - count_before
        skipped = len(batch) - inserted
        
        total_inserted += inserted
        total_skipped += skipped
        
        print(f"-> Berhasil masuk: {inserted} baris")
        print(f"-> Melewati (duplikat): {skipped} baris")
        
        conn.commit()

    conn.close()
    print("\n✅ OPERASI SELESAI!")
    print(f"Total data baru ditambahkan: {total_inserted}")
    print(f"Total data duplikat dilewati: {total_skipped}")

if __name__ == "__main__":
    safe_import()
