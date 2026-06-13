import subprocess
import os

# Lokasi file data mentah 1 Tahun Penuh (2025)
data_2025 = "/storage/emulated/0/Download/DAT_MT_XAUUSD_M1_2025.csv"

if not os.path.exists(data_2025):
    print(f"Error: File {data_2025} tidak ditemukan!")
    exit(1)

print(f"Memulai ULTRA BACKTEST (Januari 2025 - Juni 2026)...")
print("⚠️ Peringatan: Proses ini mensimulasikan ~460.000+ candle dan bisa memakan waktu 15-20 menit.")
print("Auto-Block sedang DIMATIKAN agar kita bisa melihat potensi asli seluruh metode selama 1.5 tahun.\n")

files_to_run = [
    data_2025,
    "temp_mega_backtest.csv" # Data 2026 Feb - Mei yang sudah kita buat sebelumnya
]

for i, file_path in enumerate(files_to_run):
    if not os.path.exists(file_path):
        print(f"Melewati {file_path} karena tidak ditemukan.")
        continue
        
    print(f"\n[{i+1}/{len(files_to_run)}] Menjalankan simulator untuk {file_path}...")
    cmd = [
        "python3", "-u", "src/run_simulator.py",
        "--file", file_path,
        "--fast"
    ]
    
    # Run pertama menggunakan --new-test-run untuk reset Ghost DB
    if i == 0:
        cmd.append("--new-test-run")
    else:
        # Run kedua dkk menggunakan --append-ghost agar lanjut dari memori sebelumnya
        cmd.append("--append-ghost")

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end="")
        process.wait()
    except KeyboardInterrupt:
        print("\nProses dihentikan paksa oleh pengguna.")
        break
    except Exception as e:
        print(f"\nTerjadi kesalahan: {e}")

import shutil
if os.path.exists("data/xauusd_bot_ghost.sqlite"):
    shutil.copy2("data/xauusd_bot_ghost.sqlite", "data/ghost_2025_result.sqlite")
    print("Database hasil simulasi disimpan secara aman di: data/ghost_2025_result.sqlite")

print("\n✅ ULTRA BACKTEST 1.5 TAHUN SELESAI!")
print("Silakan cek xauusd_bot_ghost.sqlite untuk melihat rapor akhir seluruh metode!")
