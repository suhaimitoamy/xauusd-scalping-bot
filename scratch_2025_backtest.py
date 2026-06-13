import subprocess
import sys
import os

print("🚀 FAST BACKTEST WRAPPER")
print("========================")

args = sys.argv[1:]

if not args:
    print("Penggunaan:")
    print("  python3 scratch_2025_backtest.py --month 202601")
    print("  python3 scratch_2025_backtest.py --month 202601 --day 2026.01.15")
    print("  python3 scratch_2025_backtest.py --file DAT_MT_XAUUSD_M1_2025.csv")
    print("\nMenjalankan secara default untuk bulan terbaru...")
    args = ["--all"]

cmd = ["python3", "-u", "src/run_simulator.py", "--fast"] + args

print(f"Menjalankan command: {' '.join(cmd)}\n")

try:
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="")
    process.wait()
except KeyboardInterrupt:
    print("\n[!] Dibatalkan oleh pengguna.")
except Exception as e:
    print(f"\n[!] Error: {e}")

print("\n✅ SELESAI!")
