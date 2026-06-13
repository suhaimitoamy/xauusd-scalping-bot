import logging

logger = logging.getLogger(__name__)


class OrderBlockEngine:
    def __init__(self, storage):
        """
        Initializes the Order Block Engine with a storage instance.
        Expects storage to expose `conn` (an sqlite3 connection) or
        have `execute` and `fetchall` methods.
        """
        self.storage = storage

    def _execute_commit(self, query, params=()):
        conn = self.storage.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()

    def _fetch_all(self, query, params=()):
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def detect_order_blocks(self, timeframe, candles):
        """
        Detects Order Blocks from a list of candles using ICT yang di sempurnakan PineScript logic.
        """
        if len(candles) < 7:
            return []

        detected_obs = []
        for i in range(6, len(candles)):
            c_curr = candles[i]
            c_1 = candles[i - 1]
            c_2 = candles[i - 2]

            # Calculate mean body of 5 candles ending at c_curr
            recent_bodies = [abs(c['close'] - c['open']) for c in candles[i - 4 : i + 1]]
            mean_body = sum(recent_bodies) / len(recent_bodies) if recent_bodies else 0
            
            curr_body = abs(c_curr['close'] - c_curr['open'])
            
            is_bull_disp = c_curr['close'] > c_curr['open'] and curr_body > mean_body and c_curr['close'] > c_2['high']
            is_bear_disp = c_curr['close'] < c_curr['open'] and curr_body > mean_body and c_curr['close'] < c_2['low']

            if is_bull_disp:
                # If c_2 is bearish, use it. Otherwise use c_1.
                if c_2['close'] < c_2['open']:
                    ob_top = max(c_2['open'], c_2['low'])
                    ob_btm = min(c_2['open'], c_2['low'])
                    source_ts = c_2.get('timestamp', 0)
                else:
                    ob_top = max(c_1['open'], c_1['low'])
                    ob_btm = min(c_1['open'], c_1['low'])
                    source_ts = c_1.get('timestamp', 0)
                    
                ob = {
                    'timeframe': timeframe,
                    'type': 'Bullish',
                    'low': ob_btm,
                    'high': ob_top,
                    'status': 'VALID',
                    'strength': 'High',
                    'reason': 'Bullish displacement > high[2]',
                    'timestamp': source_ts
                }
                self.save_order_block(ob)
                detected_obs.append(ob)

            elif is_bear_disp:
                # If c_2 is bullish, use it. Otherwise use c_1.
                if c_2['close'] > c_2['open']:
                    ob_top = max(c_2['high'], c_2['open'])
                    ob_btm = min(c_2['high'], c_2['open'])
                    source_ts = c_2.get('timestamp', 0)
                else:
                    ob_top = max(c_1['high'], c_1['open'])
                    ob_btm = min(c_1['high'], c_1['open'])
                    source_ts = c_1.get('timestamp', 0)

                ob = {
                    'timeframe': timeframe,
                    'type': 'Bearish',
                    'low': ob_btm,
                    'high': ob_top,
                    'status': 'VALID',
                    'strength': 'High',
                    'reason': 'Bearish displacement < low[2]',
                    'timestamp': source_ts
                }
                self.save_order_block(ob)
                detected_obs.append(ob)

        return detected_obs

    def save_order_block(self, ob):
        query = """
            INSERT INTO active_order_blocks
            (timeframe, type, low, high, status, strength, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self._execute_commit(query, (
            ob['timeframe'], ob['type'], ob['low'], ob['high'],
            ob['status'], ob['strength'], ob['reason'], ob.get('timestamp', 0)
        ))

    def save_breaker(self, breaker):
        query = """
            INSERT INTO active_breakers
            (timeframe, type, low, high, status, strength, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self._execute_commit(query, (
            breaker['timeframe'], breaker['type'], breaker['low'], breaker['high'],
            breaker['status'], breaker['strength'], breaker['reason'], breaker.get(
                'timestamp', 0)
        ))

    def update_ob_status(self, ob_id, status):
        query = "UPDATE active_order_blocks SET status = ? WHERE id = ?"
        self._execute_commit(query, (status, ob_id))

    def update_breaker_status(self, breaker_id, status):
        query = "UPDATE active_breakers SET status = ? WHERE id = ?"
        self._execute_commit(query, (status, breaker_id))

    def evaluate_price_action(self, current_price, current_close=None):
        """
        Evaluates current price against active OBs and Breakers.
        Updates status to MITIGATED or INVALID, and creates Breakers if OBs are strongly broken.
        """
        # Fetch all VALID OBs
        try:
            active_obs = self._fetch_all(
                "SELECT * FROM active_order_blocks WHERE status = 'VALID'")
        except Exception as e:
            logger.error(f"Failed to fetch active_order_blocks: {e}")
            active_obs = []

        for ob in active_obs:
            # handle varying id column depending on db setup
            ob_id = ob.get('id', ob.get('rowid'))
            ob_type = ob['type']
            ob_low = float(ob['low'])
            ob_high = float(ob['high'])

            if ob_type == 'Bullish':
                # Valid if not broken below
                if current_close is not None and current_close < ob_low:
                    # Broken down! Becomes a Bearish Breaker (Supply)
                    self.update_ob_status(ob_id, 'INVALID')
                    from src.telegram_notifier import send_telegram_message, telegram_is_configured
                    if telegram_is_configured():
                        send_telegram_message(f"🚨 **WARNING:** Order Block Bullish di {ob_low} - {ob_high} BREAK/JEBOL!\nBerubah menjadi Bearish Breaker (Area Supply Baru).")
                    breaker = {
                        'timeframe': ob['timeframe'],
                        'type': 'Bearish',
                        'low': ob_low,
                        'high': ob_high,
                        'status': 'VALID',
                        'strength': ob['strength'],
                        'reason': 'Bullish OB broken down, turned Bearish Breaker',
                        'timestamp': ob.get('timestamp', 0)
                    }
                    self.save_breaker(breaker)
                    logger.info(
                        f"Bullish OB {ob_id} broken down, created Bearish Breaker.")
                elif ob_low <= current_price <= ob_high:
                    self.update_ob_status(ob_id, 'MITIGATED')
                    logger.info(f"Bullish OB {ob_id} mitigated.")

            elif ob_type == 'Bearish':
                # Valid if not broken above
                if current_close is not None and current_close > ob_high:
                    # Broken up! Becomes a Bullish Breaker (Demand)
                    self.update_ob_status(ob_id, 'INVALID')
                    from src.telegram_notifier import send_telegram_message, telegram_is_configured
                    if telegram_is_configured():
                        send_telegram_message(f"🚨 **WARNING:** Order Block Bearish di {ob_low} - {ob_high} BREAK/JEBOL!\nBerubah menjadi Bullish Breaker (Area Demand Baru).")
                    breaker = {
                        'timeframe': ob['timeframe'],
                        'type': 'Bullish',
                        'low': ob_low,
                        'high': ob_high,
                        'status': 'VALID',
                        'strength': ob['strength'],
                        'reason': 'Bearish OB broken up, turned Bullish Breaker',
                        'timestamp': ob.get('timestamp', 0)
                    }
                    self.save_breaker(breaker)
                    logger.info(
                        f"Bearish OB {ob_id} broken up, created Bullish Breaker.")
                elif ob_low <= current_price <= ob_high:
                    self.update_ob_status(ob_id, 'MITIGATED')
                    logger.info(f"Bearish OB {ob_id} mitigated.")

        # Evaluate active Breakers
        try:
            active_breakers = self._fetch_all(
                "SELECT * FROM active_breakers WHERE status = 'VALID'")
        except Exception as e:
            logger.error(f"Failed to fetch active_breakers: {e}")
            active_breakers = []

        for brk in active_breakers:
            brk_id = brk.get('id', brk.get('rowid'))
            brk_type = brk['type']
            brk_low = float(brk['low'])
            brk_high = float(brk['high'])

            if brk_type == 'Bullish':
                if current_close is not None and current_close < brk_low:
                    self.update_breaker_status(brk_id, 'INVALID')
                elif brk_low <= current_price <= brk_high:
                    self.update_breaker_status(brk_id, 'MITIGATED')

            elif brk_type == 'Bearish':
                if current_close is not None and current_close > brk_high:
                    self.update_breaker_status(brk_id, 'INVALID')
                elif brk_low <= current_price <= brk_high:
                    self.update_breaker_status(brk_id, 'MITIGATED')

    def format_ob_map(self):
        """
        Returns a formatted string of all active Order Blocks and Breakers.
        Supports /ob and /ask queries.
        """
        try:
            obs = self._fetch_all(
                "SELECT * FROM active_order_blocks WHERE status IN ('VALID', 'MITIGATED') ORDER BY timeframe DESC, timestamp DESC")
        except Exception:
            obs = []

        try:
            breakers = self._fetch_all(
                "SELECT * FROM active_breakers WHERE status IN ('VALID', 'MITIGATED') ORDER BY timeframe DESC, timestamp DESC")
        except Exception:
            breakers = []

        lines = ["=== Active Order Blocks ==="]
        if not obs:
            lines.append("No active order blocks.")
        else:
            for ob in obs:
                lines.append(f"[{ob.get('timeframe',
                                        'M1')}] {ob.get('type',
                                                        'Unknown')} OB | Status: {ob.get('status',
                                                                                         'N/A')} | Strength: {ob.get('strength',
                                                                                                                     'N/A')} | Range: {ob.get('low',
                                                                                                                                              0)} - {ob.get('high',
                                                                                                                                                            0)} | Reason: {ob.get('reason',
                                                                                                                                                                                  '')}")

        lines.append("")
        lines.append("=== Active Breaker Blocks ===")
        if not breakers:
            lines.append("No active breaker blocks.")
        else:
            for brk in breakers:
                lines.append(f"[{brk.get('timeframe',
                                         'M1')}] {brk.get('type',
                                                          'Unknown')} Breaker | Status: {brk.get('status',
                                                                                                 'N/A')} | Strength: {brk.get('strength',
                                                                                                                              'N/A')} | Range: {brk.get('low',
                                                                                                                                                        0)} - {brk.get('high',
                                                                                                                                                                       0)} | Reason: {brk.get('reason',
                                                                                                                                                                                              '')}")

        return "\n".join(lines)


def format_ob_map(storage, symbol):
    engine = OrderBlockEngine(storage)
    return engine.format_ob_map()
