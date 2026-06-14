import os
import subprocess
import time
from datetime import datetime

months = []
for year in range(2022, 2027):
    for month in range(1, 13):
        if year == 2026 and month > 6:
            break
        months.append(f"{year}-{month:02d}")

print("🚀 MEMULAI MEGA-BACKTEST TAHAP 2 (AGRESSIVE SCALPING)")
print(f"Total bulan: {len(months)}")
print("Mencadangkan database Phase 1...")

os.system("mv xauusd_bot_ghost.sqlite xauusd_bot_ghost_phase1.sqlite 2>/dev/null || true") # Reset untuk Phase 2

start_time = time.time()

for m in months:
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ---> Menjalankan {m}...")
    subprocess.run(["python3", "run_bulan.py", m])

elapsed = time.time() - start_time
print(f"\n✅ MEGA-BACKTEST TAHAP 2 SELESAI DALAM {elapsed/60:.2f} MENIT!")
