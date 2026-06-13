import sqlite3
import json
import os
from datetime import datetime, timezone


class Storage:
    def __init__(self, db_path='data/xauusd_bot.sqlite'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def execute(self, query, params=()):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        conn.close()

    def fetchall(self, query, params=()):
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def ensure_column(self, cursor, table_name, column_name, column_type):
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in cursor.fetchall()]
        if column_name not in columns:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # ticks
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timestamp_utc TEXT,
                timestamp_local TEXT,
                price REAL,
                raw_json TEXT
            )
        ''')

        # candles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                open_time TEXT,
                close_time TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume_tick INTEGER,
                is_closed INTEGER,
                UNIQUE(symbol, timeframe, open_time)
            )
        ''')

        # signals
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                symbol TEXT,
                direction TEXT,
                status TEXT,
                entry_low REAL,
                entry_high REAL,
                sl REAL,
                tp1 REAL,
                tp2 REAL,
                tp3 REAL,
                invalid_level REAL,
                confidence REAL,
                reason TEXT,
                raw_context_json TEXT,
                result TEXT,
                result_time TEXT
            )
        ''')

        self.ensure_column(cursor, 'signals', 'entry_type', 'TEXT')
        self.ensure_column(cursor, 'signals', 'pending_price', 'REAL')
        self.ensure_column(cursor, 'signals', 'pending_expire_time', 'TEXT')
        self.ensure_column(cursor, 'signals', 'filled_at', 'TEXT')
        self.ensure_column(cursor, 'signals', 'signal_timeframe', 'TEXT')
        self.ensure_column(cursor, 'signals', 'signal_class', 'TEXT')

        # signal_events
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                event_time TEXT,
                event_type TEXT,
                price REAL,
                note TEXT,
                FOREIGN KEY(signal_id) REFERENCES signals(id)
            )
        ''')

        # 1. structure_events
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS structure_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                symbol TEXT,
                timeframe TEXT,
                level REAL,
                price REAL,
                direction TEXT,
                created_at TEXT,
                notified INTEGER,
                raw_json TEXT
            )
        ''')

        # 2. poi_levels
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS poi_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                poi_type TEXT,
                low REAL,
                high REAL,
                strength INTEGER,
                status TEXT,
                created_at TEXT,
                raw_json TEXT
            )
        ''')

        # 3. rule_versions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rule_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_name TEXT,
                created_at TEXT,
                rules_json TEXT,
                status TEXT,
                performance_json TEXT
            )
        ''')

        # 3.5 dynamic_rules
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dynamic_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_key TEXT UNIQUE,
                rule_json TEXT,
                created_at TEXT
            )
        ''')

        # 4. pending_actions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT,
                proposal_json TEXT,
                message TEXT,
                status TEXT,
                created_at TEXT
            )
        ''')

        # 5. ai_reviews
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                review_type TEXT,
                ai_provider TEXT,
                ai_review TEXT,
                confidence_rule REAL,
                confidence_final REAL,
                created_at TEXT,
                raw_json TEXT
            )
        ''')

        # 6. feature_requests
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                username TEXT,
                message TEXT,
                created_at TEXT,
                status TEXT
            )
        ''')

        # 7. user_reports
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                username TEXT,
                message TEXT,
                created_at TEXT,
                status TEXT
            )
        ''')

        # 8. active_order_blocks
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_order_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                direction TEXT,
                type TEXT,
                low REAL,
                high REAL,
                status TEXT,
                strength TEXT,
                reason TEXT,
                created_at TEXT,
                source_candle_time TEXT,
                raw_json TEXT,
                UNIQUE(symbol, timeframe, source_candle_time)
            )
        ''')
        self.ensure_column(cursor, 'active_order_blocks', 'type', 'TEXT')
        self.ensure_column(cursor, 'active_order_blocks', 'reason', 'TEXT')
        self.ensure_column(cursor, 'active_order_blocks', 'timestamp', 'TEXT')
        self.ensure_column(cursor, 'active_order_blocks', 'symbol', 'TEXT')
        self.ensure_column(cursor, 'active_order_blocks', 'direction', 'TEXT')
        self.ensure_column(cursor, 'active_order_blocks', 'source_candle_time', 'TEXT')

        # 9. active_breakers
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_breakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                direction TEXT,
                type TEXT,
                low REAL,
                high REAL,
                status TEXT,
                strength TEXT,
                reason TEXT,
                created_at TEXT,
                source_candle_time TEXT,
                raw_json TEXT,
                UNIQUE(symbol, timeframe, source_candle_time)
            )
        ''')
        self.ensure_column(cursor, 'active_breakers', 'type', 'TEXT')
        self.ensure_column(cursor, 'active_breakers', 'reason', 'TEXT')
        self.ensure_column(cursor, 'active_breakers', 'timestamp', 'TEXT')
        self.ensure_column(cursor, 'active_breakers', 'symbol', 'TEXT')
        self.ensure_column(cursor, 'active_breakers', 'direction', 'TEXT')
        self.ensure_column(cursor, 'active_breakers', 'source_candle_time', 'TEXT')

        # 10. supply_demand_zones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS supply_demand_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                zone_type TEXT,
                low REAL,
                high REAL,
                status TEXT,
                created_at TEXT,
                last_touched_at TEXT,
                strength TEXT,
                reason TEXT,
                raw_json TEXT
            )
        ''')

        self.ensure_column(cursor, 'supply_demand_zones', 'reason', 'TEXT')
        self.ensure_column(cursor, 'supply_demand_zones', 'timestamp', 'TEXT')

        # 11. liquidity_pools
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS liquidity_pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                pool_type TEXT,
                level REAL,
                status TEXT,
                created_at TEXT,
                source_candle_time TEXT,
                raw_json TEXT,
                UNIQUE(symbol, timeframe, level)
            )
        ''')
        self.ensure_column(cursor, 'liquidity_pools', 'timestamp', 'TEXT')
        self.ensure_column(cursor, 'liquidity_pools', 'sweep_time', 'TEXT')
        self.ensure_column(cursor, 'liquidity_pools', 'strength', 'TEXT')

        # 12. active_ote_zones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_ote_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                direction TEXT,
                low REAL,
                high REAL,
                status TEXT,
                created_at TEXT,
                source_candle_time TEXT,
                raw_json TEXT,
                UNIQUE(symbol, timeframe, source_candle_time)
            )
        ''')
        self.ensure_column(cursor, 'active_ote_zones', 'timestamp', 'TEXT')
        self.ensure_column(cursor, 'active_ote_zones', 'strength', 'TEXT')

        # 13. active_fvgs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_fvgs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                direction TEXT,
                low REAL,
                high REAL,
                mid REAL,
                status TEXT,
                created_at TEXT,
                last_touched_at TEXT,
                strength INTEGER,
                source_candle_time TEXT,
                raw_json TEXT,
                UNIQUE(symbol, timeframe, direction, low, high, source_candle_time)
            )
        ''')
        self.ensure_column(cursor, 'active_fvgs', 'timestamp', 'TEXT')

        # 14. setup_confluence
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS setup_confluence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                score INTEGER,
                setup_type TEXT,
                reasons TEXT,
                missing_confirmations TEXT,
                created_at TEXT,
                raw_json TEXT
            )
        ''')

        # 9. fvgs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fvgs_deprecated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                top REAL,
                bottom REAL,
                type TEXT,
                status TEXT,
                mitigated INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def save_tick(self, symbol, timestamp_utc,
                  timestamp_local, price, raw_json):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ticks (symbol, timestamp_utc, timestamp_local, price, raw_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (symbol, timestamp_utc, timestamp_local, price, json.dumps(raw_json)))
            conn.commit()
        finally:
            conn.close()

    def save_candle(self, symbol, timeframe, open_time, close_time,
                    open_p, high_p, low_p, close_p, volume_tick, is_closed):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO candles (symbol, timeframe, open_time, close_time, open, high, low, close, volume_tick, is_closed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
                    close_time=excluded.close_time,
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume_tick=excluded.volume_tick,
                    is_closed=excluded.is_closed
            ''', (symbol, timeframe, open_time, close_time, open_p, high_p, low_p, close_p, volume_tick, 1 if is_closed else 0))
            conn.commit()
        finally:
            conn.close()

    def get_recent_candles(self, symbol, timeframe, limit=100):
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM candles
            WHERE symbol = ? AND timeframe = ? AND is_closed = 1
            ORDER BY open_time DESC LIMIT ?
        ''', (symbol, timeframe, limit))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]

    def save_signal(self, signal):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signals (
                created_at, symbol, direction, status, entry_low, entry_high,
                sl, tp1, tp2, tp3, invalid_level, confidence, reason, raw_context_json,
                entry_type, pending_price, pending_expire_time, signal_timeframe, signal_class
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(timezone.utc).isoformat(),
            signal.get('symbol', 'XAU/USD'),
            signal.get('direction', 'NO_TRADE'),
            signal.get('status', 'ACTIVE' if signal.get(
                'direction') != 'NO_TRADE' else 'NO_TRADE'),
            signal.get('entry_low'),
            signal.get('entry_high'),
            signal.get('sl'),
            signal.get('tp1'),
            signal.get('tp2'),
            signal.get('tp3'),
            signal.get('invalid_level'),
            signal.get('confidence', 0),
            signal.get('reason', ''),
            json.dumps(signal),
            signal.get('entry_type'),
            signal.get('pending_price'),
            signal.get('pending_expire_time'),
            signal.get('signal_timeframe'),
            signal.get('signal_class')
        ))
        conn.commit()
        conn.close()

        # Event-driven: market summary dinonaktifkan (terlalu spam)
        pass

    def get_open_signals(self, signal_timeframe=None):
        """Return only blocking signals.

        V6 supports independent M1 and M5 signal streams. When signal_timeframe
        is supplied, only open signals from that TF are considered blocking.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if signal_timeframe:
            cursor.execute('''
                SELECT * FROM signals
                WHERE status IN ('ACTIVE', 'PENDING_ENTRY')
                  AND COALESCE(signal_timeframe, 'M5') = ?
            ''', (str(signal_timeframe).upper(),))
        else:
            cursor.execute('''
                SELECT * FROM signals WHERE status IN ('ACTIVE', 'PENDING_ENTRY')
            ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_trackable_signals(self):
        """Return signals that still need TP/SL/protect tracking."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM signals
            WHERE status IN ('PENDING_ENTRY', 'ACTIVE', 'PROTECTED', 'TP1_HIT')
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_signal_sl(self, signal_id, new_sl):
        self.execute('''
            UPDATE signals SET sl=? WHERE id=?
        ''', (new_sl, signal_id))

    def mark_pending_filled(self, signal_id, filled_at):
        self.execute('''
            UPDATE signals SET status='ACTIVE', filled_at=? WHERE id=?
        ''', (filled_at, signal_id))

    def expire_pending_signal(self, signal_id, result_time):
        self.execute('''
            UPDATE signals SET status='CLOSED_EXPIRED', result='EXPIRED', result_time=? WHERE id=?
        ''', (result_time, signal_id))

    def update_signal_status(self, signal_id, status, result, result_time):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE signals
            SET status = ?, result = ?, result_time = ?
            WHERE id = ?
        ''', (status, result, result_time, signal_id))
        conn.commit()
        conn.close()

    def add_signal_event(self, signal_id, event_type,
                         price, note, event_time=None):
        if not event_time:
            event_time = datetime.now(timezone.utc).isoformat()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signal_events (signal_id, event_time, event_type, price, note)
            VALUES (?, ?, ?, ?, ?)
        ''', (signal_id, event_time, event_type, price, note))
        conn.commit()
        conn.close()

    def get_stats_today(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*),
                   SUM(CASE WHEN result IN ('WIN','FULL_WIN','PARTIAL_WIN') THEN 1 ELSE 0 END),
                   SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN result = 'PARTIAL_WIN' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN result = 'FULL_WIN' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status IN ('PROTECTED','TP1_HIT') THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status LIKE 'CLOSED%' THEN 1 ELSE 0 END)
            FROM signals
            WHERE created_at LIKE ?
        ''', (f'{today}%',))
        row = cursor.fetchone()
        conn.close()
        return {
            'total': row[0] or 0,
            'wins': row[1] or 0,
            'losses': row[2] or 0,
            'partial_wins': row[3] or 0,
            'full_wins': row[4] or 0,
            'active': row[5] or 0,
            'protected': row[6] or 0,
            'closed': row[7] or 0,
        }


    # Structure Events
    def save_structure_event(self, event_type, symbol,
                             timeframe, level, price, direction, raw_json):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO structure_events (event_type, symbol, timeframe, level, price, direction, created_at, notified, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
        ''', (event_type, symbol, timeframe, level, price, direction, datetime.now(timezone.utc).isoformat(), json.dumps(raw_json)))
        conn.commit()
        conn.close()

    # Pending Actions
    def create_pending_action(self, action_type, message, proposal_json):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pending_actions (action_type, proposal_json, message, status, created_at)
            VALUES (?, ?, ?, 'PENDING', ?)
        ''', (action_type, json.dumps(proposal_json), message, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()

    def get_pending_action(self):
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM pending_actions WHERE status = 'PENDING' ORDER BY id DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def resolve_pending_action(self, action_id, new_status):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pending_actions SET status = ? WHERE id = ?
        ''', (new_status, action_id))
        conn.commit()
        conn.close()

    # Rule Versions
    def save_rule_version(self, version_name, rules_json, status='ACTIVE'):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO rule_versions (version_name, created_at, rules_json, status, performance_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (version_name, datetime.now(timezone.utc).isoformat(), json.dumps(rules_json), status, "{}"))
        conn.commit()
        conn.close()

    def get_active_rule_version(self):
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM rule_versions WHERE status IN ('ACTIVE', 'TRIAL') ORDER BY id DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # Feature Requests & Reports
    def save_feature_request(self, user_id, username, message):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO feature_requests (user_id, username, message, created_at, status)
            VALUES (?, ?, ?, ?, 'PENDING')
        ''', (str(user_id), str(username), message, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()

    def save_user_report(self, user_id, username, message):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            INSERT INTO user_reports (user_id, username, message, created_at, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (str(user_id), username, message, now, 'OPEN'))
        conn.commit()
        conn.close()

    def upsert_fvg(self, fvg_data):
        conn = self.get_connection()
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()
        symbol = fvg_data.get('symbol')
        tf = fvg_data.get('timeframe')
        direction = fvg_data.get('direction')
        low = fvg_data.get('low')
        high = fvg_data.get('high')
        mid = fvg_data.get('mid', (low + high) / 2)
        status = fvg_data.get('status', 'UNFILLED')
        created_at = fvg_data.get('created_at', now)
        last_touched_at = fvg_data.get('last_touched_at', now)
        strength = fvg_data.get('strength', 0)
        source_time = fvg_data.get('source_candle_time')
        raw_json_input = fvg_data.get('raw_json', {})

        import json
        raw_json = json.dumps(raw_json_input) if not isinstance(
            raw_json_input, str) else raw_json_input

        cursor.execute('''
            INSERT INTO active_fvgs (
                symbol, timeframe, direction, low, high, mid, status, created_at, last_touched_at, strength, source_candle_time, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timeframe, direction, low, high, source_candle_time) DO UPDATE SET
                status=excluded.status,
                last_touched_at=excluded.last_touched_at,
                strength=excluded.strength,
                raw_json=excluded.raw_json
        ''', (symbol, tf, direction, low, high, mid, status, created_at, last_touched_at, strength, source_time, raw_json))
        conn.commit()
        conn.close()

    def get_active_fvgs(self, symbol, tf=None):
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if tf:
            cursor.execute('''
                SELECT * FROM active_fvgs
                WHERE symbol = ? AND timeframe = ? AND status != 'INVALID'
            ''', (symbol, tf))
        else:
            cursor.execute('''
                SELECT * FROM active_fvgs
                WHERE symbol = ? AND status != 'INVALID'
            ''', (symbol,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_fvg_status(self, fvg_id, new_status, last_touched=None):
        if last_touched is None:
            last_touched = datetime.now(timezone.utc).isoformat()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE active_fvgs
            SET status = ?, last_touched_at = ?
            WHERE id = ?
        ''', (new_status, last_touched, fvg_id))
        conn.commit()
        conn.close()
