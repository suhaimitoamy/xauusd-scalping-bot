#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"
python3 src/run_pnl_learning_loop.py --start-month 202501 --end-month 202605 --initial-balance 3000 --risk-percent 2 --cycles 1 --main-db --natural-selection
