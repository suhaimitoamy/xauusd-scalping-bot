from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.ai_advisor import get_ai_response
from src.candle_sync import build_freshness_bundle, get_recent_valid_candles


def _fmt(v, digits: int = 2):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return "N/A"


def _c(candle: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(candle.get(key, default) or default)
    except Exception:
        return default


def _ctime(candle: Dict[str, Any]) -> str:
    return str(
        candle.get('open_time')
        or candle.get('time')
        or candle.get('timestamp')
        or candle.get('close_time')
        or '-'
    )


def _bias(candles: List[Dict[str, Any]], lookback: int = 8) -> str:
    if not candles or len(candles) < max(5, lookback):
        return "unknown"
    part = candles[-lookback:]
    first = _c(part[0], 'close')
    last = _c(part[-1], 'close')
    high = max(_c(x, 'high') for x in part)
    low = min(_c(x, 'low') for x in part)
    eq = (high + low) / 2
    if last > first and last > eq:
        return "bullish"
    if last < first and last < eq:
        return "bearish"
    return "sideways"


def _zone_from_candle(candle: Dict[str, Any]) -> Dict[str, Any]:
    o = _c(candle, 'open')
    cl = _c(candle, 'close')
    hi = _c(candle, 'high')
    lo = _c(candle, 'low')
    return {
        'low': round(max(lo, min(o, cl) - 0.20), 3),
        'high': round(min(hi, max(o, cl) + 0.20), 3),
        'time': _ctime(candle),
    }


def _nearest_levels(candles: List[Dict[str, Any]], price: float) -> Dict[str, Any]:
    if not candles:
        return {}
    recent = candles[-40:] if len(candles) >= 40 else candles
    highs = sorted({_c(c, 'high') for c in recent})
    lows = sorted({_c(c, 'low') for c in recent})
    above = [h for h in highs if h > price]
    below = [l for l in lows if l < price]
    return {
        'liquidity_above': min(above, key=lambda x: abs(x - price)) if above else None,
        'liquidity_below': max(below, key=lambda x: x) if below else None,
        'range_high': max(highs) if highs else None,
        'range_low': min(lows) if lows else None,
    }


def _supply_demand_from_candles(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not candles:
        return {'supply': None, 'demand': None}
    recent = candles[-48:] if len(candles) >= 48 else candles
    supply_candle = max(recent, key=lambda x: _c(x, 'high'))
    demand_candle = min(recent, key=lambda x: _c(x, 'low'))
    return {
        'supply': _zone_from_candle(supply_candle),
        'demand': _zone_from_candle(demand_candle),
    }


def _db_supply_demand(storage, symbol: str, price: float) -> Dict[str, Any]:
    try:
        rows = storage.fetchall(
            """
            SELECT * FROM supply_demand_zones
            WHERE (symbol=? OR symbol IS NULL)
              AND status IN ('VALID','TOUCHED','ACTIVE')
            ORDER BY created_at DESC LIMIT 50
            """,
            (symbol,)
        )
    except Exception:
        rows = []
    if not rows:
        return {}

    def dist(row):
        try:
            low = float(row.get('low'))
            high = float(row.get('high'))
        except Exception:
            return 10**9
        if low <= price <= high:
            return 0
        return min(abs(price - low), abs(price - high))

    supply_rows = [r for r in rows if 'supply' in str(r.get('zone_type') or '').lower()]
    demand_rows = [r for r in rows if 'demand' in str(r.get('zone_type') or '').lower()]
    out = {}
    if supply_rows:
        r = sorted(supply_rows, key=dist)[0]
        out['supply'] = {'low': r.get('low'), 'high': r.get('high'), 'time': r.get('created_at')}
    if demand_rows:
        r = sorted(demand_rows, key=dist)[0]
        out['demand'] = {'low': r.get('low'), 'high': r.get('high'), 'time': r.get('created_at')}
    return out


def _candle_line(c: Dict[str, Any]) -> str:
    tf = c.get('timeframe') or '-'
    if not c.get('available'):
        return f"{tf}: data belum ada | status STALE"
    age = c.get('age_minutes')
    age_text = f"{age}m" if age is not None else "N/A"
    return (
        f"{tf}: last UTC {c.get('time_utc')} | close {c.get('close_time_utc')} | "
        f"age {age_text} | {c.get('status')} | "
        f"O {_fmt(c.get('open'))} H {_fmt(c.get('high'))} "
        f"L {_fmt(c.get('low'))} C {_fmt(c.get('close'))}"
    )


def _fresh_line(tf: str, c: Dict[str, Any]) -> str:
    if not c.get('available'):
        return f"{tf}: STALE | no valid closed candle"
    age = c.get('age_minutes')
    age_text = f"{age}m" if age is not None else "N/A"
    return f"{tf}: {c.get('status')} | last {c.get('time_utc')} | age {age_text} | {c.get('reason')}"


def _structure_snapshot(m5, m15, h1) -> Dict[str, Any]:
    try:
        from src.market_structure import analyze_structure
        if m5 and m15 and h1:
            return analyze_structure(m5, m15, h1) or {}
    except Exception:
        pass
    return {}


def _decision_from_snapshot(snapshot: Dict[str, Any]) -> Dict[str, str]:
    freshness = snapshot.get('freshness') or {}
    data_status = str(freshness.get('data_status') or 'DATA STALE')
    if data_status != 'FRESH':
        return {
            'status': 'DATA STALE',
            'bias': 'WAIT',
            'reason': 'M5/M15/H1/H4 belum fresh atau HTF terdeteksi tidak sinkron.',
            'action': 'DATA STALE / WAIT'
        }

    b = snapshot.get('bias', {})
    struct = snapshot.get('structure', {}) or {}
    m15 = str(b.get('m15') or 'unknown')
    h1 = str(b.get('h1') or 'unknown')
    h4 = str(b.get('h4') or 'unknown')
    phase = str(struct.get('trend') or 'UNKNOWN')
    break_type = str(struct.get('break_type') or '')
    sweep_type = str(struct.get('sweep_type') or '')
    reclaim_valid = bool(struct.get('reclaim_valid'))

    bulls = [x for x in (m15, h1, h4) if x == 'bullish']
    bears = [x for x in (m15, h1, h4) if x == 'bearish']

    if phase == 'CHOPPY':
        return {
            'status': 'WAIT',
            'bias': 'CHOPPY',
            'reason': 'Market choppy; raw signal lebih mudah fakeout.',
            'action': 'Tunggu struktur lebih bersih atau candle displacement.'
        }

    if len(bulls) >= 2 and m15 != 'bearish':
        if sweep_type == 'bullish' and reclaim_valid:
            action = 'WAIT BUY — sweep low + reclaim valid, tunggu area entry dari signal.'
        elif 'BULLISH' in break_type:
            action = 'BUY ONLY — struktur bullish, tunggu retest/pullback.'
        else:
            action = 'WAIT BUY — HTF condong bullish, jangan sell dulu kecuali struktur rusak.'
        return {'status': 'WAIT BUY', 'bias': 'BULLISH', 'reason': f'M15/H1/H4: {m15}/{h1}/{h4}.', 'action': action}

    if len(bears) >= 2 and m15 != 'bullish':
        if sweep_type == 'bearish' and reclaim_valid:
            action = 'WAIT SELL — sweep high + reclaim valid, tunggu area entry dari signal.'
        elif 'BEARISH' in break_type:
            action = 'SELL ONLY — struktur bearish, tunggu retest/pullback.'
        else:
            action = 'WAIT SELL — HTF condong bearish, jangan buy dulu kecuali struktur rusak.'
        return {'status': 'WAIT SELL', 'bias': 'BEARISH', 'reason': f'M15/H1/H4: {m15}/{h1}/{h4}.', 'action': action}

    return {
        'status': 'CONFLICT / WAIT',
        'bias': 'MIXED',
        'reason': f'M15/H1/H4 belum searah: {m15}/{h1}/{h4}.',
        'action': 'Tunggu salah satu: H1 searah M15, sweep reclaim valid, atau BOS/CHOCH yang clean.'
    }


def build_market_snapshot(storage, symbol: str, bot_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bot_state = bot_state or {}
    m5 = get_recent_valid_candles(storage, symbol, 'M5', 80)
    m15 = get_recent_valid_candles(storage, symbol, 'M15', 96)
    h1 = get_recent_valid_candles(storage, symbol, 'H1', 72)
    h4 = get_recent_valid_candles(storage, symbol, 'H4', 48)
    d1 = get_recent_valid_candles(storage, symbol, 'D1', 30)

    freshness = build_freshness_bundle(storage, symbol, bot_state)
    live_price = freshness.get('live_price')
    price = float(live_price or (m5[-1]['close'] if m5 else 0) or 0)

    base = m15 if len(m15) >= 20 else m5
    sd = _supply_demand_from_candles(base)
    db_sd = _db_supply_demand(storage, symbol, price) if price else {}
    sd.update({k: v for k, v in db_sd.items() if v})

    levels = _nearest_levels(base, price) if price else {}
    rng_high = levels.get('range_high')
    rng_low = levels.get('range_low')
    eq = ((rng_high + rng_low) / 2) if rng_high and rng_low else None
    if eq and price:
        price_position = 'premium' if price > eq else 'discount' if price < eq else 'equilibrium'
    else:
        price_position = 'unknown'

    m15_bias = _bias(m15, 8)
    h1_bias = _bias(h1, 8)
    h4_bias = _bias(h4, 6)
    d1_bias = _bias(d1, 5)
    if m15_bias == h1_bias and m15_bias in ('bullish', 'bearish'):
        intraday_bias = m15_bias
    elif h1_bias in ('bullish', 'bearish'):
        intraday_bias = f"mixed_{h1_bias}_h1"
    else:
        intraday_bias = 'sideways'

    structure = _structure_snapshot(m5, m15, h1)

    snapshot = {
        'symbol': symbol,
        'price': round(price, 3) if price else None,
        'live_price': round(float(live_price), 3) if live_price else None,
        'updated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'freshness': freshness,
        'data_status': freshness.get('data_status'),
        'bias': {
            'm15': m15_bias,
            'h1': h1_bias,
            'h4': h4_bias,
            'd1': d1_bias,
            'intraday': intraday_bias,
            'price_position': price_position,
        },
        'levels': {
            'range_high': round(rng_high, 3) if rng_high else None,
            'range_low': round(rng_low, 3) if rng_low else None,
            'equilibrium': round(eq, 3) if eq else None,
            'liquidity_above': round(levels.get('liquidity_above'), 3) if levels.get('liquidity_above') else None,
            'liquidity_below': round(levels.get('liquidity_below'), 3) if levels.get('liquidity_below') else None,
        },
        'supply_demand': sd,
        'structure': structure,
        'last_candles': freshness.get('candles') or {},
    }
    snapshot['decision'] = _decision_from_snapshot(snapshot)
    payload = json.dumps({k: snapshot[k] for k in ('price', 'bias', 'levels', 'supply_demand', 'structure', 'freshness')}, sort_keys=True, default=str)
    snapshot['signature'] = hashlib.sha1(payload.encode()).hexdigest()[:12]
    return snapshot


def format_market_context(storage, symbol: str, bot_state: Optional[Dict[str, Any]] = None) -> str:
    s = build_market_snapshot(storage, symbol, bot_state)
    sd = s.get('supply_demand', {})
    supply = sd.get('supply') or {}
    demand = sd.get('demand') or {}
    levels = s.get('levels', {})
    bias = s.get('bias', {})
    struct = s.get('structure', {}) or {}
    dec = s.get('decision', {})
    candles = s.get('last_candles', {})
    freshness = s.get('freshness', {})

    return (
        "🧭 XAUUSD MARKET CONTEXT\n"
        "Source: BOT DATA / SQLite Candle\n\n"
        f"Live price: {_fmt(s.get('live_price') or s.get('price'))}\n"
        f"Live source: {freshness.get('price_source', 'Twelve Data WebSocket')}\n"
        f"Status data: {s.get('data_status')}\n"
        f"Market decision: {dec.get('action')}\n"
        f"Bias final: {dec.get('bias')}\n"
        f"Alasan: {dec.get('reason')}\n\n"
        "📊 BIAS DETAIL\n"
        f"M15: {bias.get('m15')} | H1: {bias.get('h1')} | H4: {bias.get('h4')} | D1: {bias.get('d1')}\n"
        f"Intraday: {bias.get('intraday')} | Posisi harga: {bias.get('price_position')}\n\n"
        "🏗 PHASE STRUCTURE\n"
        f"Phase: {struct.get('trend', 'N/A')} | Break: {struct.get('break_type', 'N/A')} | Sweep: {struct.get('sweep_type', 'N/A')}\n\n"
        "📍 SUPPLY / DEMAND\n"
        f"Supply: {_fmt(supply.get('low'))} - {_fmt(supply.get('high'))}\n"
        f"Demand: {_fmt(demand.get('low'))} - {_fmt(demand.get('high'))}\n"
        f"EQ: {_fmt(levels.get('equilibrium'))}\n\n"
        "💧 LIQUIDITY\n"
        f"Liquidity atas: {_fmt(levels.get('liquidity_above'))}\n"
        f"Liquidity bawah: {_fmt(levels.get('liquidity_below'))}\n\n"
        "🕯 LAST CLOSED CANDLE OHLC\n"
        f"{_candle_line(candles.get('M5', {'timeframe': 'M5'}))}\n"
        f"{_candle_line(candles.get('M15', {'timeframe': 'M15'}))}\n"
        f"{_candle_line(candles.get('H1', {'timeframe': 'H1'}))}\n"
        f"{_candle_line(candles.get('H4', {'timeframe': 'H4'}))}\n\n"
        "🧪 FRESHNESS STATUS\n"
        f"{_fresh_line('M5', candles.get('M5', {}))}\n"
        f"{_fresh_line('M15', candles.get('M15', {}))}\n"
        f"{_fresh_line('H1', candles.get('H1', {}))}\n"
        f"{_fresh_line('H4', candles.get('H4', {}))}\n\n"
        "Catatan: bandingkan OHLC last closed candle di atas dengan TradingView pada waktu UTC yang sama."
    )


def format_supply_demand(storage, symbol: str, bot_state: Optional[Dict[str, Any]] = None) -> str:
    s = build_market_snapshot(storage, symbol, bot_state)
    sd = s.get('supply_demand', {})
    supply = sd.get('supply') or {}
    demand = sd.get('demand') or {}
    return (
        "📍 XAUUSD SUPPLY / DEMAND\n"
        "Source: BOT DATA\n\n"
        f"Harga: {_fmt(s.get('price'))}\n"
        f"Supply: {_fmt(supply.get('low'))} - {_fmt(supply.get('high'))}\n"
        f"Demand: {_fmt(demand.get('low'))} - {_fmt(demand.get('high'))}\n\n"
        "Action: area ini hanya area pantau, entry tetap tunggu konfirmasi bot."
    )


class TelegramMarketAI:
    def __init__(self, storage, symbol: str = 'XAU/USD', bot_state: Optional[Dict[str, Any]] = None, cache_path: str = 'data/telegram_ai_cache.json'):
        self.storage = storage
        self.symbol = symbol
        self.bot_state = bot_state or {}
        self.cache_path = cache_path
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    @staticmethod
    def _norm(text: str) -> str:
        text = (text or '').lower().strip()
        text = re.sub(r'[^a-z0-9\s_./-]+', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _load_cache(self) -> Dict[str, Any]:
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cache(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def answer(self, question: str, chat_id=None, user_id=None, username=None) -> Optional[str]:
        question = (question or '').strip()
        if not question:
            return None
        snapshot = build_market_snapshot(self.storage, self.symbol, self.bot_state)
        key = hashlib.sha1((self._norm(question) + '|' + snapshot.get('signature', '')).encode()).hexdigest()
        cache = self._load_cache()
        if key in cache:
            return cache[key].get('answer')

        fallback = self._local_grounded_answer(question, snapshot)
        prompt = (
            "Jawab pertanyaan user Telegram berdasarkan DATA BOT di bawah.\n"
            "Jangan mengarang angka, gunakan data bot. Jawab natural dan singkat.\n"
            "Kalau data belum cukup, katakan data belum cukup.\n\n"
            f"PERTANYAAN: {question}\n\n"
            f"DATA BOT:\n{json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)}"
        )
        messages = [
            {"role": "system", "content": "You are Telegram AI fallback for an XAUUSD bot. Use only provided bot data and exact levels."},
            {"role": "user", "content": prompt},
        ]
        ai_text, used_ai = get_ai_response(messages, fallback, max_tokens=800, timeout=20)
        source = "BOT DATA ONLY" if used_ai else "BOT DATA"
        answer = f"🤖 Dijawab oleh Bot Lokal\nSource: {source}\n\n{ai_text.strip()}"
        cache[key] = {
            'question': question,
            'answer': answer,
            'snapshot_signature': snapshot.get('signature'),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'snapshot': snapshot,
        }
        if len(cache) > 200:
            items = list(cache.items())[-200:]
            cache = dict(items)
        self._save_cache(cache)
        return answer

    def _local_grounded_answer(self, question: str, snapshot: Dict[str, Any]) -> str:
        b = snapshot.get('bias', {})
        lv = snapshot.get('levels', {})
        sd = snapshot.get('supply_demand', {})
        supply = sd.get('supply') or {}
        demand = sd.get('demand') or {}
        dec = snapshot.get('decision', {})
        q = question.lower()
        if any(x in q for x in ('supply', 'demand', 'sd', 'zona')):
            return (
                f"Supply terdekat: {_fmt(supply.get('low'))} - {_fmt(supply.get('high'))}.\n"
                f"Demand terdekat: {_fmt(demand.get('low'))} - {_fmt(demand.get('high'))}.\n"
                f"Harga sekarang: {_fmt(snapshot.get('price'))}."
            )
        if any(x in q for x in ('bias', 'arah', 'intraday', 'trend', 'buy', 'sell')):
            return (
                f"Status: {dec.get('status')}.\n"
                f"Bias final: {dec.get('bias')}.\n"
                f"M15: {b.get('m15')} | H1: {b.get('h1')} | H4: {b.get('h4')}.\n"
                f"Action: {dec.get('action')}"
            )
        return (
            f"Harga: {_fmt(snapshot.get('price'))}.\n"
            f"Status: {dec.get('status')}.\n"
            f"Bias intraday: {str(b.get('intraday')).upper()}.\n"
            f"Supply: {_fmt(supply.get('low'))} - {_fmt(supply.get('high'))}.\n"
            f"Demand: {_fmt(demand.get('low'))} - {_fmt(demand.get('high'))}.\n"
            f"Liquidity atas: {_fmt(lv.get('liquidity_above'))}; liquidity bawah: {_fmt(lv.get('liquidity_below'))}."
        )
