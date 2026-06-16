NONMAIN COOK V3 PATCH

Isi patch:
- run_bulan.py
- src/bt_research_patch.py
- NONMAIN_COOK_V3_README.txt

Tujuan:
- Masak ulang semua metode yang belum masuk whitelist / LIVE_MAIN.
- LIVE_MAIN tetap tidak ikut backtest kandidat.
- Cooldown mati hanya saat BT_RESEARCH.
- Active signal lock mati hanya saat BT_RESEARCH.
- Semua non-main diputar bergantian agar tidak ada metode 0 trade terus.
- Jika logic natural cocok, alasan signal memakai logic keluarga metode.
- Jika logic natural belum cocok, tetap dibuat forced sample untuk mengumpulkan data.

Default baru:
- BT_RESEARCH_PER_DAY default 24 signal/hari.
- Bisa diubah lewat environment variable.

Cara pasang:
cd "/storage/emulated/0/Download/aplikasi"
unzip -o "/storage/emulated/0/Download/xauusd-scalping-bot-34-NONMAIN-COOK-V3-PATCH.zip"
cd xauusd-scalping-bot

Tes 6 bulan 2026:
BT_RESEARCH_PER_DAY=24 python3 run_bulan.py 2026-01
BT_RESEARCH_PER_DAY=24 python3 run_bulan.py 2026-02
BT_RESEARCH_PER_DAY=24 python3 run_bulan.py 2026-03
BT_RESEARCH_PER_DAY=24 python3 run_bulan.py 2026-04
BT_RESEARCH_PER_DAY=24 python3 run_bulan.py 2026-05
BT_RESEARCH_PER_DAY=24 python3 run_bulan.py 2026-06

Cek hasil:
cat reports/BACKTEST_RESULTS_REPORT.md
python3 query_backtest_results.py

Push:
git add run_bulan.py src/bt_research_patch.py NONMAIN_COOK_V3_README.txt reports/BACKTEST_RESULTS_REPORT.md data/backtest_results.sqlite config/method_registry.json
git commit -m "cook non-main research methods v3"
git push
