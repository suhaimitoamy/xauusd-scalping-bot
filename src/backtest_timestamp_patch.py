from __future__ import annotations

from functools import wraps
from typing import Any


def apply_backtest_timestamp_patch() -> None:
    """Allow historical timestamps only inside simulator/backtest.

    Live CandleBuilder stays unchanged.
    This patch is loaded by run_bulan.py before src/run_simulator.py runs.
    """
    try:
        from src.candle_builder import CandleBuilder
        from src.candle_sync import parse_utc
    except Exception:
        return

    if getattr(CandleBuilder, "_amy_backtest_timestamp_patched", False):
        return

    original_normalize_timestamp = CandleBuilder._normalize_timestamp

    @wraps(original_normalize_timestamp)
    def normalize_timestamp_for_backtest(self, timestamp: Any):
        ts = None
        try:
            ts = float(timestamp)
        except (ValueError, TypeError):
            dt = parse_utc(timestamp)
            if dt:
                ts = dt.timestamp()

        if ts is None:
            return original_normalize_timestamp(self, timestamp)

        if ts > 10_000_000_000:
            ts = ts / 1000.0

        return int(ts)

    CandleBuilder._normalize_timestamp = normalize_timestamp_for_backtest
    CandleBuilder._amy_backtest_timestamp_patched = True
