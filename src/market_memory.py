"""Local market memory for the adaptive XAUUSD brain.

DB = physical storage. MarketMemory = reader/writer for the bot's private memory.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MarketMemory:
    def __init__(self, storage):
        self.storage = storage
        self.ensure_schema()

    def ensure_schema(self) -> None:
        conn = self.storage.get_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS brain_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                symbol TEXT,
                timeframe TEXT,
                event_type TEXT,
                direction TEXT,
                level REAL,
                price REAL,
                weight REAL,
                source TEXT,
                raw_json TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_brain_events_created ON brain_events(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_brain_events_symbol ON brain_events(symbol, timeframe)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS brain_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                symbol TEXT,
                price REAL,
                decision TEXT,
                direction TEXT,
                confidence REAL,
                reason TEXT,
                pattern_key TEXT,
                raw_json TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS brain_patterns (
                pattern_key TEXT PRIMARY KEY,
                direction TEXT,
                score REAL,
                wins INTEGER,
                losses INTEGER,
                partials INTEGER,
                last_result TEXT,
                cooldown_until TEXT,
                notes TEXT,
                updated_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS brain_training (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                signal_id INTEGER UNIQUE,
                result TEXT,
                pattern_key TEXT,
                penalty REAL,
                reward REAL,
                ai_used INTEGER,
                lesson TEXT,
                raw_json TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS brain_state (
                key TEXT PRIMARY KEY,
                value_json TEXT,
                updated_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS brain_code_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                version_name TEXT,
                file_path TEXT,
                status TEXT,
                reason TEXT,
                syntax_ok INTEGER,
                raw_json TEXT
            )
        """)

        cur.execute("PRAGMA table_info(brain_decisions)")
        cols = [info[1] for info in cur.fetchall()]
        if 'evaluated' not in cols:
            cur.execute("ALTER TABLE brain_decisions ADD COLUMN evaluated INTEGER DEFAULT 0")

        conn.commit()
        conn.close()

    def record_event(self, symbol: str, timeframe: str, event_type: str,
                     direction: str = "", level: Optional[float] = None,
                     price: Optional[float] = None, weight: float = 1.0,
                     source: str = "ADAPTIVE_BRAIN", raw: Optional[Dict[str, Any]] = None,
                     dedupe_window_minutes: int = 20) -> bool:
        raw = raw or {}
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id FROM brain_events
                WHERE symbol=? AND timeframe=? AND event_type=? AND direction=?
                  AND ABS(COALESCE(level,0) - COALESCE(?,0)) < 0.0001
                ORDER BY id DESC LIMIT 1
                """,
                (symbol, timeframe, event_type, direction, level)
            )
            row = cur.fetchone()
            if row:
                cur.execute("SELECT created_at FROM brain_events WHERE id=?", (row["id"],))
                r2 = cur.fetchone()
                if r2:
                    try:
                        last_dt = datetime.fromisoformat(r2["created_at"])
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - last_dt < timedelta(minutes=dedupe_window_minutes):
                            return False
                    except Exception as e:
                        import logging
                        logging.getLogger("MarketMemory").warning(f"Error parsing date {r2.get('created_at', '')}: {e}")

            cur.execute(
                """
                INSERT INTO brain_events
                (created_at, symbol, timeframe, event_type, direction, level, price, weight, source, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (utc_now(), symbol, timeframe, event_type, direction, level, price, weight, source, json.dumps(self._compact_raw(raw), ensure_ascii=False))
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def _compact_raw(self, raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        keep = {}
        for key in (
            'price', 'prev_high', 'prev_low', 'last_open', 'last_high', 'last_low',
            'last_close', 'atr', 'body_ratio', 'momentum', 'break_bull',
            'break_bear', 'sentuh_high', 'sentuh_low', 'choppy', 'm15_bias', 'h1_bias'
        ):
            if key in raw:
                keep[key] = raw.get(key)
        return keep

    def _compact_decision(self, signal: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(signal, dict):
            return {}
        keys = (
            'symbol', 'direction', 'entry_low', 'entry_high', 'sl', 'tp1', 'tp2',
            'tp3', 'invalid_level', 'confidence', 'reason', 'status',
            'entry_type', 'pending_price', 'signal_timeframe', 'signal_class',
            'current_price', 'pattern_key', 'source'
        )
        data = {k: signal.get(k) for k in keys if k in signal}
        ctx = signal.get('brain_context')
        if isinstance(ctx, dict):
            data['brain_context'] = self._compact_raw(ctx)
        return data

    def recent_events(self, symbol: Optional[str] = None, limit: int = 30,
                      current_price: Optional[float] = None,
                      max_age_minutes: Optional[int] = None,
                      max_distance_points: Optional[float] = None) -> List[Dict[str, Any]]:
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        where = []
        params = []
        if symbol:
            where.append("symbol=?")
            params.append(symbol)
        if max_age_minutes:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat()
            where.append("created_at>=?")
            params.append(cutoff)
        sql = "SELECT id, created_at, symbol, timeframe, event_type, direction, level, price, weight, source FROM brain_events"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(max(limit * 4, limit))
        cur.execute(sql, tuple(params))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        if current_price is not None and max_distance_points is not None:
            filtered = []
            try:
                cp = float(current_price)
                md = float(max_distance_points)
                for row in rows:
                    level = row.get('level')
                    ev_price = row.get('price')

                    # For SENTUH/BREAK events the actionable reference is the
                    # level itself. Do not keep a stale old level only because
                    # the event was recorded near the current price.
                    reference = level if level is not None else ev_price
                    if reference is None:
                        filtered.append(row)
                        continue
                    try:
                        if abs(float(reference) - cp) <= md:
                            filtered.append(row)
                    except Exception:
                        filtered.append(row)
                rows = filtered
            except Exception:
                pass
        return rows[:limit]

    def save_decision(self, signal: Dict[str, Any]) -> None:
        conn = self.storage.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO brain_decisions
            (created_at, symbol, price, decision, direction, confidence, reason, pattern_key, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now(), signal.get('symbol', 'XAU/USD'), signal.get('current_price'),
                signal.get('status', 'NO_TRADE'), signal.get('direction', 'NO_TRADE'),
                signal.get('confidence', 0), signal.get('reason', ''),
                signal.get('pattern_key', ''), json.dumps(self._compact_decision(signal), ensure_ascii=False)
            )
        )
        conn.commit()
        conn.close()

    def get_pattern(self, pattern_key: str) -> Dict[str, Any]:
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM brain_patterns WHERE pattern_key=?", (pattern_key,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {
                'pattern_key': pattern_key, 'score': 0, 'wins': 0,
                'losses': 0, 'partials': 0, 'cooldown_until': None, 'notes': ''
            }
        return dict(row)

    def update_pattern_result(self, pattern_key: str, direction: str, result: str,
                              lesson: str = "", penalty: float = 0.0,
                              reward: float = 0.0, cooldown_minutes: int = 0,
                              prev_result: str = None) -> Dict[str, Any]:
        current = self.get_pattern(pattern_key)
        score = float(current.get('score') or 0) + float(reward or 0) - float(penalty or 0)
        wins = int(current.get('wins') or 0)
        losses = int(current.get('losses') or 0)
        partials = int(current.get('partials') or 0)

        # Remove previous result count
        if prev_result:
            if prev_result in ('WIN', 'FULL_WIN', 'PARTIAL_WIN'):
                wins = max(0, wins - 1)
                if prev_result == 'PARTIAL_WIN':
                    partials = max(0, partials - 1)
            elif prev_result == 'LOSS':
                losses = max(0, losses - 1)
            else:
                partials = max(0, partials - 1)

        # Add new result count. PARTIAL_WIN is counted as a win because TP1
        # is protected and should be treated as a successful outcome.
        if result in ('WIN', 'FULL_WIN', 'PARTIAL_WIN'):
            wins += 1
            if result == 'PARTIAL_WIN':
                partials += 1
        elif result == 'LOSS':
            losses += 1
        else:
            partials += 1
        cooldown_until = None
        if cooldown_minutes:
            cooldown_until = (datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)).isoformat()

        conn = self.storage.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO brain_patterns
            (pattern_key, direction, score, wins, losses, partials, last_result, cooldown_until, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pattern_key) DO UPDATE SET
                direction=excluded.direction,
                score=excluded.score,
                wins=excluded.wins,
                losses=excluded.losses,
                partials=excluded.partials,
                last_result=excluded.last_result,
                cooldown_until=excluded.cooldown_until,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (pattern_key, direction, score, wins, losses, partials, result, cooldown_until, lesson, utc_now())
        )
        conn.commit()
        conn.close()
        return self.get_pattern(pattern_key)

    def is_pattern_in_cooldown(self, pattern_key: str) -> bool:
        pattern = self.get_pattern(pattern_key)
        cd = pattern.get('cooldown_until')
        if not cd:
            return False
        try:
            return datetime.now(timezone.utc) < datetime.fromisoformat(cd)
        except Exception:
            return False

    def save_training(self, signal_id: int, result: str, pattern_key: str,
                      lesson: str, penalty: float, reward: float,
                      ai_used: bool, raw: Dict[str, Any]) -> None:
        conn = self.storage.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO brain_training
            (created_at, signal_id, result, pattern_key, penalty, reward, ai_used, lesson, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_id) DO UPDATE SET
                result=excluded.result,
                lesson=excluded.lesson,
                penalty=excluded.penalty,
                reward=excluded.reward,
                created_at=excluded.created_at
            """,
            (utc_now(), signal_id, result, pattern_key, penalty, reward, 1 if ai_used else 0, lesson, json.dumps(raw, ensure_ascii=False))
        )
        conn.commit()
        conn.close()

    def get_training(self, signal_id: int) -> Optional[Dict[str, Any]]:
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM brain_training WHERE signal_id=?", (signal_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def signal_already_trained(self, signal_id: int) -> bool:
        conn = self.storage.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM brain_training WHERE signal_id=?", (signal_id,))
        row = cur.fetchone()
        conn.close()
        return bool(row)

    def recent_patterns(self, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM brain_patterns ORDER BY updated_at DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def active_signal(self, signal_timeframe: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            rows = self.storage.get_open_signals(signal_timeframe=signal_timeframe)
        except TypeError:
            rows = self.storage.get_open_signals()
            if signal_timeframe:
                rows = [r for r in rows if str(r.get('signal_timeframe') or 'M5').upper() == str(signal_timeframe).upper()]
        return rows[0] if rows else None

    def set_state(self, key: str, value: Any) -> None:
        conn = self.storage.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO brain_state (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
            """,
            (key, json.dumps(value, ensure_ascii=False), utc_now())
        )
        conn.commit()
        conn.close()

    def get_state(self, key: str, default: Any = None) -> Any:
        conn = self.storage.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT value_json FROM brain_state WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except Exception:
            return default

    def get_unevaluated_no_trades(self, minutes_ago: int = 30) -> List[Dict[str, Any]]:
        """Get NO_TRADE decisions older than minutes_ago that haven't been evaluated."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM brain_decisions
            WHERE decision = 'NO_TRADE' AND created_at <= ? AND COALESCE(evaluated, 0) = 0
            ORDER BY id DESC LIMIT 10
            """,
            (cutoff,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def mark_no_trade_evaluated(self, decision_id: int) -> None:
        """Mark a NO_TRADE decision as evaluated."""
        conn = self.storage.get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE brain_decisions SET evaluated = 1 WHERE id = ?", (decision_id,))
        conn.commit()
        conn.close()
