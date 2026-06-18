from __future__ import annotations

import os
from functools import wraps
from typing import Any

LIVE_CONTEXT_LIMITS = {
    "M5": 80,
    "M15": 64,
    "H1": 96,
}

OLD_SIMULATOR_LIMITS = {
    "M5": 60,
    "M15": 32,
    "H1": 12,
}


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def apply_backtest_live_context_patch() -> None:
    """Make simulator candle context match live bot context.

    Live main.py uses:
    - M5  : 80 candles
    - M15 : 64 candles
    - H1  : 96 candles

    Old src/run_simulator.py asks for:
    - M5  : 60 candles
    - M15 : 32 candles
    - H1  : 12 candles

    This patch keeps live code unchanged and only expands those old simulator
    requests during backtest runs.
    """
    if not _truthy(os.environ.get("BACKTEST_MATCH_LIVE_CONTEXT", "true")):
        return

    try:
        from src.storage import Storage
    except Exception:
        return

    if getattr(Storage, "_amy_backtest_live_context_patched", False):
        return

    original_get_recent_candles = Storage.get_recent_candles

    @wraps(original_get_recent_candles)
    def get_recent_candles_live_context(self, symbol, timeframe, limit=100):
        tf = str(timeframe or "").upper()
        try:
            requested_limit = int(limit)
        except Exception:
            requested_limit = limit

        if tf in LIVE_CONTEXT_LIMITS and requested_limit == OLD_SIMULATOR_LIMITS.get(tf):
            limit = LIVE_CONTEXT_LIMITS[tf]

        return original_get_recent_candles(self, symbol, timeframe, limit)

    Storage.get_recent_candles = get_recent_candles_live_context
    Storage._amy_backtest_live_context_patched = True
