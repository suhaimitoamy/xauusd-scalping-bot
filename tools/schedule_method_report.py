#!/usr/bin/env python3
"""CLI wrapper for scheduled method evaluator.

Examples:
  python tools/schedule_method_report.py --period weekly --send-telegram
  python tools/schedule_method_report.py --period monthly --send-telegram
"""
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if load_dotenv:
    load_dotenv(ROOT / ".env")

from src.scheduled_method_evaluator import main

if __name__ == "__main__":
    raise SystemExit(main())
