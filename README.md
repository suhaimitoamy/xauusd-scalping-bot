# XAUUSD Adaptive Brain Bot V7

Local Python project for XAUUSD chart context, Telegram commands, and SQLite storage.

## Current focus

- Local brain
- Telegram local replies
- M5 automatic candle processing
- Manual M1 and M5 command checks
- Market context output
- Candle calibration output
- SQLite local database

## Important files

```text
main.py
config.yaml
src/market_brain.py
src/market_structure.py
src/market_context_ai.py
src/local_knowledge_agent.py
src/telegram_interactive.py
src/storage.py
scripts/send_mapping_summary.py
```

## Termux

```bash
cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot
python main.py
```

## Useful Telegram commands

```text
/price
/signal
/m1_signal
/m5_signal
/market_context
/market_plan
/supply_demand
/fvg
/ob
/liquidity
/ote
/events
/bot_health
/help
```

## Calibration

`/market_context` includes recent candle OHLC for M5, M15, H1, and H4 so the local database can be compared with chart candles.
