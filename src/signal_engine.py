"""Signal Engine for XAUUSD Scalping Signal Bot."""
from datetime import datetime, timezone
import sqlite3
from src.market_structure import analyze_structure
from src.risk_engine import calculate_risk_params
from src.session_filter import evaluate_session
from src.confidence_engine import calculate_confidence
from src.utils import load_config
from src.adaptive_confidence import adapt_confidence
from src.performance_analyzer import PerformanceAnalyzer


def _no_trade(reason, confidence=0):
    return {
        'symbol': 'XAU/USD', 'direction': 'NO_TRADE', 'entry_low': None,
        'entry_high': None, 'sl': None, 'tp1': None, 'tp2': None, 'tp3': None,
        'invalid_level': None, 'confidence': confidence, 'reason': reason,
        'status': 'NO_TRADE'
    }


def check_warmup(m5_candles, m15_candles, h1_candles, config):
    full = config.get('warmup', {}).get('full_mode', {})
    early = config.get('warmup', {}).get('early_mode', {})
    if len(m5_candles) >= full.get('m5_min_candles', 50) and len(m15_candles) >= full.get('m15_min_candles', 32) and len(h1_candles) >= full.get('h1_min_candles', 12):
        return 'FULL'
    if len(m5_candles) >= early.get('m5_min_candles', 24) and len(m15_candles) >= early.get('m15_min_candles', 8):
        return 'EARLY'
    return 'NOT READY'


