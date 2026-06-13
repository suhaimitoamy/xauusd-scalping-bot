from datetime import datetime, timezone, timedelta
import json


def _wib_now():
    return (datetime.now(timezone.utc) + timedelta(hours=7)).strftime('%H:%M WIB')


def _fmt(v, digits=2):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return "N/A"


def _rowdicts(rows):
    return [dict(r) for r in rows] if rows else []


def _fetch(storage, query, params=()):
    conn = storage.get_connection()
    conn.row_factory = __import__('sqlite3').Row
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        rows = cur.fetchall()
        return _rowdicts(rows)
    finally:
        conn.close()


def _nearest(rows, price, direction=None):
    if direction:
        dset = {direction, direction.upper(), direction.lower()}
        if direction.upper() == 'BUY':
            dset |= {'Bullish', 'BULLISH', 'bullish', 'Demand'}
        if direction.upper() == 'SELL':
            dset |= {'Bearish', 'BEARISH', 'bearish', 'Supply'}
        rows = [r for r in rows if str(r.get('direction') or r.get('type') or r.get('zone_type')).strip() in dset]
    if not rows:
        return None
    def dist(r):
        lows = [r.get('low'), r.get('level')]
        low = next((x for x in lows if x is not None), price)
        high = r.get('high', low)
        try:
            low = float(low); high = float(high)
        except Exception:
            return 10**9
        if low <= price <= high:
            return 0
        return min(abs(price-low), abs(price-high))
    return sorted(rows, key=dist)[0]


def build_context(storage, symbol, bot_state=None):
    from src.market_structure import analyze_structure
    from src.session_filter import evaluate_session
    price = (bot_state or {}).get('last_price') or 0
    m5 = storage.get_recent_candles(symbol, 'M5', 80)
    m15 = storage.get_recent_candles(symbol, 'M15', 80)
    h1 = storage.get_recent_candles(symbol, 'H1', 50)
    struct = analyze_structure(m5, m15, h1) if m5 and m15 and h1 else {}
    session = evaluate_session()
    fvgs = _fetch(storage, "SELECT * FROM active_fvgs WHERE symbol=? AND status IN ('UNFILLED','PARTIAL','PARTIALLY_FILLED','HIT') ORDER BY created_at DESC LIMIT 20", (symbol,))
    obs = _fetch(storage, "SELECT * FROM active_order_blocks WHERE (symbol=? OR symbol IS NULL) AND status='VALID' ORDER BY created_at DESC LIMIT 20", (symbol,))
    brks = _fetch(storage, "SELECT * FROM active_breakers WHERE (symbol=? OR symbol IS NULL) AND status='VALID' ORDER BY created_at DESC LIMIT 20", (symbol,))
    sd = _fetch(storage, "SELECT * FROM supply_demand_zones WHERE (symbol=? OR symbol IS NULL) AND status IN ('VALID','TOUCHED') ORDER BY created_at DESC LIMIT 20", (symbol,))
    liq = _fetch(storage, "SELECT * FROM liquidity_pools WHERE (symbol=? OR symbol IS NULL) AND status='ACTIVE' ORDER BY level DESC LIMIT 20", (symbol,))
    ote = _fetch(storage, "SELECT * FROM active_ote_zones WHERE (symbol=? OR symbol IS NULL) AND status IN ('ACTIVE','HIT') ORDER BY created_at DESC LIMIT 20", (symbol,))
    # components nearest current price
    nearest_fvg = _nearest(fvgs, price) if price else None
    nearest_ob = _nearest(obs, price) if price else None
    nearest_sd = _nearest(sd, price) if price else None
    nearest_ote = _nearest(ote, price) if price else None
    above = [p for p in liq if p.get('level') is not None and float(p['level']) > float(price or 0)]
    below = [p for p in liq if p.get('level') is not None and float(p['level']) < float(price or 0)]
    liq_above = min(above, key=lambda x: abs(float(x['level'])-float(price))) if above and price else None
    liq_below = max(below, key=lambda x: float(x['level'])) if below and price else None
    return {
        'symbol': symbol,
        'price': price,
        'time': _wib_now(),
        'm5': m5,
        'm15': m15,
        'h1': h1,
        'structure': struct,
        'session': session.get('session_name', 'N/A'),
        'fvgs': fvgs,
        'obs': obs,
        'breakers': brks,
        'sd': sd,
        'liquidity': liq,
        'ote': ote,
        'nearest_fvg': nearest_fvg,
        'nearest_ob': nearest_ob,
        'nearest_sd': nearest_sd,
        'nearest_ote': nearest_ote,
        'liq_above': liq_above,
        'liq_below': liq_below,
    }


