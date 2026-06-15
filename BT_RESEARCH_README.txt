BT RESEARCH MODE

File yang diubah/ditambah:
- run_bulan.py
- src/bt_research_patch.py

Efek:
- Hanya aktif saat menjalankan run_bulan.py.
- Live trading tidak berubah.
- Backtest riset tidak memakai cooldown.
- Backtest riset tidak menguji metode LIVE_MAIN.
- Jika metode non-main jarang trigger, sistem membuat trigger eksplorasi agar kandidat non-main muncul.
- Default target eksplorasi: sekitar 8 signal per hari market aktif.
- WR di mode ini jangan langsung dipercaya. Ini mode pencarian kandidat dulu.

Command:
python3 run_bulan.py 2026-06

Hasil disimpan dengan suffix:
2026-06__BT_RESEARCH_NON_MAIN

Untuk ubah target jumlah trade per hari:
BT_RESEARCH_PER_DAY=12 python3 run_bulan.py 2026-06

Untuk matikan research dan backtest normal:
BT_RESEARCH=false python3 run_bulan.py 2026-06
