#!/usr/bin/env python3
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import yaml
except Exception:
    yaml = None

from src.storage import Storage
from src.mapping_assistant import MappingAssistant


def load_config():
    if yaml and os.path.exists("config.yaml"):
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="send to Telegram")
    parser.add_argument("--symbol", default=None)
    args = parser.parse_args()

    config = load_config()
    symbol = args.symbol or config.get("symbol", "XAU/USD")
    db_path = config.get("db_path", "data/xauusd_bot.sqlite")

    storage = Storage(db_path)
    assistant = MappingAssistant(storage, symbol)

    if args.send:
        ok, snapshot = assistant.send_snapshot()
        print(snapshot["message"])
        print("\nTELEGRAM:", "SENT" if ok else "NOT_SENT")
    else:
        snapshot = assistant.build_snapshot()
        print(snapshot["message"])


if __name__ == "__main__":
    main()