def _component_label(ctx):
    parts = []
    has_active_fvg = any(f.get('status') in ('UNFILLED', 'PARTIAL', 'PARTIALLY_FILLED') for f in ctx.get('fvgs', []))
    if has_active_fvg:
        parts.append('FVG')
        
    has_active_ob = any(o.get('status') == 'VALID' for o in ctx.get('obs', []))
    if has_active_ob:
        parts.append('OB')
        
    has_active_sd = any(s.get('status') == 'VALID' for s in ctx.get('sd', []))
    if has_active_sd:
        # ambil zone_type dari nearest_sd jika ada
        zt = ctx.get('nearest_sd', {}).get('zone_type', 'S/D') if ctx.get('nearest_sd') else 'S/D'
        parts.append(zt)
        
    has_active_ote = any(o.get('status') == 'ACTIVE' for o in ctx.get('ote', []))
    if has_active_ote:
        parts.append('OTE')
        
    has_active_liq = any(l.get('status') == 'ACTIVE' for l in ctx.get('liquidity', []))
    if has_active_liq:
        parts.append('Liquidity')
        
    if ctx.get('structure', {}).get('retest_mode', 'NONE') != 'NONE':
        parts.append('Retest')
        
    return ' + '.join(parts) if parts else 'Belum ada setup bersih'


def _priority(ctx):
    s = ctx.get('structure', {})
    m15 = str(s.get('m15_bias', 'neutral')).lower()
    m5 = str(s.get('m5_momentum', 'neutral')).lower()
    br = str(s.get('break_type') or '')
    if 'BEARISH' in br or (m15 == 'bearish' and m5 in ('bearish', 'neutral')):
        return 'WAIT SELL'
    if 'BULLISH' in br or (m15 == 'bullish' and m5 in ('bullish', 'neutral')):
        return 'WAIT BUY'
    return 'WAIT'


def _area(ctx):
    for key in ('nearest_fvg', 'nearest_ob', 'nearest_sd', 'nearest_ote'):
        r = ctx.get(key)
        if r and r.get('low') is not None and r.get('high') is not None:
            return f"{_fmt(r.get('low'))} - {_fmt(r.get('high'))}"
    br = ctx.get('structure', {}).get('break_level')
    if br:
        return f"{_fmt(float(br)-1.5)} - {_fmt(float(br)+1.5)}"
    return 'Belum valid'


def format_scalping_plan(storage, symbol, bot_state=None):
    ctx = build_context(storage, symbol, bot_state)
    s = ctx.get('structure', {})
    priority = _priority(ctx)
    area = _area(ctx)
    setup = _component_label(ctx)
    m15 = s.get('m15_bias', 'N/A')
    phase = s.get('trend') or ('CHOPPY' if s.get('choppy') else 'N/A')
    valid = 'M5 reject / MSS / reclaim jelas.'
    if 'SELL' in priority:
        action = 'Tunggu harga retest area pantau. Jangan sell kalau harga sudah jauh turun.'
        invalid = 'M5 close kuat di atas area pantau.'
    elif 'BUY' in priority:
        action = 'Tunggu harga retest area pantau. Jangan buy kalau harga sudah jauh naik.'
        invalid = 'M5 close kuat di bawah area pantau.'
    else:
        action = 'Tunggu sweep/retest/reclaim yang lebih bersih.'
        invalid = 'Harga tetap di tengah range tanpa displacement.'
    return (
        f"📍 XAUUSD Update {ctx['time']}\n\n"
        f"Bias scalping: {str(m15).upper()}\n"
        f"Phase: {phase}\n"
        f"Prioritas: {priority}\n\n"
        f"Area pantau:\n{area}\n\n"
        f"Setup:\n{setup}\n\n"
        f"Rencana:\n{action}\n\n"
        f"Valid kalau:\n{valid}\n\n"
        f"Batal kalau:\n{invalid}"
    )


def answer_area(storage, symbol, bot_state, kind):
    ctx = build_context(storage, symbol, bot_state)
    price = _fmt(ctx['price'])
    if kind == 'fvg':
        r = ctx.get('nearest_fvg')
        title = 'FVG aktif terdekat'
        typ = f"{r.get('direction')} FVG" if r else None
    elif kind == 'ob':
        r = ctx.get('nearest_ob')
        title = 'OB aktif terdekat'
        typ = f"{r.get('type') or r.get('direction')} OB" if r else None
    elif kind == 'ote':
        r = ctx.get('nearest_ote')
        title = 'OTE aktif terdekat'
        typ = f"{r.get('direction')} OTE" if r else None
    elif kind == 'liquidity':
        above = ctx.get('liq_above'); below = ctx.get('liq_below')
        return (
            f"💧 XAUUSD Liquidity\n\n"
            f"Harga: {price}\n"
            f"Liquidity atas: {_fmt(above.get('level')) if above else 'Tidak ada'}\n"
            f"Liquidity bawah: {_fmt(below.get('level')) if below else 'Tidak ada'}\n\n"
            f"Action:\nGunakan liquidity sebagai target, bukan entry langsung."
        )
    elif kind == 'sd':
        r = ctx.get('nearest_sd')
        title = 'Supply/Demand aktif terdekat'
        typ = r.get('zone_type') if r else None
    else:
        return format_scalping_plan(storage, symbol, bot_state)
    if not r:
        return f"{title}: belum ada area aktif yang relevan.\n\nHarga: {price}\nAction: tunggu area baru terbentuk."
    area = f"{_fmt(r.get('low'))} - {_fmt(r.get('high'))}"
    status = r.get('status', 'N/A')
    return (
        f"📍 XAUUSD {title}\n\n"
        f"Harga: {price}\n"
        f"Area: {area}\n"
        f"Type: {typ}\n"
        f"Status: {status}\n\n"
        f"Action:\nPantau reaksi M5 di area ini. Jangan entry hanya karena harga menyentuh area."
    )


