FIX: DAILY LIMIT + CHOCH REVERSAL SELL SL

Yang diubah:
1. config.yaml
   max_signals_per_day: 6 -> 999

2. src/market_brain.py
   SL khusus METHOD_CHOCH_REVERSAL_SELL saja.
   Metode lain tidak disentuh.

Cara pakai:

cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot
unzip /storage/emulated/0/Download/fix_daily_limit_choch_sell_sl.zip
bash install_fix_daily_limit_choch_sl.sh
git push origin main
