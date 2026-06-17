# XAUUSD Adaptive Brain Bot V7

XAUUSD Adaptive Brain Bot V7 adalah project bot scalping XAUUSD berbasis Python yang berjalan secara lokal di Termux/Android. Bot ini membaca harga live, membangun candle, menyimpan data ke SQLite, membuat market context, mengirim output ke Telegram, dan menyediakan command untuk memantau kondisi market.

Project ini digunakan untuk membantu membaca konteks market XAUUSD, memantau candle multi-timeframe, melihat bias intraday, membaca supply/demand, liquidity, phase structure, dan menjaga kualitas data sebelum sinyal trading dipercaya.

## Tujuan Project

Tujuan utama project ini adalah membuat bot monitoring dan analisis XAUUSD yang bisa:

- membaca harga live XAUUSD
- menyimpan tick dan candle ke SQLite
- membangun candle M5, M15, H1, H4, dan D1
- menampilkan market context melalui Telegram
- memantau bias multi-timeframe
- menampilkan supply/demand dan liquidity
- menjaga kualitas data candle agar tidak membaca candle stale atau candle masa depan
- memberi status WAIT jika data candle belum sehat

## Fitur Utama

- Live price XAUUSD dari websocket/API
- Penyimpanan tick ke SQLite
- Penyimpanan candle ke SQLite
- Candle builder multi-timeframe
- Market context Telegram
- Bias M15, H1, H4, D1
- Phase structure
- Supply/demand zone
- Liquidity level
- Freshness check candle
- Future candle protection
- Telegram command polling
- Local bot command via CLI
- Signal tracking
- Market alert engine
- Adaptive brain engine

## Cara Kerja Singkat

Alur kerja bot:

```text
Live price websocket/API
        ↓
Tick diterima bot
        ↓
Tick disimpan ke SQLite
        ↓
Candle M5 dibentuk
        ↓
M15/H1/H4 dibangun dari closed M5
        ↓
Market context membaca candle valid
        ↓
Telegram menampilkan status market
```

Bot tidak langsung mempercayai data candle. Setiap timeframe dicek apakah candle masih fresh atau sudah stale.

Jika data HTF tidak sehat, bot tidak memaksa bias BUY/SELL dan akan mengeluarkan status:

```text
DATA STALE / WAIT
```

## Sistem Candle

Bot membedakan antara:

- live price
- last closed M5
- last closed M15
- last closed H1
- last closed H4

Higher timeframe candle dibuat dari closed M5 candle:

- M15 = 3 closed M5 candle
- H1 = 12 closed M5 candle
- H4 = 48 closed M5 candle

Tujuannya agar M15, H1, dan H4 tidak terbentuk dari fallback candle yang salah atau tidak sinkron.

## Freshness Check

`/market_context` menampilkan freshness status untuk:

- M5
- M15
- H1
- H4

Setiap timeframe menampilkan:

- last candle time UTC
- close time UTC
- age in minutes
- status FRESH/STALE
- OHLC last closed candle

Status data bisa menjadi:

```text
FRESH
PARTIAL STALE
DATA STALE
```

## Future Candle Protection

Bot menolak candle yang timestamp-nya terlalu jauh dari waktu server/Termux.

Fitur ini mencegah:

- candle masa depan terbaca sebagai candle fresh
- age candle menjadi 0.0m palsu
- bias market dibangun dari waktu candle yang salah
- output Telegram berbeda jauh dari TradingView karena timestamp error

## Telegram Command

Command utama:

```text
/market_context
```

Output `/market_context` berisi:

- live price
- status data: FRESH / PARTIAL STALE / DATA STALE
- market decision: WAIT BUY / WAIT SELL / CONFLICT / WAIT / DATA STALE
- bias M15, H1, H4, D1
- phase structure
- supply / demand
- liquidity
- last closed candle OHLC M5, M15, H1, H4
- freshness status per timeframe

Command lain yang tersedia di bot:

```text
/signal
/m1_signal
/m5_signal
/daily_recap
/alerts
/brain
/events
/ai_review
/trainer_review
/pending
/methods
/supply_demand
/ask
/bot_health
/price
/stats
/telegram_status
/test_telegram
```

## Struktur Data SQLite

Database utama menyimpan:

- ticks
- candles
- signals
- signal_events
- structure_events
- supply_demand_zones
- liquidity_pools
- active_fvgs
- active_order_blocks
- active_breakers
- active_ote_zones

Tabel candle menyimpan:

- symbol
- timeframe
- open_time
- close_time
- open
- high
- low
- close
- volume_tick
- is_closed

## Termux

Masuk folder repo:

```bash
cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot
```

Update repo:

```bash
git pull origin main
```

Pastikan hanya satu bot yang jalan:

```bash
pkill -f "python main.py"
```

Jalankan bot:

```bash
python main.py
```

Cek waktu Termux:

```bash
date
date -u
```

Cek Telegram:

```text
/market_context
```

## Membersihkan Candle Future Lama

Jika sebelumnya pernah ada candle dengan timestamp salah atau candle masa depan, bersihkan dengan:

```bash
sqlite3 data/xauusd_bot.sqlite "
DELETE FROM candles
WHERE julianday(open_time) > julianday('now', '+2 minutes')
   OR julianday(close_time) > julianday('now', '+2 minutes');
"
```

## Catatan Kalibrasi TradingView

Cocokkan OHLC bot dengan TradingView memakai waktu UTC yang sama.

Contoh normal:

- HP 17:16 WITA
- UTC sekitar 09:16
- M5 last UTC 09:10 close 09:14:59
- M15 last UTC 09:00 close 09:14:59
- H1 last UTC 08:00 close 08:59:59
- H4 last UTC 04:00 close 07:59:59

Jika time candle bot lebih maju dari UTC asli, berarti data candle belum sehat.

## Masalah Umum

### Telegram 409 Conflict

Artinya ada lebih dari satu terminal/bot polling yang aktif.

Solusi:

```bash
pkill -f "python main.py"
python main.py
```

### Market context DATA STALE

Artinya salah satu candle M5/M15/H1/H4 belum fresh atau tidak sinkron.

Bot akan menunggu dan tidak memaksa bias BUY/SELL.

### Age candle 0.0m terus

Kemungkinan:

- ada bot lama yang masih jalan
- timestamp provider salah
- database masih menyimpan candle future
- waktu Termux/server tidak sesuai

## Batasan

Bot ini adalah alat bantu monitoring dan analisis market. Bot tidak menjamin profit dan tidak menggantikan keputusan trading manual.

## Update Terbaru

Update terbaru fokus pada kesehatan data candle, market context, dan output Telegram.

Tidak diubah:

- metode trading
- rule entry
- risk management
- SignalGate