def answer_history(storage):
    conn = storage.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM signals WHERE direction IN ('BUY','SELL')")
    total = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM signals WHERE result='LOSS'")
    loss = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM signals WHERE result IN ('WIN','BIG_WIN')")
    win = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM signals WHERE result='PARTIAL_WIN'")
    partial = cur.fetchone()[0] or 0
    cur.execute("SELECT event_type, price, event_time FROM signal_events ORDER BY id DESC LIMIT 5")
    events = cur.fetchall()
    conn.close()
    ev = '\n'.join([f"- {e[0]} @ {_fmt(e[1])}" for e in events]) or 'Belum ada event.'
    resolved = win + partial + loss
    wr = round(((win + partial) / resolved) * 100, 1) if resolved else 0
    return f"📊 History Singkat\n\nTotal trade: {total}\nWin: {win}\nPartial (TP1): {partial}\nLoss: {loss}\nWinrate: {wr}%\n\nEvent terakhir:\n{ev}"


def daily_recap(storage):
    """Generate a daily trading recap for today."""
    import sqlite3 as _sqlite3
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    conn = storage.get_connection()
    conn.row_factory = _sqlite3.Row
    cur = conn.cursor()

    # Today's closed signals
    cur.execute("""
        SELECT signal_class, direction, result, result_time, entry_low, sl, tp1, tp2
        FROM signals
        WHERE date(result_time) = ? AND status LIKE 'CLOSED%' AND result IS NOT NULL
        ORDER BY result_time
    """, (today,))
    closed = [dict(r) for r in cur.fetchall()]

    # Today's active signals
    cur.execute("""
        SELECT signal_class, direction, status, entry_low
        FROM signals
        WHERE status IN ('ACTIVE', 'PROTECTED', 'TP1_HIT', 'PENDING_ENTRY')
    """)
    active = [dict(r) for r in cur.fetchall()]

    # Today's events
    cur.execute("""
        SELECT event_type, COUNT(*) as cnt
        FROM signal_events
        WHERE date(event_time) = ?
        GROUP BY event_type
        ORDER BY cnt DESC
    """, (today,))
    event_summary = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Compute stats
    wins = sum(1 for s in closed if s.get('result') in ('WIN', 'FULL_WIN', 'PARTIAL_WIN'))
    losses = sum(1 for s in closed if s.get('result') == 'LOSS')
    total_closed = len(closed)
    wr = round((wins / total_closed) * 100, 1) if total_closed else 0
    net_r = (wins * 2) - losses  # simplified: WIN=+2R, LOSS=-1R

    # Method breakdown
    method_stats = {}
    for s in closed:
        m = s.get('signal_class') or 'UNKNOWN'
        if m not in method_stats:
            method_stats[m] = {'w': 0, 'l': 0}
        if s.get('result') in ('WIN', 'FULL_WIN', 'PARTIAL_WIN'):
            method_stats[m]['w'] += 1
        elif s.get('result') == 'LOSS':
            method_stats[m]['l'] += 1

    method_lines = []
    for m, st in sorted(method_stats.items(), key=lambda x: x[1]['w'] - x[1]['l'], reverse=True):
        emoji = "🟢" if st['w'] > st['l'] else "🔴" if st['l'] > st['w'] else "⚪"
        r = (st['w'] * 2) - st['l']
        method_lines.append(f"{emoji} {m}: {st['w']}W / {st['l']}L ({'+' if r >= 0 else ''}{r}R)")

    # Event lines
    ev_lines = []
    for ev in event_summary:
        ev_lines.append(f"  • {ev['event_type']}: {ev['cnt']}x")

    msg = (
        f"📋 DAILY RECAP — {today}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Ringkasan Hari Ini:\n"
        f"  Total Closed: {total_closed}\n"
        f"  Win: {wins} | Loss: {losses}\n"
        f"  Win Rate: {wr}%\n"
        f"  Net R: {'+' if net_r >= 0 else ''}{net_r}R\n\n"
    )

    if method_lines:
        msg += "📌 Per Metode:\n" + "\n".join(method_lines) + "\n\n"

    if active:
        msg += f"⏳ Masih Aktif: {len(active)} posisi\n"
        for a in active[:5]:
            msg += f"  • {a.get('signal_class', '?')} {a.get('direction', '?')} [{a.get('status')}]\n"
        msg += "\n"

    if ev_lines:
        msg += "🧾 Event Hari Ini:\n" + "\n".join(ev_lines) + "\n\n"

    if not closed and not active:
        msg += "💤 Belum ada aktivitas trading hari ini.\n"

    return msg


