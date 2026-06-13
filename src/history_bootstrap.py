import os
import requests
import json
from src.formatter import setup_logger
from datetime import datetime, timezone
import time

logger = setup_logger("DataBootstrapAgent")


def bootstrap_history(storage, config):
    api_key = os.getenv("TWELVE_API_KEY")
    if not api_key:
        logger.warning("TWELVE_API_KEY is empty. Skipping REST bootstrap.")
        return False

    symbol = config.get("symbol", "XAU/USD")
    rest_config = config.get("rest_bootstrap", {})
    if not rest_config.get("enabled", True):
        logger.info("REST bootstrap is disabled in config.")
        return False

    timeframes = {
        "5min": ("M5", rest_config.get("m5_outputsize", 200)),
        "15min": ("M15", rest_config.get("m15_outputsize", 200)),
        "1h": ("H1", rest_config.get("h1_outputsize", 100)),
        "4h": ("H4", rest_config.get("h4_outputsize", 50)),
        "1day": ("D1", rest_config.get("d1_outputsize", 80))
    }

    use_closed_only = rest_config.get("use_closed_candles_only", True)

    logger.info("Starting REST Bootstrap for historical candles...")
    base_url = "https://api.twelvedata.com/time_series"

    success = True
    for td_tf, (internal_tf, limit) in timeframes.items():
        params = {
            "symbol": symbol,
            "interval": td_tf,
            "outputsize": limit,
            "apikey": api_key,
            "format": "JSON"
        }

        try:
            response = requests.get(base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                logger.error(
                    f"Failed to fetch {internal_tf}: {
                        data.get('message')}")
                success = False
                continue

            values = data.get("values", [])
            # Twelve data returns newest first. We reverse it to oldest first for logical processing,
            # though storage uses UPSERT anyway.
            values.reverse()

            saved_count = 0
            for i, row in enumerate(values):
                open_time = row['datetime'] + \
                    ":00" if len(row['datetime']) == 16 else row['datetime']

                # Assume closed if not the very last candle (most recent)
                is_closed = True
                if use_closed_only and i == len(values) - 1:
                    is_closed = False  # The last one might still be forming

                storage.save_candle(
                    symbol=symbol,
                    timeframe=internal_tf,
                    open_time=open_time,
                    close_time=open_time,  # approximate for now
                    open_p=float(row['open']),
                    high_p=float(row['high']),
                    low_p=float(row['low']),
                    close_p=float(row['close']),
                    volume_tick=0,
                    is_closed=is_closed
                )
                saved_count += 1

            logger.info(
                f"Bootstrap {internal_tf}: saved {saved_count} candles.")
            time.sleep(0.5)  # Prevent rate limiting

        except Exception as e:
            logger.error(f"Error bootstrapping {internal_tf}: {e}")
            success = False

    logger.info("REST Bootstrap completed.")
    return success
