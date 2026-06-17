EARLY WARNING MARKET STRUCTURE

Fungsi:
- Kirim peringatan lebih cepat sebelum candle close final.
- Confirmed VALID / INVALID tetap dikirim setelah validasi close candle.

Jenis early warning:
1. Support sedang disweep
2. Resistance sedang disweep
3. Support break bearish sedang terbentuk
4. Resistance break bullish sedang terbentuk
5. CHOCH/MSS bullish sedang terbentuk
6. CHOCH/MSS bearish sedang terbentuk
7. Trend bullish hampir invalid
8. Trend bearish hampir invalid

Cara pakai:

cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot
unzip /storage/emulated/0/Download/early_warning_structure_patch.zip
bash install_early_warning_structure.sh
git push origin main

ENV:
EARLY_STRUCTURE_TELEGRAM_ALERTS=false
untuk mematikan early warning.

EARLY_STRUCTURE_ALERT_COOLDOWN_SECONDS=180
untuk mengatur cooldown early warning.
