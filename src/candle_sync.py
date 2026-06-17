from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional


TF_SECONDS = {
    'M1': 60,
    'M5': 300,
    'M15': 900,
    'H1': 3600,
    'H4': 14400,
    'D1': 86400,
}

FRESH_LIMIT_MINUTES = {
    'M5': 10,
    'M15': 25,
    'H1': 90,
    'H4': 300,
    'D1': 1800,
}

M5_PER_TIMEFRAME = {
    'M15': 3,
    'H1': 12,
    'H4': 48,
}


def parse_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    text = text.replace('Z', '+00:00')
    if ' ' in text and 'T' not in text:
        text = text.replace(' ', 'T', 1)
    if len(text) == 16:
        text = f"{text}:00"

    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(str(value).strip(), fmt)
                break
            except Exception:
                dt = None
        if dt is None:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_iso_from_ts(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), timezone.utc).isoformat(timespec='seconds')


def canonical_time(value: Any) -> Optional[str]:
    dt = parse_utc(value)
    if not dt:
        return None
    return dt.isoformat(timespec='seconds')


def open_ts_from_candle(candle: Dict[str, Any]) -> Optional[int]:
    dt = parse_utc(candle.get('open_time') or candle.get('time') or candle.get('timestamp'))
    if not dt:
        return None
    return int(dt.timestamp())


