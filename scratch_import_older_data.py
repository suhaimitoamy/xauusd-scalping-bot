import sqlite3
import os
import shutil
import zipfile
import glob

DB_PATH = 'data/xauusd_bot.sqlite'
BACKUP_PATH = 'data/xauusd_bot_backup_before_2022_2024.sqlite'

ZIP_FILES = [
    '/storage/emulated/0/Download/HISTDATA_COM_MT_XAUUSD_M12022.zip',
    '/storage/emulated/0/Download/HISTDATA_COM_MT_XAUUSD_M12023.zip',
    '/storage/emulated/0/Download/HISTDATA_COM_MT_XAUUSD_M12024.zip'
]
EXTRACT_DIR = '/storage/emulated/0/Download/extracted_xauusd_data'

def safe_import():
    print("Membuat backup database...")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"Backup berhasil: {BACKUP_PATH}")

    if not os.path.exists(EXTRACT_DIR):
        os.makedirs(EXTRACT_DIR)

    # 1. Extract ZIP files
    csv_files = []
    for zip_path in ZIP_FILES:
        if not os.path.exists(zip_path):
            print(f"Peringatan: File {zip_path} tidak ditemukan!")
            continue
        print(f"Mengekstrak {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)

    # Find extracted CSV files
    extracted_files = glob.glob(os.path.join(EXTRACT_DIR, '*.csv'))
    if not extracted_files:
        print("Tidak ada file CSV yang diekstrak!")
        return

    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM candles WHERE timeframe = 'M1'")
    count_before = cur.fetchone()[0]

    for csv_file in extracted_files:
        print(f"\nMemproses {os.path.basename(csv_file)}...")
        
        batch = []
        with open(csv_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 7:
                    # Format HISTDATA usually: 2022.01.03,00:00,1828.64,1828.67,1828.53,1828.65,0
                    # or 20220103 000000;1828.64;1828.67;1828.53;1828.65;0 (Tick data)
                    # Let's handle the standard MT4 format from HistData
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
        
        print("Menyuntikkan data ke SQLite... (Mohon tunggu, ini mungkin memakan waktu)")
        
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
            if i % 100000 == 0 and i > 0:
                print(f"-> Berhasil menyimpan {i} baris...")
                
    cur.execute("SELECT COUNT(*) FROM candles WHERE timeframe = 'M1'")
    count_after = cur.fetchone()[0]
    
    inserted = count_after - count_before
    
    conn.close()
    
    print("\n✅ SUNTIKAN DATA HISTORIS SELESAI!")
    print(f"Total data baru ditambahkan: {inserted} baris")
    print(f"Total isi memori bot saat ini: {count_after} candle M1")

if __name__ == "__main__":
    safe_import()
