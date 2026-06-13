#!/bin/bash
set -e

echo "Starting 17-Month Marathon (Jan 2025 - May 2026)..."

# 2025 (Resumed from July)
python3 src/run_simulator.py --month 202507
python3 src/run_simulator.py --month 202508
python3 src/run_simulator.py --month 202509
python3 src/run_simulator.py --month 202510
python3 src/run_simulator.py --month 202511
python3 src/run_simulator.py --month 202512

# 2026
python3 src/run_simulator.py --month 202601
python3 src/run_simulator.py --month 202602
python3 src/run_simulator.py --month 202603
python3 src/run_simulator.py --month 202604
python3 src/run_simulator.py --month 202605

echo "Marathon Finished Successfully!"
