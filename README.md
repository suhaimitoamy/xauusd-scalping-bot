# 🤖 XAUUSD Adaptive Brain Bot V7

Bot lokal untuk membantu membaca, memetakan, dan memberi sinyal XAUUSD berdasarkan data candle, market structure, Smart Money Concepts, dan memori performa metode.

Project ini berjalan di **Termux Android** dan terhubung ke **Telegram** untuk mengirim notifikasi, edukasi signal, market alert, dan ringkasan mapping.

---

## Status Project Saat Ini

```text
🤖 BOT AKTIF

Sistem sudah online.
Silakan kirim pertanyaan di kolom komentar.
```

Mode utama project saat ini:

```text
Source utama       : Local Brain + AI Trainer
AI Telegram        : OFF
AI fallback        : OFF secara default
Edukasi Telegram   : Bot lokal
Signal             : M1 dan M5 berjalan terpisah
Market alert       : Aktif
Knowledge          : Local Knowledge Agent + knowledge_seed.json
Database           : SQLite lokal
```

---

## Fungsi Utama

### 1. Signal Bot

Bot membaca setup BUY/SELL dari metode yang aktif di `market_brain.py` dan menyimpan hasilnya ke database SQLite.

Signal utama mencakup:

- Arah signal: BUY / SELL / NO TRADE
- Entry area
- Stop Loss
- TP1
- TP2
- Invalidasi
- Pattern / metode
- Confidence
- Reason signal
- Status signal
- Result signal

M1 dan M5 berjalan sebagai stream signal yang terpisah.

---

### 2. Market Structure Alert

Bot membaca struktur market dan mengirim alert Telegram untuk kondisi seperti:

- BOS valid / invalid
- CHOCH valid / invalid
- MSS valid / invalid
- Support break valid / invalid
- Resistance break valid / invalid
- Sweep reclaim valid / invalid
- Fake break
- Trend invalidation
- Retest mode

Invalidasi trend:

```text
Bullish invalid jika Higher Low jebol
Bearish invalid jika Lower High jebol
```

---

### 3. Early Warning Alert

Bot juga punya mode early warning sebelum candle benar-benar confirm.

Early warning yang tersedia:

- Support sedang disweep
- Resistance sedang disweep
- Support break bearish sedang terbentuk
- Resistance break bullish sedang terbentuk
- CHOCH/MSS bullish sedang terbentuk
- CHOCH/MSS bearish sedang terbentuk
- Trend bullish hampir invalid
- Trend bearish hampir invalid

Confirmed `VALID / INVALID` tetap dikirim setelah validasi close candle.

---

### 4. Mapping Assistant

Mapping assistant membantu membaca kondisi market sebelum mengambil keputusan.

Komponen mapping:

- Session context WIB / New York
- EST / EDT otomatis
- London Killzone
- New York Killzone
- D1 / H4 / H1 bias
- Range high / range low / equilibrium
- Premium / discount
- BSL / SSL
- Equal high / equal low
- PDH / PDL
- FVG aktif
- Order Block aktif
- Liquidity map
- Market narrative

Script utama:

```bash
python scripts/send_mapping_summary.py
python scripts/send_mapping_summary.py --send
```

---

### 5. Order Block dan FVG Mapping

Bot memetakan area penting seperti:

- Bullish OB
- Bearish OB
- OB fresh
- OB touched
- OB invalid
- Bullish FVG
- Bearish FVG
- FVG fresh
- FVG partial
- FVG invalid / IFVG

Area ini digunakan sebagai area pantau, bukan tombol entry otomatis.

---

### 6. Telegram Edukasi Lokal

Telegram sekarang memakai **bot lokal**, bukan AI bebas.

Sumber edukasi Telegram:

```text
src/local_knowledge_agent.py
/data/knowledge_seed.json
```

Pertanyaan seperti ini dijawab dari signal aktif / signal terakhir:

```text
Enaknya sell atau buy?
Buy atau sell?
Kenapa?
Alasannya?
Detail signal?
Kenapa sell?
Kenapa buy?
```

Jawaban edukasi signal berisi:

- Rekomendasi BUY/SELL
- Current price
- Entry
- SL
- TP1
- TP2
- Invalidasi
- Pattern
- Timeframe
- Class
- Reason signal
- Bias M15
- Bias H1
- Momentum M5
- ATR
- Choppy
- Zone terakhir
- OB terakhir
- FVG terakhir
- Status valid / invalidasi

Pertanyaan konsep market juga dijawab lokal, misalnya:

