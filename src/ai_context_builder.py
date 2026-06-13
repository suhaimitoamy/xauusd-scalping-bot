"""Build compact AI context from DB/brain output. Never send raw 200 candles by default."""
from __future__ import annotations

import json
from typing import Any, Dict
from src.market_memory import MarketMemory


def build_compact_ai_context(storage, symbol: str, current_price: float = 0, signal: Dict[str, Any] | None = None) -> str:
    memory = MarketMemory(storage)
    events = memory.recent_events(symbol, 12)
    patterns = memory.recent_patterns(8)
    active = memory.active_signal()

    data = {
        'symbol': symbol,
        'price': current_price,
        'active_signal': {
            'id': active.get('id'), 'direction': active.get('direction'), 'status': active.get('status')
        } if active else None,
        'candidate_signal': {
            'direction': signal.get('direction'),
            'entry': [signal.get('entry_low'), signal.get('entry_high')],
            'sl': signal.get('sl'),
            'tp1': signal.get('tp1'),
            'tp2': signal.get('tp2'),
            'confidence': signal.get('confidence'),
            'pattern_key': signal.get('pattern_key'),
            'reason': signal.get('reason'),
        } if signal else None,
        'recent_events': [
            {
                'type': e.get('event_type'),
                'direction': e.get('direction'),
                'level': e.get('level'),
                'price': e.get('price'),
                'time': e.get('created_at'),
            } for e in events
        ],
        'learned_patterns': [
            {
                'pattern': p.get('pattern_key'),
                'score': p.get('score'),
                'wins': p.get('wins'),
                'losses': p.get('losses'),
                'last_result': p.get('last_result'),
                'notes': p.get('notes'),
            } for p in patterns
        ]
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
