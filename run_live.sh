#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"

# Pastikan tidak ada Cron Manager ganda yang berjalan
pkill -f scratch_cron_manager.py
# Pastikan SL monitor dibunuh agar bisa dihidupkan bersih oleh Cron Manager
pkill -f scratch_antigravity_monitor.py

# Jalankan Cron Manager di background (Cron Manager akan menjaga SL Monitor)
nohup python3 scratch_cron_manager.py > logs/cron_manager.log 2>&1 &

# Jalankan Bot Utama dengan Watchdog
python3 run_live_auto_reload.py