def expected_close_time(open_time: Any, timeframe: str) -> Optional[str]:
    dt = parse_utc(open_time)
    seconds = TF_SECONDS.get(str(timeframe or '').upper())
    if not dt or not seconds:
        return canonical_time(open_time)
    return utc_iso_from_ts(int(dt.timestamp()) + seconds - 1)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _dedupe_by_open_time(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dedup: Dict[int, Dict[str, Any]] = {}
    for candle in candles or []:
        ts = open_ts_from_candle(candle)
        if ts is None:
            continue
        current = dedup.get(ts)
        if current is None or _to_int(candle.get('id')) >= _to_int(current.get('id')):
            dedup[ts] = candle
    return [dedup[ts] for ts in sorted(dedup)]


def sync_closed_higher_timeframes_from_m5(storage, symbol: str, limit: int = 650) -> Dict[str, Any]:
    """Rebuild closed M15/H1/H4 candles from closed M5 candles.

    This keeps higher-timeframe OHLC aligned to the same base data as the M5 chart
    and avoids stale/fallback HTF rows being trusted by /market_context.
    """
    try:
        m5_rows = storage.get_recent_candles(symbol, 'M5', limit)
    except Exception as exc:
        return {'ok': False, 'error': str(exc), 'saved': {}}

    m5_rows = _dedupe_by_open_time(m5_rows)
    if len(m5_rows) < 3:
        return {'ok': False, 'error': 'not enough closed M5 candles', 'saved': {}}

    now_ts = int(time.time())
    saved: Dict[str, int] = {}

    for tf, expected_count in M5_PER_TIMEFRAME.items():
        tf_seconds = TF_SECONDS[tf]
        current_bucket = (now_ts // tf_seconds) * tf_seconds
        buckets: Dict[int, List[Dict[str, Any]]] = {}

        for candle in m5_rows:
            ts = open_ts_from_candle(candle)
            if ts is None:
                continue
            bucket_start = (ts // tf_seconds) * tf_seconds
            if bucket_start >= current_bucket:
                continue
            buckets.setdefault(bucket_start, []).append(candle)

        count_saved = 0
        for bucket_start, rows in sorted(buckets.items()):
            rows = _dedupe_by_open_time(rows)
            if len(rows) != expected_count:
                continue

            row_times = [open_ts_from_candle(row) for row in rows]
            expected_times = [bucket_start + (i * TF_SECONDS['M5']) for i in range(expected_count)]
            if row_times != expected_times:
                continue

            open_price = _to_float(rows[0].get('open'))
            high_price = max(_to_float(row.get('high')) for row in rows)
            low_price = min(_to_float(row.get('low')) for row in rows)
            close_price = _to_float(rows[-1].get('close'))
            volume_tick = sum(_to_int(row.get('volume_tick')) for row in rows)

            storage.save_candle(
                symbol=symbol,
                timeframe=tf,
                open_time=utc_iso_from_ts(bucket_start),
                close_time=utc_iso_from_ts(bucket_start + tf_seconds - 1),
                open_p=open_price,
                high_p=high_price,
                low_p=low_price,
                close_p=close_price,
                volume_tick=volume_tick,
                is_closed=True,
            )
            count_saved += 1

        saved[tf] = count_saved

    return {'ok': True, 'saved': saved}


def last_closed_candle_summary(storage, symbol: str, timeframe: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    tf = str(timeframe or '').upper()
    now = now or datetime.now(timezone.utc)
    try:
        rows = storage.get_recent_candles(symbol, tf, 1)
    except Exception as exc:
        return {
            'timeframe': tf,
            'available': False,
            'fresh': False,
            'status': 'STALE',
            'age_minutes': None,
            'reason': f'db_error: {exc}',
        }

    if not rows:
        return {
            'timeframe': tf,
            'available': False,
            'fresh': False,
            'status': 'STALE',
            'age_minutes': None,
            'reason': 'no closed candle',
        }

    candle = rows[-1]
    open_dt = parse_utc(candle.get('open_time'))
    seconds = TF_SECONDS.get(tf, 0)
    if open_dt and seconds:
        close_dt = open_dt.timestamp() + seconds - 1
        age_minutes = max(0.0, (now.timestamp() - close_dt) / 60.0)
        close_time_utc = utc_iso_from_ts(int(close_dt))
    else:
        age_minutes = None
        close_time_utc = canonical_time(candle.get('close_time'))

    limit = FRESH_LIMIT_MINUTES.get(tf, 999999)
    fresh = age_minutes is not None and age_minutes <= limit
    reason = 'ok' if fresh else f'age>{limit}m'

    return {
        'timeframe': tf,
        'available': True,
        'fresh': fresh,
        'status': 'FRESH' if fresh else 'STALE',
        'reason': reason,
        'time': canonical_time(candle.get('open_time')) or str(candle.get('open_time') or '-'),
        'time_utc': canonical_time(candle.get('open_time')) or str(candle.get('open_time') or '-'),
        'close_time_utc': close_time_utc,
        'age_minutes': round(age_minutes, 1) if age_minutes is not None else None,
        'open': _to_float(candle.get('open')),
        'high': _to_float(candle.get('high')),
        'low': _to_float(candle.get('low')),
        'close': _to_float(candle.get('close')),
        'closed': candle.get('is_closed', 1),
    }


def _same_ohlc(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    if not a.get('available') or not b.get('available'):
        return False
    keys = ('open', 'high', 'low', 'close')
    return all(round(_to_float(a.get(k)), 3) == round(_to_float(b.get(k)), 3) for k in keys)


def build_freshness_bundle(storage, symbol: str, bot_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    bot_state = bot_state or {}
    candles = {
        tf: last_closed_candle_summary(storage, symbol, tf, now)
        for tf in ('M5', 'M15', 'H1', 'H4')
    }

    h1 = candles.get('H1', {})
    h4 = candles.get('H4', {})
    if _same_ohlc(h1, h4) and h1.get('time_utc') == h4.get('time_utc'):
        h4['fresh'] = False
        h4['status'] = 'STALE'
        h4['reason'] = 'H1/H4 identical OHLC+time'

    critical = ('M5', 'M15', 'H1', 'H4')
    all_fresh = all(candles[tf].get('fresh') for tf in critical)
    htf_fresh = all(candles[tf].get('fresh') for tf in ('M15', 'H1', 'H4'))

    if all_fresh:
        data_status = 'FRESH'
    elif not htf_fresh:
        data_status = 'DATA STALE'
    else:
        data_status = 'PARTIAL STALE'

    live_price = bot_state.get('last_price')
    try:
        live_price = float(live_price)
    except Exception:
        live_price = None

    return {
        'updated_utc': now.isoformat(timespec='seconds'),
        'live_price': live_price,
        'price_source': bot_state.get('price_source') or 'Twelve Data WebSocket',
        'data_status': data_status,
        'htf_fresh': htf_fresh,
        'candles': candles,
    }
