import sqlite3
from datetime import datetime, timezone, timedelta


class PerformanceAnalyzer:
    def __init__(self, storage):
        self.storage = storage

    def get_weekly_stats(self):
        conn = self.storage.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        cursor.execute('''
            SELECT * FROM signals
            WHERE created_at >= ? AND status != 'NO_TRADE'
        ''', (week_ago,))

        signals = [dict(r) for r in cursor.fetchall()]

        # Count TP hits from signal_events table (accurate source)
        signal_ids = [s['id'] for s in signals if s.get('id')]
        tp_hit_map = {}  # signal_id -> set of events
        if signal_ids:
            placeholders = ','.join(['?'] * len(signal_ids))
            cursor.execute(f'''
                SELECT signal_id, event_type FROM signal_events
                WHERE signal_id IN ({placeholders})
                  AND event_type IN ('TP1_HIT', 'TP2_HIT', 'TP3_HIT')
            ''', signal_ids)
            for row in cursor.fetchall():
                sid = row['signal_id']
                if sid not in tp_hit_map:
                    tp_hit_map[sid] = set()
                tp_hit_map[sid].add(row['event_type'])

        conn.close()

        stats = {
            'total': len(signals),
            'wins': 0,
            'full_wins': 0,
            'partial_wins': 0,
            'losses': 0,
            'expired': 0,
            'tp1_hits': 0,
            'tp2_hits': 0,
            'tp3_hits': 0,
            'sl_hits': 0,
            'winrate': 0.0,
            'best_session': 'Unknown',
            'worst_session': 'Unknown',
            'best_setup': 'Unknown',
            'weak_setup': 'Unknown',
            'confidence_bins': {'65-69': {'w': 0, 'l': 0}, '70-79': {'w': 0, 'l': 0}, '80+': {'w': 0, 'l': 0}},
            'direction_stats': {'BUY': {'w': 0, 'l': 0}, 'SELL': {'w': 0, 'l': 0}}
        }

        if not signals:
            return stats

        for s in signals:
            res = s.get('result')
            status = s.get('status')
            conf = s.get('confidence') or 0
            dir = s.get('direction')
            sid = s.get('id')

            if res == 'FULL_WIN':
                stats['full_wins'] += 1
            elif res == 'WIN':
                stats['wins'] += 1
            elif res == 'PARTIAL_WIN':
                stats['partial_wins'] += 1
            elif res == 'LOSS':
                stats['losses'] += 1

            if status == 'EXPIRED':
                stats['expired'] += 1
            if status == 'CLOSED_LOSS':
                stats['sl_hits'] += 1

            # Count TP hits from signal_events (accurate)
            events = tp_hit_map.get(sid, set())
            if 'TP1_HIT' in events:
                stats['tp1_hits'] += 1
            if 'TP2_HIT' in events:
                stats['tp2_hits'] += 1
            if 'TP3_HIT' in events:
                stats['tp3_hits'] += 1

            # Confidence bins
            bin_key = '65-69' if conf < 70 else (
                '70-79' if conf < 80 else '80+')
            if res in ('WIN', 'FULL_WIN', 'PARTIAL_WIN'):
                stats['confidence_bins'][bin_key]['w'] += 1
                if dir in stats['direction_stats']:
                    stats['direction_stats'][dir]['w'] += 1
            elif res == 'LOSS':
                stats['confidence_bins'][bin_key]['l'] += 1
                if dir in stats['direction_stats']:
                    stats['direction_stats'][dir]['l'] += 1

        resolved = stats['wins'] + stats['full_wins'] + stats['partial_wins'] + stats['losses']
        if resolved > 0:
            stats['winrate'] = round(((stats['wins'] + stats['full_wins'] + stats['partial_wins']) / resolved) * 100, 2)

        return stats
