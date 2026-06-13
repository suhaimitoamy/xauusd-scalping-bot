from src.utils import load_config
from src.atr_engine import calculate_atr


def _near_level(value, fallback):
    try:
        return float(value) if value is not None else float(fallback)
    except Exception:
        return float(fallback)


def calculate_risk_params(direction, current_price, structure, m5_candles=None):
    """Calculate entry, SL, TP using sweep/POI/structure fallback.

    This version does not require sweep_extreme. If no sweep is available,
    it falls back to POI, support/resistance, and ATR so confluence setups
    (FVG/OB/OTE/retest) can still become valid signals.
    """
    config = load_config('config.yaml')
    risk_cfg = config.get('risk', {})
    min_sl = float(risk_cfg.get('min_sl_points', 4))
    max_sl = float(risk_cfg.get('max_sl_points', 10))
    tp1_rr = 1.0
    tp2_rr = 2.0

    entry = float(current_price)
    atr_m5 = calculate_atr(m5_candles) if m5_candles else 0.0
    atr_buffer = max(min_sl, float(atr_m5 or 0) * 1.0)

    poi_low = structure.get('poi_low')
    poi_high = structure.get('poi_high')
    swept_level = structure.get('swept_level')
    sweep_extreme = structure.get('sweep_extreme')

    if direction == 'BUY':
        anchor = sweep_extreme or swept_level or poi_low or structure.get('nearest_support') or (entry - min_sl)
        anchor = _near_level(anchor, entry - min_sl)
        dist = max(entry - anchor + 0.5, atr_buffer, min_sl)
        dist = min(dist, max_sl)
        sl = round(entry - dist, 2)
        tp1 = round(entry + dist * tp1_rr, 2)
        tp2 = round(entry + dist * tp2_rr, 2)
        return {
            'entry': entry,
            'entry_low': round(entry - 0.5, 2),
            'entry_high': round(entry + 0.5, 2),
            'sl': sl,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': None,
            'invalid_level': round(sl - 1.0, 2),
            'rr_ratio': round((tp1 - entry) / max(entry - sl, 0.01), 2)
        }

    if direction == 'SELL':
        anchor = sweep_extreme or swept_level or poi_high or structure.get('nearest_resistance') or (entry + min_sl)
        anchor = _near_level(anchor, entry + min_sl)
        dist = max(anchor - entry + 0.5, atr_buffer, min_sl)
        dist = min(dist, max_sl)
        sl = round(entry + dist, 2)
        tp1 = round(entry - dist * tp1_rr, 2)
        tp2 = round(entry - dist * tp2_rr, 2)
        return {
            'entry': entry,
            'entry_low': round(entry - 0.5, 2),
            'entry_high': round(entry + 0.5, 2),
            'sl': sl,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': None,
            'invalid_level': round(sl + 1.0, 2),
            'rr_ratio': round((entry - tp1) / max(sl - entry, 0.01), 2)
        }

    return None