```text
Apa itu FVG?
Apa itu OB?
Apa itu CHOCH?
Apa itu BOS?
Apa itu MSS?
Apa itu liquidity?
Apa itu inducement?
Apa itu premium discount?
Apa itu OTE?
```

---

### 7. AI Trainer Lokal

AI Trainer lokal menyimpan hasil evaluasi metode berdasarkan hasil signal.

Contoh output:

```text
🧠 AI TRAINER RESULT
Signal: #70 SELL
Result: LOSS / WIN
Pattern: METHOD_CHOCH_REVERSAL_SELL
Reward: +0.0
Penalty: -10.0
Pattern score: -10.0
```

AI Trainer digunakan untuk membaca performa metode, bukan untuk menjawab bebas seperti chatbot.

---

## File Penting

```text
main.py                              # Entry point bot
config.yaml                          # Konfigurasi utama
src/market_brain.py                  # Otak signal dan metode
src/market_structure.py              # BOS/CHOCH/MSS/break/sweep/invalidasi
src/local_knowledge_agent.py         # Jawaban Telegram lokal
src/telegram_interactive.py          # Polling dan routing Telegram
src/telegram_notifier.py             # Kirim pesan Telegram
src/storage.py                       # SQLite storage
src/session_context.py               # WIB, NY, EST/EDT, killzone
src/mapping_assistant.py             # Ringkasan mapping market
src/htf_bias_engine.py               # Bias D1/H4/H1
src/range_map.py                     # Range, premium, discount, EQ
src/liquidity_map.py                 # BSL, SSL, EQH, EQL, PDH, PDL
src/order_block_engine.py            # OB mapping
src/fvg_mapping.py                   # FVG mapping
src/market_narrative.py              # Kesimpulan mapping
scripts/send_mapping_summary.py      # Print/kirim mapping ke Telegram
data/knowledge_seed.json             # Knowledge edukasi lokal
data/xauusd_bot.sqlite               # Database utama
```

---

## Cara Menjalankan di Termux

Masuk ke folder project:

```bash
cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot
```

Jalankan bot:

```bash
python main.py
```

Jalankan mapping summary:

```bash
python scripts/send_mapping_summary.py
```

Kirim mapping summary ke Telegram:

```bash
python scripts/send_mapping_summary.py --send
```

Push perubahan ke GitHub:

```bash
git add .
git commit -m "update project"
git push origin main
```

---

## Environment Telegram

Minimal environment yang dibutuhkan:

```bash
export TELEGRAM_BOT_TOKEN="ISI_TOKEN_BOT"
export TELEGRAM_CHAT_ID="ISI_CHAT_ID"
```

Opsional:

```bash
export TELEGRAM_DISCUSSION_CHAT_ID="ISI_CHAT_ID_GROUP_DISKUSI"
export TELEGRAM_PARSE_MODE=""
export TELEGRAM_AI_FALLBACK_ENABLED="false"
export STRUCTURE_TELEGRAM_ALERTS="true"
export EARLY_STRUCTURE_TELEGRAM_ALERTS="true"
export STRUCTURE_ALERT_COOLDOWN_SECONDS="900"
export EARLY_STRUCTURE_ALERT_COOLDOWN_SECONDS="180"
```

---

## Telegram Command yang Umum Dipakai

```text
/price
/signal
/m1_signal
/m5_signal
/alerts
/brain
/methods
/stats
/daily_recap
/market_context
/market_plan
/supply_demand
/fvg
/ob
/liquidity
/ote
/poi
/events
/bot_health
/chat_id
/help
```

Bot juga bisa menjawab pertanyaan bahasa biasa, seperti:

```text
Enaknya sell atau buy?
Kenapa?
Apa itu FVG?
OB terdekat di mana?
Liquidity terdekat di mana?
Support terdekat?
Resistance terdekat?
Bias sekarang?
Market structure sekarang?
```

---

## Catatan Penting

Bot ini adalah alat bantu mapping dan signal, bukan jaminan profit.

Gunakan tetap dengan:

- SL jelas
- lot aman
- risk management
- validasi manual
- hindari overtrade
- jangan entry hanya karena notifikasi

---

## Update Terakhir

README ini disinkronkan dengan kondisi project saat ini:

```text
AI Telegram OFF
Local Knowledge Agent aktif
Signal education satu pintu di local_knowledge_agent.py
Market structure alert aktif
Early warning aktif
Mapping assistant aktif
Startup message robot aktif
```