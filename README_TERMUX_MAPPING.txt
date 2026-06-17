CARA PAKAI DI TERMUX

1. Download zip ini ke folder Download.

2. Masuk ke repo bot:
cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot

3. Extract zip:
unzip /storage/emulated/0/Download/mapping_assistant_upgrade.zip

4. Install / commit:
bash install_mapping_assistant_upgrade.sh

5. Test tanpa Telegram:
python scripts/send_mapping_summary.py

6. Kirim ke Telegram:
python scripts/send_mapping_summary.py --send

7. Push:
git push origin main


ISI UPGRADE

1. src/session_context.py
- WIB = Asia/Jakarta
- New York = America/New_York
- EST/EDT otomatis
- London Killzone: 02:00-05:00 New York time
- NY Killzone: 08:30-11:30 New York time
- Saat EDT: NY Killzone 19:30-22:30 WIB
- Saat EST: NY Killzone 20:30-23:30 WIB

2. src/order_block_engine.py
- Bullish OB
- Bearish OB
- OB fresh
- OB touched
- OB invalid
- invalidasi OB

3. src/fvg_mapping.py
- nearest FVG
- FVG fresh
- FVG partial
- FVG invalid / IFVG

4. src/range_map.py
- premium
- discount
- equilibrium

5. src/liquidity_map.py
- nearest BSL
- nearest SSL
- equal high
- equal low
- PDH
- PDL

6. src/htf_bias_engine.py
- D1/H4/H1 bias
- invalidasi bullish di Higher Low
- invalidasi bearish di Lower High

7. src/market_narrative.py
- kesimpulan mapping

8. scripts/send_mapping_summary.py
- print mapping
- --send untuk Telegram
