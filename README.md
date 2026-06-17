# XAUUSD Adaptive Brain Bot V7

Local Python project untuk XAUUSD scalping bot dengan Telegram command, SQLite candle storage, market context, dan candle calibration.

## Fokus update terbaru

Update terbaru hanya memperbaiki kesehatan data candle, market context, dan output Telegram.

Tidak diubah:

- metode trading
- rule entry
- risk management
- SignalGate

## Candle calibration

Bot sekarang membedakan:

- live price
- last closed M5
- last closed M15
- last closed H1
- last closed H4

Higher timeframe candle dibuat dari closed M5 candle:

- M15 = 3 closed M5 candle
- H1 = 12 closed M5 candle
- H4 = 48 closed M5 candle

M15/H1/H4 tidak lagi dipercaya dari fallback candle asal jika tidak sinkron.

## Freshness check

`/market_context` sekarang menampilkan status freshness per timeframe:

- M5 fresh/stale
- M15 fresh/stale
- H1 fresh/stale
- H4 fresh/stale

Setiap timeframe menampilkan:

- last candle time UTC
- close time UTC
- age in minutes
- status FRESH/STALE
- OHLC last closed candle

Jika HTF stale atau data tidak sinkron, market decision menjadi:

```text
DATA STALE / WAIT
```

## Future candle protection

Bot menolak candle yang timestamp-nya terlalu jauh dari waktu server/Termux.

Efeknya:

- candle masa depan tidak dipakai
- age candle tidak lagi 0.0m palsu
- output TradingView calibration lebih aman dibandingkan berdasarkan UTC yang sama

## Telegram command utama

```text
/market_context
```

Output berisi:

- live price
- status data: FRESH / PARTIAL STALE / DATA STALE
- market decision: WAIT BUY / WAIT SELL / CONFLICT / WAIT / DATA STALE
- bias M15, H1, H4, D1
- phase structure
- supply / demand
- liquidity
- last closed candle OHLC M5, M15, H1, H4
- freshness status per timeframe

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

Bersihkan candle future lama jika pernah ada data timestamp salah:

```bash
sqlite3 data/xauusd_bot.sqlite "
DELETE FROM candles
WHERE julianday(open_time) > julianday('now', '+2 minutes')
   OR julianday(close_time) > julianday('now', '+2 minutes');
"
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

## Catatan kalibrasi

Cocokkan OHLC bot dengan TradingView memakai waktu UTC yang sama.

Contoh normal:

- HP 17:16 WITA
- UTC sekitar 09:16
- M5 last UTC 09:10 close 09:14:59
- M15 last UTC 09:00 close 09:14:59
- H1 last UTC 08:00 close 08:59:59
- H4 last UTC 04:00 close 07:59:59

Jika Telegram muncul `409 Conflict`, berarti ada lebih dari satu terminal/bot polling yang aktif. Matikan semua lalu jalankan ulang satu bot saja:

```bash
pkill -f "python main.py"
python main.py
```
