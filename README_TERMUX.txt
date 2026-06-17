CARA PAKAI DI TERMUX

1. Download dan extract file zip ini.

2. Copy dua file ini ke folder repo bot:
- market_structure.py
- install_market_structure_patch.sh

3. Masuk ke folder repo bot:
cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot

4. Jalankan:
bash install_market_structure_patch.sh

5. Push:
git push origin main

ENV tambahan:
STRUCTURE_TELEGRAM_ALERTS=false
untuk mematikan alert Telegram market structure.

STRUCTURE_ALERT_COOLDOWN_SECONDS=900
untuk atur cooldown notifikasi.
