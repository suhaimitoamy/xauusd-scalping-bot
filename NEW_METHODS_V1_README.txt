NEW METHODS V1 PATCH

Isi patch:
- src/bt_research_patch.py
- src/method_registry.py
- config/method_registry.json

Efek:
- 11 metode whitelist lama tetap LIVE_MAIN.
- 15 metode baru masuk WATCHLIST untuk backtest research.
- BT_RESEARCH default SL 5, TP1 5, TP2 10.
- CRT H1 sudah punya rule khusus:
  Bearish: candle H1 merah sebagai CRT, candle berikutnya sweep CRH, close balik dalam range, close <= 50% range.
  Bullish: candle H1 hijau sebagai CRT, candle berikutnya sweep CRL, close balik dalam range, close >= 50% range.

Jangan jalankan manage_methods.py sync kalau belum perlu.

Contoh backtest 2 tahun:
BT_RESEARCH=true BT_RESEARCH_SL=5 BT_RESEARCH_TP1=5 BT_RESEARCH_TP2=10 BT_RESEARCH_PER_DAY=12 python3 run_bulan.py 2025-01
