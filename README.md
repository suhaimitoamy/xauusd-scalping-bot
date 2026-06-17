# XAUUSD Adaptive Brain Bot V7

Local Python project for chart context, Telegram commands, and SQLite storage.

## Current focus

- Local brain
- Telegram local replies
- M5 automatic candle processing
- Manual M1 and M5 command checks
- Context output
- Candle calibration output
- SQLite local database

## Termux

```bash
cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot
python main.py
```

## Calibration

`/market_context` includes recent candle OHLC for M5, M15, H1, and H4 so the local database can be compared with chart candles.
