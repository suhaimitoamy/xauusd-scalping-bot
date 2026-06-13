import time
import subprocess
from datetime import datetime, timezone

sl_monitor_proc = None

def ensure_sl_monitor():
    """Memastikan SL Monitor (Daemon) selalu hidup."""
    global sl_monitor_proc
    if sl_monitor_proc is None or sl_monitor_proc.poll() is not None:
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] [CronManager] (Re)starting SL Monitor...")
        # Buka subprocess baru
        sl_monitor_proc = subprocess.Popen(["python3", "scratch_antigravity_monitor.py"])

def run_manager():
    print("🤖 [CronManager] Bot Pengelola Jadwal Abadi telah aktif.")
    print("🛡️ Fokus Tugas: Menjaga SL Monitor (Daemon) tetap hidup 24/7.")

    while True:
        try:
            # 1. Cek & hidupkan SL monitor jika mati
            ensure_sl_monitor()
            
            # Tidur 30 detik untuk menghemat CPU
            time.sleep(30)

        except Exception as e:
            print(f"[CronManager] Error di main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_manager()
