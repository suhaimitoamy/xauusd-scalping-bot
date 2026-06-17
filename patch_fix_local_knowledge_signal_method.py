#!/usr/bin/env python3
from pathlib import Path

ROOT = Path.cwd()
path = ROOT / "src" / "local_knowledge_agent.py"

if not path.exists():
    raise SystemExit("src/local_knowledge_agent.py tidak ditemukan")

txt = path.read_text(encoding="utf-8")

block = '''

# ═══════════════════════════════════════════════════════════════════════════════
# PATCH: SIGNAL EDUCATION METHODS
# Dipasang sebagai monkey patch agar tidak merusak struktur class lama.
# ═══════════════════════════════════════════════════════════════════════════════

def _lk_is_signal_education_question(text):
    norm = normalize_text(text)
    if not norm:
        return False

    concept_prefixes = (
        'apa itu', 'itu apa', 'pengertian', 'definisi', 'maksud ob',
        'maksud fvg', 'maksud bos', 'maksud choch', 'maksud mss',
    )
    if any(norm.startswith(p) for p in concept_prefixes):
        return False

    exact_followup = {
        'kenapa', 'why', 'alasan', 'alasannya', 'detail', 'detailnya',
        'jelaskan', 'jelasin', 'gimana', 'bagaimana',
    }
    if norm in exact_followup:
        return True

    signal_phrases = (
        'buy atau sell', 'sell atau buy', 'buy apa sell',
        'enaknya buy', 'enaknya sell', 'enaknya sell atau buy',
        'enaknya buy atau sell', 'mending buy', 'mending sell',
        'rekomendasi buy', 'rekomendasi sell',
        'arah signal', 'arah sinyal', 'signal aktif', 'sinyal aktif',
        'setup aktif', 'setup sekarang', 'kenapa buy', 'kenapa sell',
        'kenapa signal', 'kenapa sinyal', 'kenapa setup',
        'alasan buy', 'alasan sell', 'alasan signal', 'alasan sinyal',
    )
    return any(p in norm for p in signal_phrases)


def _lk_signal_fmt(value, nd=3):
    try:
        if value is None or value == '':
            return "N/A"
        return f"{float(value):.{nd}f}"
    except Exception:
        return str(value)


def _lk_parse_signal_raw(signal):
    raw = signal.get('raw_context_json') or signal.get('raw_json') or '{}'
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _lk_active_or_latest_signal(self):
    try:
        from src.market_memory import MarketMemory
        memory = MarketMemory(self.storage)
        active = memory.active_signal()
        if active and active.get('direction') in ('BUY', 'SELL'):
            return active
    except Exception:
        pass

    try:
        rows = self.storage.fetchall(
            "SELECT * FROM signals WHERE direction IN ('BUY','SELL') ORDER BY id DESC LIMIT 1"
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _lk_latest_price_local(self, symbol='XAU/USD'):
    if getattr(self, '_bot_state', None):
        price = self._bot_state.get('last_price')
        if price:
            return price
    try:
        rows = self.storage.fetchall(
            "SELECT price FROM ticks WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,),
        )
        if rows:
            return rows[0].get('price')
    except Exception:
        pass
    try:
        rows = self.storage.fetchall(
            "SELECT close FROM candles WHERE symbol=? AND is_closed=1 ORDER BY open_time DESC LIMIT 1",
            (symbol,),
        )
        if rows:
            return rows[0].get('close')
    except Exception:
        pass
    return None


def _lk_latest_zone_local(self, table, symbol='XAU/USD'):
    try:
        rows = self.storage.fetchall(
            f"SELECT * FROM {table} WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,),
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _lk_format_signal_education(self, signal, source="BOT DATA ONLY"):
    raw = _lk_parse_signal_raw(signal)
    ctx = raw.get('brain_context') or raw.get('context') or raw.get('ctx') or {}

    symbol = signal.get('symbol') or raw.get('symbol') or 'XAU/USD'
    direction = signal.get('direction') or raw.get('direction') or 'N/A'
    entry_low = signal.get('entry_low') or raw.get('entry_low')
    entry_high = signal.get('entry_high') or raw.get('entry_high')
    sl = signal.get('sl') or raw.get('sl')
    tp1 = signal.get('tp1') or raw.get('tp1')
    tp2 = signal.get('tp2') or raw.get('tp2')
    invalid = signal.get('invalid_level') or raw.get('invalid_level') or sl

    pattern = (
        raw.get('pattern_key')
        or signal.get('pattern_key')
        or ctx.get('pattern_key')
        or raw.get('method')
        or "N/A"
    )
    reason = (
        signal.get('reason')
        or raw.get('reason')
        or ctx.get('reason')
        or "Signal dibuat berdasarkan rule bot lokal."
    )

    m15_bias = ctx.get('m15_bias') or ctx.get('bias_m15') or "N/A"
    h1_bias = ctx.get('h1_bias') or ctx.get('bias_h1') or "N/A"
    momentum = ctx.get('momentum') or ctx.get('m5_momentum') or "N/A"
    atr = ctx.get('atr') or raw.get('atr')
    choppy = ctx.get('choppy') if ctx.get('choppy') is not None else "N/A"
    signal_tf = signal.get('signal_timeframe') or raw.get('signal_timeframe') or "N/A"
    signal_class = signal.get('signal_class') or raw.get('signal_class') or "N/A"
    price = _lk_latest_price_local(self, symbol)

    supply = _lk_latest_zone_local(self, 'supply_demand_zones', symbol)
    ob = _lk_latest_zone_local(self, 'active_order_blocks', symbol)
    fvg = _lk_latest_zone_local(self, 'active_fvgs', symbol)

    lines = [
        "🤖 Dijawab oleh Bot Lokal",
        f"Source: {source}",
        "",
        "📘 EDUKASI SIGNAL",
        "",
        f"Rekomendasi: {direction}",
        f"Current Price: {_lk_signal_fmt(price)}",
        f"Entry: {_lk_signal_fmt(entry_low)} - {_lk_signal_fmt(entry_high)}",
        f"SL: {_lk_signal_fmt(sl)}",
        f"TP1: {_lk_signal_fmt(tp1)}",
        f"TP2: {_lk_signal_fmt(tp2)}",
        f"Invalidasi: {_lk_signal_fmt(invalid)}",
        f"Pattern: {pattern}",
        f"Timeframe: {signal_tf}",
        f"Class: {signal_class}",
        "",
        "Alasan:",
        f"1. {reason}",
        f"2. Bias M15: {m15_bias} | Bias H1: {h1_bias}",
        f"3. Momentum M5: {momentum} | ATR: {_lk_signal_fmt(atr)} | Choppy: {choppy}",
    ]

    if direction == 'SELL':
        lines.append("4. Setup SELL dianggap valid selama harga tidak close kuat di atas SL / invalidasi.")
        lines.append("5. TP diarahkan ke area bawah sesuai target bot.")
    elif direction == 'BUY':
        lines.append("4. Setup BUY dianggap valid selama harga tidak close kuat di bawah SL / invalidasi.")
        lines.append("5. TP diarahkan ke area atas sesuai target bot.")

    idx = 6
    if supply:
        ztype = supply.get('zone_type') or supply.get('type') or 'zone'
        lines.append(f"{idx}. Zone terakhir: {ztype} {_lk_signal_fmt(supply.get('low'))} - {_lk_signal_fmt(supply.get('high'))}")
        idx += 1

    if ob:
        ob_type = ob.get('type') or ob.get('direction') or 'OB'
        lines.append(f"{idx}. OB terakhir: {ob_type} {_lk_signal_fmt(ob.get('low'))} - {_lk_signal_fmt(ob.get('high'))}")
        idx += 1

    if fvg:
        fvg_type = fvg.get('direction') or 'FVG'
        lines.append(f"{idx}. FVG terakhir: {fvg_type} {_lk_signal_fmt(fvg.get('low'))} - {_lk_signal_fmt(fvg.get('high'))}")

    lines.extend([
        "",
        "Status:",
        f"{direction} masih valid selama harga tidak close kuat melewati invalidasi {_lk_signal_fmt(invalid)}.",
    ])

    return "\\n".join(lines)


def _lk_handle_signal_education_question(self, text):
    if not _lk_is_signal_education_question(text):
        return None

    signal = _lk_active_or_latest_signal(self)
    if not signal:
        return self._label_local(
            "Source: BOT DATA ONLY\\n\\n"
            "Belum ada signal BUY/SELL terakhir yang bisa dijelaskan."
        )

    return _lk_format_signal_education(self, signal, source="BOT DATA ONLY")


LocalKnowledgeAgent._handle_signal_education_question = _lk_handle_signal_education_question
LocalKnowledgeAgent._format_signal_education = _lk_format_signal_education
LocalKnowledgeAgent._active_or_latest_signal = _lk_active_or_latest_signal
LocalKnowledgeAgent._latest_price_local = _lk_latest_price_local
LocalKnowledgeAgent._latest_zone_local = _lk_latest_zone_local
LocalKnowledgeAgent._signal_fmt = staticmethod(_lk_signal_fmt)
LocalKnowledgeAgent._parse_signal_raw = staticmethod(_lk_parse_signal_raw)
'''

if "PATCH: SIGNAL EDUCATION METHODS" not in txt:
    txt = txt.rstrip() + "\n" + block + "\n"
    path.write_text(txt, encoding="utf-8")
    print("✅ Method signal education ditambahkan ke LocalKnowledgeAgent")
else:
    print("ℹ️ Patch method sudah ada")

print("✅ Fix selesai")
