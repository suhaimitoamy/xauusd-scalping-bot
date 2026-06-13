import sqlite3
from typing import List, Dict, Any


class LiquidityEngine:
    def __init__(self, storage=None, swing_length: int = 3,
                 eq_threshold: float = 0.5):
        self.swing_length = swing_length
        self.eq_threshold = eq_threshold
        self.storage = storage

    def detect_pools(self, symbol: str, timeframe: str,
                     candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        new_pools = []
        sl = self.swing_length
        if not candles or len(candles) < sl * 2 + 1:
            return new_pools

        swing_highs = []
        swing_lows = []

        for i in range(sl, len(candles) - sl):
            is_sh = True
            is_sl = True
            for j in range(1, sl + 1):
                if candles[i]['high'] <= candles[i -
                                                 j]['high'] or candles[i]['high'] <= candles[i + j]['high']:
                    is_sh = False
                if candles[i]['low'] >= candles[i -
                                                j]['low'] or candles[i]['low'] >= candles[i + j]['low']:
                    is_sl = False

            if is_sh:
                swing_highs.append({'price': candles[i]['high'], 'idx': i})
            if is_sl:
                swing_lows.append({'price': candles[i]['low'], 'idx': i})

        # Find EQH
        for i in range(len(swing_highs)):
            for j in range(i + 1, len(swing_highs)):
                diff = abs(swing_highs[i]['price'] - swing_highs[j]['price'])
                if diff <= self.eq_threshold:
                    new_pools.append({
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'pool_type': 'EQH',
                        'level': max(swing_highs[i]['price'], swing_highs[j]['price']),
                        'status': 'ACTIVE'
                    })

        # Find EQL
        for i in range(len(swing_lows)):
            for j in range(i + 1, len(swing_lows)):
                diff = abs(swing_lows[i]['price'] - swing_lows[j]['price'])
                if diff <= self.eq_threshold:
                    new_pools.append({
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'pool_type': 'EQL',
                        'level': min(swing_lows[i]['price'], swing_lows[j]['price']),
                        'status': 'ACTIVE'
                    })

        return new_pools

    def save_pools(self, pools: List[Dict[str, Any]]):
        if not self.storage or not pools:
            return

        conn = self.storage.get_connection()
        cursor = conn.cursor()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        for p in pools:
            cursor.execute('''
                INSERT OR IGNORE INTO liquidity_pools (
                    symbol, timeframe, pool_type, level, status, created_at, sweep_time
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
            ''', (p['symbol'], p['timeframe'], p['pool_type'], p['level'], p['status'], now))

        conn.commit()
        conn.close()

    def format_liquidity_map(self):
        if not self.storage:
            return "Storage not initialized."
        try:
            conn = self.storage.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM liquidity_pools WHERE status='ACTIVE' ORDER BY level DESC")
            pools = cursor.fetchall()
            conn.close()
        except BaseException:
            pools = []

        if not pools:
            return "### Liquidity Pools Map\nNo *active* liquidity pools mapped."

        lines = ["### Liquidity Pools Map"]
        for p in pools:
            lines.append(
                f"- 💧 **{p['pool_type']} [{p['timeframe']}]**: {p['level']:.3f}")
        return "\n".join(lines)


def format_liquidity_map(storage, symbol):
    engine = LiquidityEngine(storage)
    return engine.format_liquidity_map()
