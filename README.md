# 🚀 XAUUSD Hyper-Evolution Scalping Bot (V8 - Operasi Mata Dewa)

Sistem Bot XAUUSD (Gold) yang didesain secara khusus untuk ekosistem Termux Android. Bot ini telah berevolusi menjadi agen **Hyper-Evolution**, sebuah *signal provider* yang sangat agresif, brutal, dan mampu **Bermutasi Otomatis (Self-Evolving)** secara *real-time* setiap kali mengalami kerugian (*Stop Loss*). 
Di Versi 8 ini, penglihatan bot (Vision) dirombak total menyamai akurasi *script Pine indikator SMC* terbaik.

---

## 🧠 Filosofi & Mesin Utama

Bot ini mengesampingkan indikator tradisional yang lambat (seperti MA/Trend Filters) dan mengandalkan **Price Action murni** serta **Smart Money Concepts (SMC)** di sekitar area likuiditas (*Point of Interest*). 

### 1. The Watchdog (`run_live_auto_reload.py`)
Bot tidak perlu lagi di-*restart* manual. Daemon *Watchdog* akan memantau seluruh file `.py` dan `config.yaml` setiap 1 detik. Jika *source code* berubah (misal Antigravity AI menyuntikkan strategi baru), bot akan otomatis merestart dirinya sendiri dalam 0.5 detik tanpa interupsi *trading* (*Hot-Reload*).

### 2. Market Brain (`market_brain.py`) & 8 Pilar SMC (Mata Dewa)
Pusat eksekusi sinyal bot telah ditingkatkan dengan **8 Pilar SMC PineScript Asli**:
1. **FVG Berfilter Wick**: Mendeteksi FVG hanya dengan validasi *wick* ketat (< 36% dari bodi).
2. **Liquidity Swings (3,1)**: Memetakan likuiditas menggunakan formasi pivot (Kiri 3, Kanan 1).
3. **Akurasi Order Block**: OB ditarik spesifik dari *Open* ke *Low* (Bull) atau *Open* ke *High* (Bear) dengan validasi breakout menembus 2 candle ke belakang.
4. **Displacement Dinamis**: Momentum breakout tidak lagi kaku, melainkan menggunakan rata-rata bodi 5 candle (`sma(body, 5)`).
5. **Tokyo Killzone**: Mengunci area sapuan sesi Asia pada pukul 10:00 - 14:00 (JST/Tokyo).
6. **BPR & IFVG**: Mendeteksi tumpukan FVG (Balanced Price Range) dan perubahan fungsi FVG jebol (Inversion FVG).
7. **HTF Bias (EMA 20 & 50)**: Eksekusi metode SMC selalu difilter mengikuti tren Timeframe Besar (H1).
8. **S&R Price Action**: Bot wajib memvalidasi bentuk lilin *Pinbar* ekstrem (jarum > 1.5x lipat bodi) saat harga menolak/mantul dari *Support* atau *Resistance*.

**13 Pasukan Metode (User Suite) Aktif:**
1. **CRT Sweep** (Sapuan likuiditas H4 & D1)
2. **H1 Breakout**
3. **M15 Double Top**
4. **FVG Rejection** (Pinbar Retest)
5. **IFVG Breakout & Retest** (Momentum Jebol / Pantul Inversion FVG)
6. **Support/Resistance Rejection** (Pinbar Retest)
7. **CHoCH Reversal** (Reversal Kuat M5/M15)
8. **BOS Momentum** (Continuation)
9. **OTE Retrace** (Pinbar Fib 0.618-0.786)
10. **Breaker Block Retest** (Pinbar di OB Jebol)
11. **Asian Session Sweep** (Reversal di Tokyo Killzone)
12. **OB + FVG Confluence** (Power of 3 Sniper Entry)
13. **POI Accumulation** (Breakout Ketat Konsolidasi)

### 3. Market Alert Engine (`market_alert_engine.py`)
Mata-mata *market structure* yang akan memberikan notifikasi ke Telegram Anda.
- **Bebas Noise**: Alert dari Timeframe M1 **telah dimatikan secara permanen**. Anda hanya akan menerima struktur valid dari M5 ke atas.

### 4. Performance Reporter (Event-Driven)
Tidak perlu menunggu *cron* per 30 menit! Modul ini **langsung memicu (trigger)** laporan otomatis ke Telegram seketika (*real-time*) setiap kali sebuah posisi ditutup, menampilkan semua status (🟢, 🟠, 🔴, ⚪) dari seluruh arsenal metode yang ada.

---

## 🧬 Antigravity Auto-Mutator (Pengganti DeepSeek)
Sistem mutasi internal bot (DeepSeek API) telah **DIBEKUKAN**. Sekarang, proses evaluasi 100% diambil alih oleh **Antigravity (Google Gemini Agent)** dari luar bot.

1. **Antigravity Monitor**: *Script* `scratch_antigravity_monitor.py` terus berputar di *background* setiap 5 detik untuk memindai Database SQLite.
2. **Reaktif Waking**: Jika *Stop Loss* terjadi, script ini akan menemukan SL yang belum dievaluasi dan langsung "membangunkan" agen Antigravity.
3. **Pembedahan Kode (Mutasi)**: Antigravity akan merombak kode Python di `market_brain.py` secara presisi untuk menutupi kelemahan metode tersebut.
4. **Reinkarnasi (Memory Reset)**: Metode yang sudah dimutasi akan dihapus "dosa masa lalunya" (Win Rate dikembalikan ke 0/0) agar memiliki kesempatan membuktikan diri lagi sebagai entitas baru, menghindari pemblokiran (*Auto-Block*) prematur dari bot.
5. Telegram menerima notifikasi: `🧬 HOT-RELOAD: Otak bot berhasil dimutasi (Hyper-Evolution) secara otomatis!`

Semua ini terjadi secara otonom tanpa memerlukan persetujuan (`YES/NO`) dari Anda!

---

## 🕹️ Komando Telegram Dasar (CLI)
Saat berjalan, Anda punya arsenal komando berikut melalui Terminal/Telegram:
- `/status` / `/price` / `/signal` : Komando sinyal standar.
- `/poi` : Mencetak Peta *Point of Interest* Multi-Timeframe.
- `/stats` : Rangkuman memori kemenangan/kekalahan hari ini.
- `/kb_stats` : Statistik *Knowledge Base*.
- `/exit` : Mematikan bot dengan aman.

---

## ⏳ Background Tasks (Cron Jobs & Monitors)

1. **Morning Routine Dev Report (Jam 5 Pagi / 22:00 UTC)**
   - Cron: `0 22 * * *`
   - Prompt/Tugas: `1. Review bot performance/mutasi. 2. Mini Backtest: Uji coba mutasi ke data 3 hari terakhir sebelum diterapkan. 3. Daily Bias Outlook: Analisa trend D1/H4 lalu kirim forecast (ramalan cuaca market) ke Telegram.`
2. **Antigravity SL Monitor**
   - Perintah: `python3 scratch_antigravity_monitor.py` (Berjalan permanen di *background*)
   - Tugas: Menjadi radar pendeteksi LOSS yang otomatis menyalakan proses Reinkarnasi Metode.

---
*Dokumen ini merupakan "Living Document". Setiap mutasi atau perubahan struktural pada logika AI wajib di-update langsung ke dokumen ini agar tersinkronisasi sempurna dengan otak bot.*