def answer_question(storage, symbol, bot_state, question):
    q = (question or '').lower()
    if any(x in q for x in ['history', 'riwayat', 'sl', 'tp', 'winrate', 'performa', 'loss']):
        return answer_history(storage)
    if any(x in q for x in ['fvg', 'fair value']):
        return answer_area(storage, symbol, bot_state, 'fvg')
    if any(x in q for x in ['ob', 'order block']):
        return answer_area(storage, symbol, bot_state, 'ob')
    if any(x in q for x in ['ote', 'fibo', 'fibonacci']):
        return answer_area(storage, symbol, bot_state, 'ote')
    if any(x in q for x in ['liquidity', 'liq', 'target']):
        return answer_area(storage, symbol, bot_state, 'liquidity')
    if any(x in q for x in ['demand', 'supply', 'snd']):
        return answer_area(storage, symbol, bot_state, 'sd')
    return format_scalping_plan(storage, symbol, bot_state)


def debug_fvg(storage, symbol, bot_state=None):
    ctx = build_context(storage, symbol, bot_state)
    r = ctx.get('nearest_fvg')
    if not r:
        return 'DEBUG FVG\nTidak ada active FVG tersimpan.'
    return (
        f"DEBUG FVG\n"
        f"TF: {r.get('timeframe')}\n"
        f"Type: {r.get('direction')} FVG\n"
        f"Area: {_fmt(r.get('low'))} - {_fmt(r.get('high'))}\n"
        f"Status: {r.get('status')}\n"
        f"Source candle: {r.get('source_candle_time')}\n"
        f"Valid for setup: {'YES' if r.get('status') in ('UNFILLED','PARTIAL','PARTIALLY_FILLED','HIT') else 'NO'}\n"
        f"Reason: candle[i-2] gap dengan candle[i], lalu dicek status filled/mitigated."
    )


def debug_ob(storage, symbol, bot_state=None):
    ctx = build_context(storage, symbol, bot_state)
    r = ctx.get('nearest_ob')
    if not r:
        return 'DEBUG OB\nTidak ada active OB tersimpan.'
    return (
        f"DEBUG OB\n"
        f"TF: {r.get('timeframe')}\n"
        f"Type: {r.get('type') or r.get('direction')} OB\n"
        f"Area: {_fmt(r.get('low'))} - {_fmt(r.get('high'))}\n"
        f"Status: {r.get('status')}\n"
        f"Source candle: {r.get('source_candle_time') or r.get('timestamp')}\n"
        f"Valid for setup: {'YES' if r.get('status') == 'VALID' else 'NO'}\n"
        f"Reason: {r.get('reason', 'candle sebelum displacement')}"
    )


def debug_ote(storage, symbol, bot_state=None):
    ctx = build_context(storage, symbol, bot_state)
    r = ctx.get('nearest_ote')
    if not r:
        return 'DEBUG OTE\nTidak ada active OTE tersimpan.'
    return (
        f"DEBUG OTE\n"
        f"TF: {r.get('timeframe')}\n"
        f"Direction: {r.get('direction')}\n"
        f"Area: {_fmt(r.get('low'))} - {_fmt(r.get('high'))}\n"
        f"Status: {r.get('status')}\n"
        f"Valid for setup: {'YES' if r.get('status') in ('ACTIVE','HIT') else 'NO'}\n"
        f"Reason: retracement 0.62-0.79 dari swing terakhir."
    )


def debug_poi(storage, symbol, bot_state=None):
    ctx = build_context(storage, symbol, bot_state)
    return (
        f"DEBUG POI\n"
        f"FVG: {'YES' if ctx.get('nearest_fvg') else 'NO'}\n"
        f"OB: {'YES' if ctx.get('nearest_ob') else 'NO'}\n"
        f"Supply/Demand: {'YES' if ctx.get('nearest_sd') else 'NO'}\n"
        f"OTE: {'YES' if ctx.get('nearest_ote') else 'NO'}\n"
        f"Liquidity: {'YES' if ctx.get('liquidity') else 'NO'}\n"
        f"Area pantau: {_area(ctx)}"
    )
