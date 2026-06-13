import sqlite3
import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class OTEEngine:
    def __init__(self, storage=None):
        self.storage = storage

    def detect_ote(self, candles, timeframe):
        """
        Detect Optimal Trade Entry (OTE) zones from candles.
        Returns a list of dicts.
        """
        if len(candles) < 3:
            return []

        # Basic swing detection for OTE
        highs = [c['high'] for c in candles[-15:]]
        lows = [c['low'] for c in candles[-15:]]
        swing_high = max(highs)
        swing_low = min(lows)

        if swing_high == swing_low:
            return []

        current_close = candles[-1]['close']
        mid = (swing_high + swing_low) / 2

        # Determine direction based on recent momentum
        direction = "BULLISH" if current_close > mid else "BEARISH"
        range_size = swing_high - swing_low

        if direction == 'BULLISH':
            # Retracement down from swing high
            fib_062 = swing_high - (range_size * 0.62)
            fib_079 = swing_high - (range_size * 0.79)
            ote_high = fib_062
            ote_low = fib_079
        else:
            # Retracement up from swing low
            fib_062 = swing_low + (range_size * 0.62)
            fib_079 = swing_low + (range_size * 0.79)
            ote_low = fib_062
            ote_high = fib_079

        return [{
            "symbol": candles[0].get('symbol', 'XAUUSD'),
            "timeframe": timeframe,
            "ote_zone_low": ote_low,
            "ote_zone_high": ote_high,
            "ote_direction": direction,
            "ote_status": "ACTIVE",
            "fib_062": fib_062,
            "fib_079": fib_079,
            "swing_low": swing_low,
            "swing_high": swing_high,
            "confluence": 0
        }]

    def get_active_ote(self, symbol="XAUUSD"):
        if not self.storage:
            return []
        conn = self.storage.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM active_ote_zones WHERE symbol=? AND status='ACTIVE' ORDER BY created_at DESC",
            (symbol,
             ))
        rows = cursor.fetchall()
        conn.close()

        result = []
        for r in rows:
            d = dict(r)
            try:
                raw = json.loads(d.get('raw_json', '{}'))
            except BaseException:
                raw = {}
            # Format output identically to requirements
            result.append({
                "id": d['id'],
                "ote_zone_low": d['low'],
                "ote_zone_high": d['high'],
                "ote_direction": d['direction'],
                "ote_status": d['status'],
                "fib_062": raw.get('fib_062', d['low']),
                "fib_079": raw.get('fib_079', d['high']),
                "swing_low": raw.get('swing_low', d['low']),
                "swing_high": raw.get('swing_high', d['high']),
                "confluence": raw.get('confluence', 0)
            })
        return result

    def save_ote_zone(self, ote):
        if not self.storage:
            return
        conn = self.storage.get_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        raw_json = json.dumps({
            "fib_062": ote.get("fib_062"),
            "fib_079": ote.get("fib_079"),
            "swing_low": ote.get("swing_low"),
            "swing_high": ote.get("swing_high"),
            "confluence": ote.get("confluence", 0)
        })

        # Schema has: id, symbol, timeframe, direction, low, high, status,
        # created_at, source_candle_time, raw_json
        cursor.execute('''
            INSERT INTO active_ote_zones (
                symbol, timeframe, direction, low, high, status, created_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ote.get(
                'symbol', 'XAUUSD'), ote['timeframe'], ote['ote_direction'],
            ote['ote_zone_low'], ote['ote_zone_high'], ote['ote_status'], now, raw_json
        ))
        conn.commit()
        conn.close()

    def update_ote_status(self, current_price, symbol="XAUUSD"):
        active_otes = self.get_active_ote(symbol)
        if not active_otes or not self.storage:
            return

        conn = self.storage.get_connection()
        cursor = conn.cursor()

        for ote in active_otes:
            status = "ACTIVE"
            if ote['ote_direction'] == 'BULLISH':
                if current_price < ote['ote_zone_low']:
                    status = "INVALID"
                elif ote['ote_zone_low'] <= current_price <= ote['ote_zone_high']:
                    status = "HIT"
            else:
                if current_price > ote['ote_zone_high']:
                    status = "INVALID"
                elif ote['ote_zone_low'] <= current_price <= ote['ote_zone_high']:
                    status = "HIT"

            if status != ote['ote_status']:
                cursor.execute(
                    "UPDATE active_ote_zones SET status=? WHERE id=?", (status, ote['id']))
        conn.commit()
        conn.close()

    def format_ote_map(self):
        zones = self.get_active_ote()
        if not zones:
            return "### OTE Zones Map\nNo *active* OTE zones mapped."

        lines = ["### OTE Zones Map"]
        for z in zones:
            lines.append(
                f"- 🎯 **{z['ote_direction']}**: {z['ote_zone_low']:.3f} - {z['ote_zone_high']:.3f} (Status: {z['ote_status']})")
        return "\n".join(lines)


def format_ote_map(storage, symbol="XAUUSD"):
    engine = OTEEngine(storage)
    return engine.format_ote_map()
