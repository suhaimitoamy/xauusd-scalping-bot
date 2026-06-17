from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from src.ai_advisor import get_ai_response


def _fmt(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return "N/A"


def _c(c: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(c.get(key, default) or default)
    except Exception:
        return default


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


def _zone_from_candle(c: Dict[str, Any]) -> Dict[str, Any]:
    o = _c(c, 'open')
    cl = _c(c, 'close')
    hi = _c(c, 'high')
    lo = _c(c, 'low')
    return {
        'low': round(max(lo, min(o, cl) - 0.20), 3),
        'high': round(min(hi, max(o, cl) + 0.20), 3),
        'time': c.get('open_time') or c.get('time') or c.get('timestamp') or '-',
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
        return min(abs(price-low), abs(price-high))

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


def build_market_snapshot(storage, symbol: str, bot_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bot_state = bot_state or {}
    m5 = storage.get_recent_candles(symbol, 'M5', 80)
    m15 = storage.get_recent_candles(symbol, 'M15', 96)
    h1 = storage.get_recent_candles(symbol, 'H1', 72)
    h4 = storage.get_recent_candles(symbol, 'H4', 48)
    price = float(bot_state.get('last_price') or (m5[-1]['close'] if m5 else 0) or 0)

    base = m15 if len(m15) >= 20 else m5
    sd = _supply_demand_from_candles(base)
    db_sd = _db_supply_demand(storage, symbol, price) if price else {}
    sd.update({k: v for k, v in db_sd.items() if v})

    lv = _nearest_levels(base, price) if price else {}
    rng_high = lv.get('range_high')
    rng_low = lv.get('range_low')
    eq = ((rng_high + rng_low) / 2) if rng_high and rng_low else None
    if eq and price:
        if price > eq:
            price_position = 'premium'
        elif price < eq:
            price_position = 'discount'
        else:
            price_position = 'equilibrium'
    else:
        price_position = 'unknown'

    m15_bias = _bias(m15, 8)
    h1_bias = _bias(h1, 8)
    h4_bias = _bias(h4, 6)
    if m15_bias == h1_bias and m15_bias in ('bullish', 'bearish'):
        intraday_bias = m15_bias
    elif h1_bias in ('bullish', 'bearish'):
        intraday_bias = f"mixed_{h1_bias}_h1"
    else:
        intraday_bias = 'sideways'

    snapshot = {
        'symbol': symbol,
        'price': round(price, 3) if price else None,
        'updated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'bias': {
            'm15': m15_bias,
            'h1': h1_bias,
            'h4': h4_bias,
            'intraday': intraday_bias,
            'price_position': price_position,
        },
        'levels': {
            'range_high': round(rng_high, 3) if rng_high else None,
            'range_low': round(rng_low, 3) if rng_low else None,
            'equilibrium': round(eq, 3) if eq else None,
            'liquidity_above': round(lv.get('liquidity_above'), 3) if lv.get('liquidity_above') else None,
            'liquidity_below': round(lv.get('liquidity_below'), 3) if lv.get('liquidity_below') else None,
        },
        'supply_demand': sd,
    }
    payload = json.dumps({k: snapshot[k] for k in ('price', 'bias', 'levels', 'supply_demand')}, sort_keys=True, default=str)
    snapshot['signature'] = hashlib.sha1(payload.encode()).hexdigest()[:12]
    return snapshot


def format_market_context(storage, symbol: str, bot_state: Optional[Dict[str, Any]] = None) -> str:
    s = build_market_snapshot(storage, symbol, bot_state)
    sd = s.get('supply_demand', {})
    supply = sd.get('supply') or {}
    demand = sd.get('demand') or {}
    lv = s.get('levels', {})
    b = s.get('bias', {})
    return (
        "📊 XAUUSD MARKET CONTEXT\n"
        "Source: BOT DATA\n\n"
        f"Harga: {_fmt(s.get('price'))}\n"
        f"Bias intraday: {str(b.get('intraday')).upper()}\n"
        f"M15: {b.get('m15')} | H1: {b.get('h1')} | H4: {b.get('h4')}\n"
        f"Posisi harga: {b.get('price_position')}\n\n"
        f"Supply: {_fmt(supply.get('low'))} - {_fmt(supply.get('high'))}\n"
        f"Demand: {_fmt(demand.get('low'))} - {_fmt(demand.get('high'))}\n"
        f"EQ: {_fmt(lv.get('equilibrium'))}\n"
        f"Liquidity atas: {_fmt(lv.get('liquidity_above'))}\n"
        f"Liquidity bawah: {_fmt(lv.get('liquidity_below'))}\n\n"
        "Action: tunggu signal valid dari 9 method high-WR."
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
            "Jangan mengarang angka, gunakan data bot. Jawab dengan gaya natural, santai, dan seperti manusia sungguhan (pakai bahasa Indonesia gaul/casual yang sopan, seperti trader ke trader).\n"
            "Jangan buat jawaban yang kaku seperti robot. Hindari bullet points kaku jika bisa diceritakan mengalir.\n"
            "Kalau data belum cukup, katakan saja 'Datanya belum dapet nih bro'.\n\n"
            f"PERTANYAAN: {question}\n\n"
            f"DATA BOT:\n{json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)}"
        )
        messages = [
            {"role": "system", "content": "You are Telegram AI fallback for an XAUUSD bot. Use only provided bot data and exact levels."},
            {"role": "user", "content": prompt},
        ]
        ai_text, used_ai = get_ai_response(messages, fallback, max_tokens=800, timeout=20)
        source = "AI + BOT DATA" if used_ai else "BOT DATA"
        answer = f"🧠 Dijawab oleh AI berdasarkan data bot\nSource: {source}\n\n{ai_text.strip()}"
        cache[key] = {
            'question': question,
            'answer': answer,
            'snapshot_signature': snapshot.get('signature'),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'snapshot': snapshot,
        }
        # keep cache small
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
        q = question.lower()
        if any(x in q for x in ('supply', 'demand', 'sd', 'zona')):
            return (
                f"Supply terdekat: {_fmt(supply.get('low'))} - {_fmt(supply.get('high'))}.\n"
                f"Demand terdekat: {_fmt(demand.get('low'))} - {_fmt(demand.get('high'))}.\n"
                f"Harga sekarang: {_fmt(snapshot.get('price'))}."
            )
        if any(x in q for x in ('bias', 'arah', 'intraday', 'trend')):
            return (
                f"Bias intraday: {str(b.get('intraday')).upper()}.\n"
                f"M15: {b.get('m15')} | H1: {b.get('h1')} | H4: {b.get('h4')}.\n"
                f"Harga berada di area {b.get('price_position')} terhadap EQ {_fmt(lv.get('equilibrium'))}."
            )
        return (
            f"Harga: {_fmt(snapshot.get('price'))}.\n"
            f"Bias intraday: {str(b.get('intraday')).upper()}.\n"
            f"Supply: {_fmt(supply.get('low'))} - {_fmt(supply.get('high'))}.\n"
            f"Demand: {_fmt(demand.get('low'))} - {_fmt(demand.get('high'))}.\n"
            f"Liquidity atas: {_fmt(lv.get('liquidity_above'))}; liquidity bawah: {_fmt(lv.get('liquidity_below'))}."
        )
