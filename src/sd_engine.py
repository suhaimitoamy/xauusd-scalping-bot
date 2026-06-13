import sqlite3
from typing import List, Dict, Any


class SupplyDemandEngine:
    def __init__(self, storage=None, swing_length: int = 3):
        self.swing_length = swing_length
        self.storage = storage

    def detect_zones(self, symbol: str, timeframe: str,
                     candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        new_zones = []
        sl = self.swing_length
        if not candles or len(candles) < sl * 2 + 1:
            return new_zones

        for i in range(sl, len(candles) - sl):
            # 1. Supply Zone (Swing High)
            is_swing_high = True
            for j in range(1, sl + 1):
                if candles[i]['high'] <= candles[i -
                                                 j]['high'] or candles[i]['high'] <= candles[i + j]['high']:
                    is_swing_high = False
                    break

            if is_swing_high:
                c = candles[i]
                wick_len = c['high'] - max(c['open'], c['close'])
                body_len = abs(c['open'] - c['close'])
                bearish_rejection = wick_len >= (
                    body_len * 0.5) if body_len > 0 else wick_len > 0

                displacement_idx = min(i + 2, len(candles) - 1)
                bearish_displacement = candles[displacement_idx]['close'] < c['low']

                if bearish_rejection and bearish_displacement:
                    disp_str = candles[i + 1]['open'] - \
                        candles[displacement_idx]['close']
                    if disp_str >= 1.5:
                        strength = 'STRONG' if disp_str > body_len * 2 else 'NORMAL'
                        new_zones.append({
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'zone_type': 'Supply',
                            'low': min(c['open'], c['close']),
                            'high': c['high'],
                            'status': 'VALID',
                            'strength': strength,
                            'reason': 'Swing high + bearish rejection + bearish displacement'
                        })

            # 2. Demand Zone (Swing Low)
            is_swing_low = True
            for j in range(1, sl + 1):
                if candles[i]['low'] >= candles[i -
                                                j]['low'] or candles[i]['low'] >= candles[i + j]['low']:
                    is_swing_low = False
                    break

            if is_swing_low:
                c = candles[i]
                wick_len = min(c['open'], c['close']) - c['low']
                body_len = abs(c['open'] - c['close'])
                bullish_rejection = wick_len >= (
                    body_len * 0.5) if body_len > 0 else wick_len > 0

                displacement_idx = min(i + 2, len(candles) - 1)
                bullish_displacement = candles[displacement_idx]['close'] > c['high']

                if bullish_rejection and bullish_displacement:
                    disp_str = candles[displacement_idx]['close'] - \
                        candles[i + 1]['open']
                    if disp_str >= 1.5:
                        strength = 'STRONG' if disp_str > body_len * 2 else 'NORMAL'
                        new_zones.append({
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'zone_type': 'Demand',
                            'low': c['low'],
                            'high': max(c['open'], c['close']),
                            'status': 'VALID',
                            'strength': strength,
                            'reason': 'Swing low + bullish rejection + bullish displacement'
                        })

        return new_zones

    def save_zones(self, zones: List[Dict[str, Any]]):
        if not self.storage or not zones:
            return

        conn = self.storage.get_connection()
        cursor = conn.cursor()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        for z in zones:
            cursor.execute('''
                INSERT INTO supply_demand_zones (
                    symbol, timeframe, zone_type, low, high, status, created_at, strength, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (z['symbol'], z['timeframe'], z['zone_type'], z['low'], z['high'], z['status'], now, z['strength'], z['reason']))

        conn.commit()
        conn.close()

    def format_sd_map(self):
        if not self.storage:
            return "Storage not initialized."
        try:
            conn = self.storage.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM supply_demand_zones WHERE status IN ('VALID', 'TOUCHED') ORDER BY timeframe DESC, created_at DESC")
            zones = cursor.fetchall()
            conn.close()
        except BaseException:
            zones = []

        if not zones:
            return "### Supply & Demand Zones Map\nNo *valid* or *touched* zones currently mapped."

        lines = ["### Supply & Demand Zones Map"]
        for z in zones:
            status_icon = "🟡" if z['status'] == 'TOUCHED' else "🟢"
            lines.append(
                f"- {status_icon} **{z['zone_type']} [{z['timeframe']}]**: {z['low']:.3f} - {z['high']:.3f} | Strength: **{z['strength']}**")
        return "\n".join(lines)


def format_sd_map(storage, symbol):
    engine = SupplyDemandEngine(storage)
    return engine.format_sd_map()