def check_cooldown(storage, config):
    stats = storage.get_stats_today()
    if stats['total'] >= config.get('trading', {}).get('max_signals_per_day', 6):
        return True, 'Daily signal limit reached'
    conn = storage.get_connection(); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as active_count FROM signals WHERE status = 'ACTIVE'")
    active_row = cur.fetchone()
    if active_row and active_row['active_count'] > 0:
        conn.close()
        return True, 'Ada signal yang sedang aktif'

    cur.execute("SELECT * FROM signals WHERE status != 'NO_TRADE' ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone(); conn.close()
    if not row:
        return False, ''
    try:
        last_time = datetime.fromisoformat(row['created_at']).replace(tzinfo=timezone.utc)
        diff = (datetime.now(timezone.utc) - last_time).total_seconds()/60
        
        row_dict = dict(row)
        if row_dict.get('result') == 'LOSS' or row_dict.get('status') == 'CLOSED_LOSS':
            cd = config.get('trading', {}).get('cooldown_minutes_after_loss', 60)
            if diff < cd:
                return True, f'Cooldown setelah LOSS aktif for {int(cd-diff)}m'
        else:
            cd = config.get('trading', {}).get('cooldown_minutes_any_signal', 20)
            if diff < cd:
                return True, f'Cooldown active for {int(cd-diff)}m'
    except Exception:
        pass
    return False, ''


def _aliases(direction):
    return ('BUY', 'Bullish', 'BULLISH', 'bullish', 'Demand') if direction == 'BUY' else ('SELL', 'Bearish', 'BEARISH', 'bearish', 'Supply')


def _price_near(price, low, high, pad=1.5):
    try:
        low = float(low); high = float(high); price = float(price)
        return (low - pad) <= price <= (high + pad)
    except Exception:
        return False


def _load_components(storage, symbol, direction, price):
    conn = storage.get_connection(); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    aliases = _aliases(direction)
    qmarks = ','.join(['?']*len(aliases))
    comps = {'reasons': [], 'poi_low': None, 'poi_high': None, 'score': 0, 'target': None}
    def use_area(name, row, pts):
        if not row:
            return
        comps['reasons'].append(name)
        comps['score'] += pts
        if row['low'] is not None and row['high'] is not None:
            comps['poi_low'] = float(row['low']) if comps['poi_low'] is None else min(comps['poi_low'], float(row['low']))
            comps['poi_high'] = float(row['high']) if comps['poi_high'] is None else max(comps['poi_high'], float(row['high']))
    try:
        cur.execute(f"SELECT * FROM active_fvgs WHERE symbol=? AND status IN ('UNFILLED','PARTIAL','PARTIALLY_FILLED','HIT') AND direction IN ({qmarks}) ORDER BY created_at DESC LIMIT 8", (symbol, *aliases))
        for r in cur.fetchall():
            if _price_near(price, r['low'], r['high'], 2.5):
                use_area('FVG retest/fill', r, 15); break
        cur.execute(f"SELECT * FROM active_order_blocks WHERE (symbol=? OR symbol IS NULL) AND status='VALID' AND (direction IN ({qmarks}) OR type IN ({qmarks})) ORDER BY created_at DESC LIMIT 8", (symbol, *aliases, *aliases))
        for r in cur.fetchall():
            if _price_near(price, r['low'], r['high'], 3.0):
                use_area('OB retest', r, 15); break
        cur.execute(f"SELECT * FROM active_breakers WHERE (symbol=? OR symbol IS NULL) AND status='VALID' AND (direction IN ({qmarks}) OR type IN ({qmarks})) ORDER BY created_at DESC LIMIT 8", (symbol, *aliases, *aliases))
        for r in cur.fetchall():
            if _price_near(price, r['low'], r['high'], 3.0):
                use_area('Breaker retest', r, 12); break
        sd_type = 'Demand' if direction == 'BUY' else 'Supply'
        cur.execute("SELECT * FROM supply_demand_zones WHERE (symbol=? OR symbol IS NULL) AND status IN ('VALID','TOUCHED') AND zone_type=? ORDER BY created_at DESC LIMIT 8", (symbol, sd_type))
        for r in cur.fetchall():
            if _price_near(price, r['low'], r['high'], 3.0):
                use_area(f'{sd_type} retest', r, 12); break
        cur.execute(f"SELECT * FROM active_ote_zones WHERE (symbol=? OR symbol IS NULL) AND status IN ('ACTIVE','HIT') AND direction IN ({qmarks}) ORDER BY created_at DESC LIMIT 8", (symbol, *aliases))
        for r in cur.fetchall():
            if _price_near(price, r['low'], r['high'], 2.0):
                use_area('OTE touch', r, 10); break
        cur.execute("SELECT * FROM liquidity_pools WHERE (symbol=? OR symbol IS NULL) AND status='ACTIVE' ORDER BY level DESC LIMIT 20", (symbol,))
        pools = [dict(r) for r in cur.fetchall()]
        if direction == 'BUY':
            targets = [float(p['level']) for p in pools if p.get('level') is not None and float(p['level']) > price]
            comps['target'] = min(targets) if targets else None
        else:
            targets = [float(p['level']) for p in pools if p.get('level') is not None and float(p['level']) < price]
            comps['target'] = max(targets) if targets else None
        if comps['target']:
            comps['reasons'].append('Liquidity target jelas'); comps['score'] += 8
    except Exception:
        pass
    finally:
        conn.close()
    return comps


def generate_signal(symbol, current_price, m5_candles, m15_candles, h1_candles, data_health, storage):
    config = load_config('config.yaml')
    if check_warmup(m5_candles, m15_candles, h1_candles, config) == 'NOT READY':
        return _no_trade('Data belum cukup (Warmup)')
    if data_health and not data_health.get('is_healthy', True):
        return _no_trade('Data warming up or WS stale')

    session = evaluate_session()
    structure = analyze_structure(m5_candles, m15_candles, h1_candles)
    price = float(current_price)

    if structure.get('m15_bias') == 'choppy' or structure.get('choppy'):
        return _no_trade('Market condition is choppy, waiting for clear direction')

    cd_active, cd_reason = check_cooldown(storage, config)
    if cd_active:
        return _no_trade(cd_reason)

    # Direction from M15/M5, sweep, or BOS/MSS retest. H1/H4 are not hard blockers.
    direction = 'NO_TRADE'
    bt = str(structure.get('break_type') or '')
    if structure.get('sweep_type') == 'bullish' or 'BULLISH' in bt:
        direction = 'BUY'
    elif structure.get('sweep_type') == 'bearish' or 'BEARISH' in bt:
        direction = 'SELL'
    elif structure.get('m15_bias') == 'bullish' or structure.get('m5_momentum') == 'bullish':
        direction = 'BUY'
    elif structure.get('m15_bias') == 'bearish' or structure.get('m5_momentum') == 'bearish':
        direction = 'SELL'
    if direction == 'NO_TRADE':
        return _no_trade('Belum ada arah scalping yang cukup jelas')

    # Counter-structure validation
    bt_upper = bt.upper()
    is_counter = False
    counter_reason = ""
    
    if 'BEARISH' in bt_upper and direction == 'BUY':
        has_rev = (
            structure.get('sweep_type') == 'bullish' or 
            'BULLISH MSS' in bt_upper or
            structure.get('reclaim_valid', False) or
            structure.get('m5_momentum') == 'bullish'
        )
        if not has_rev:
            return _no_trade('BOS Bearish aktif. WAIT / WATCH BUY (butuh konfirmasi reversal)')
        is_counter = True
            
    elif 'BULLISH' in bt_upper and direction == 'SELL':
        has_rev = (
            structure.get('sweep_type') == 'bearish' or 
            'BEARISH MSS' in bt_upper or
            structure.get('reclaim_valid', False) or
            structure.get('m5_momentum') == 'bearish'
        )
        if not has_rev:
            return _no_trade('BOS Bullish aktif. WAIT / WATCH SELL (butuh konfirmasi reversal)')
        is_counter = True

    if is_counter:
        counter_reason = "Counter-structure setup. Butuh konfirmasi ekstra. "

    comps = _load_components(storage, symbol, direction, price)
    for key in ('poi_low', 'poi_high'):
        if comps.get(key) is not None:
            structure[key] = comps[key]
    if comps.get('target'):
        structure['target_liquidity'] = comps['target']

    # Confirmation: no longer sweep-only. M5 momentum/retest/POI touch can qualify as candidate.
    aligned_mom = structure.get('m5_momentum') == ('bullish' if direction == 'BUY' else 'bearish')
    has_retest = structure.get('retest_mode', 'NONE') != 'NONE'
    has_sweep = bool(structure.get('sweep_type'))
    has_poi = comps['score'] > 0
    if not (has_sweep or has_retest or has_poi):
        return _no_trade('Belum ada POI/retest/sweep aktif untuk setup')
    if not (aligned_mom or structure.get('reclaim_valid') or has_retest or has_poi):
        return _no_trade('Setup ada, tapi menunggu reject / MSS / reclaim')

    # --- Price Action Validation at POI ---
    if has_poi and comps.get('poi_low') is not None and comps.get('poi_high') is not None:
        from src.price_action import validate_price_action
        pa_valid, pa_reason = validate_price_action(direction, m5_candles, comps['poi_low'], comps['poi_high'])
        if not pa_valid:
            return _no_trade(pa_reason)
        else:
            comps['reasons'].append(pa_reason)

    risk = calculate_risk_params(direction, price, structure, m5_candles)
    if not risk or risk.get('error'):
        return _no_trade(risk.get('error', 'Risk invalid') if risk else 'Risk invalid')

    base = calculate_confidence(structure, risk, session, data_health)
    base += comps['score']
    base = max(0, min(100, base))
    stats = PerformanceAnalyzer(storage).get_weekly_stats()
    final = adapt_confidence(base, structure, risk, session, stats)
    
    # Strictly respect the config's min_confidence to enforce sniper accuracy
    min_conf = config.get('trading', {}).get('min_confidence', 65)
    if final < min_conf:
        return _no_trade(f'Confidence too low: {final}%', final)

    setup_parts = comps['reasons'][:] or ['Structure confirmation']
    if has_sweep:
        setup_parts.insert(0, 'Sweep/Reclaim')
    if has_retest:
        setup_parts.append('BOS/MSS Retest')
    setup_type = ' + '.join(dict.fromkeys(setup_parts))
    return {
        'symbol': symbol,
        'direction': direction,
        'entry_low': risk['entry_low'],
        'entry_high': risk['entry_high'],
        'sl': risk['sl'],
        'tp1': risk['tp1'],
        'tp2': risk['tp2'],
        'tp3': risk.get('tp3'),
        'invalid_level': risk['invalid_level'],
        'confidence_rule': base,
        'confidence_final': final,
        'confidence': final,
        'adaptive_note': 'Data belum cukup untuk adaptive confidence' if stats.get('total', 0) < 5 else 'Confidence disesuaikan dari history',
        'reason': f'{counter_reason}{direction} setup valid. Setup: {setup_type}, Bias: {structure.get("m15_bias", "N/A")}, Session: {session.get("session_name", "N/A")}',
        'status': 'ACTIVE'
    }
