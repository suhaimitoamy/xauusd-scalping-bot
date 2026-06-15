NON-MAIN METHOD RESEARCH PATCH

Isi patch:
- src/bt_research_patch.py
- run_bulan.py
- NONMAIN_LOGIC_README.txt

Tujuan:
1. Hanya untuk backtest research.
2. LIVE_MAIN tidak ikut dites sebagai kandidat.
3. Cooldown dan active-signal lock dimatikan hanya saat BT_RESEARCH=true.
4. Metode non-main diberi logic riset per keluarga metode:
   - Session Open / London / NY breakout
   - Asia sweep / Asia range
   - BOS / continuation / breakout
   - Break and retest / OB / breaker
   - POI accumulation / POI rebound
   - Sweep / turtle soup / liquidity
   - Inducement trap / CHoCH reversal
   - Pullback / follow trend
   - Momentum / marubozu
   - Choppy scalp
   - News spike fade
   - AI / Antigravity generic candidates
5. Jika tidak ada setup alami, engine membuat fallback trigger terjadwal untuk memberi data ke metode non-main.

Default:
python3 run_bulan.py 2026-01

Default itu menjalankan BT_RESEARCH=true dan target sekitar 8 sample/hari.

Lebih banyak trade per hari:
BT_RESEARCH_PER_DAY=12 python3 run_bulan.py 2026-01
BT_RESEARCH_PER_DAY=20 python3 run_bulan.py 2026-01

Matikan research dan pakai backtest normal:
BT_RESEARCH=false python3 run_bulan.py 2026-01

Catatan:
- Patch ini tidak mengubah logic live trading.
- Patch ini sengaja mengabaikan WR dulu untuk mencari kandidat.
- Hasil bagus tetap harus kamu pilih manual untuk masuk MAIN.
