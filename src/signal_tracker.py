"""
Signal Tracker for XAUUSD Scalping Signal Bot.
Evaluates open/protected signals against current ticks to detect SL/TP hits.

Lifecycle:
PENDING_ENTRY -> ACTIVE when pending limit price is touched
PENDING_ENTRY -> CLOSED_EXPIRED when pending order expires
ACTIVE -> PROTECTED on TP1
PROTECTED -> CLOSED_PARTIAL_WIN if price returns to BE/protect before TP2
ACTIVE/PROTECTED -> CLOSED_WIN on TP2
ACTIVE/PROTECTED -> CLOSED_FULL_WIN on TP3
ACTIVE -> CLOSED_LOSS only if SL is hit before TP1
"""
from datetime import datetime, timezone
import logging
import time
from src.telegram_notifier import send_telegram_message, telegram_is_configured

logger = logging.getLogger("SignalTracker")


def notify_telegram_event(event_type, signal, current_price):
    if not telegram_is_configured():
        return
    try:
        from src.telegram_templates import format_trade_event
        send_telegram_message(format_trade_event(event_type, signal, current_price))
    except Exception:
        return


def _event_already_fired(storage, signal_id, event_type):
    conn = storage.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT 1 FROM signal_events WHERE signal_id = ? AND event_type = ?',
            (signal_id, event_type)
        )
        return bool(cursor.fetchone())
    finally:
        conn.close()


def _entry_price(signal):
    low = float(signal.get('entry_low') or 0)
    high = float(signal.get('entry_high') or 0)
    if low and high:
        return (low + high) / 2
    return float(signal.get('entry') or low or high or 0)


def _parse_iso_time(value):
    if not value:
        return None
    try:
        text = str(value).replace('Z', '+00:00')
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _pending_should_fill(signal, price):
    entry_type = (signal.get('entry_type') or '').upper()
    pending_price = signal.get('pending_price')
    if pending_price is None:
        return False
    pending_price = float(pending_price)
    if entry_type == 'BUY_LIMIT':
        return float(price) <= pending_price
    if entry_type == 'SELL_LIMIT':
        return float(price) >= pending_price
    return False


def _review_signal(storage, signal, sid, current_price):
    try:
        from src.ai_trainer import AdaptiveTrainer
        trainer_msg = AdaptiveTrainer(storage, signal.get('symbol', 'XAU/USD')).review_closed_signal(sid, current_price)
        logger.info(trainer_msg)
        if telegram_is_configured():
            send_telegram_message(trainer_msg)
    except Exception as e:
        logger.error(f"Adaptive trainer error: {e}")


def _fire_event(storage, signal, event, new_status, result, current_price, dt_utc, final_for_training=False):
    sid = signal['id']
    if _event_already_fired(storage, sid, event):
        return

    logger.info(f"Signal {sid} ({signal['direction']}) generated event {event} at {current_price}")
    storage.add_signal_event(sid, event, current_price, f"Price hit {current_price}", dt_utc)
    notify_telegram_event(event, signal, current_price)

    if new_status:
        storage.update_signal_status(sid, new_status, result, dt_utc)
        if event == 'SL_HIT' and result == 'LOSS':
            try:
                from src.sl_method_auditor import record_sl
                record_sl(storage, signal, current_price, dt_utc)
            except Exception as e:
                logger.error(f"SL auditor error: {e}")
        if final_for_training:
            _review_signal(storage, signal, sid, current_price)


def track_signals(storage, current_price, timestamp=None):
    dt_utc = datetime.now(timezone.utc).isoformat()
    try:
        if timestamp is not None:
            ts = int(timestamp)
            dt_utc = datetime.fromtimestamp(ts, timezone.utc).isoformat()
    except Exception:
        pass

    signals = storage.get_trackable_signals()
    price = float(current_price)
    now_dt = _parse_iso_time(dt_utc) or datetime.now(timezone.utc)

    for signal in signals:
        sid = signal['id']
        direction = signal['direction']
        status = signal.get('status')
        entry = _entry_price(signal)
        sl = float(signal.get('sl') or 0)
        tp1 = float(signal.get('tp1') or 0)
        tp2 = float(signal.get('tp2') or 0)
        tp3 = float(signal.get('tp3') or 0) if signal.get('tp3') else None

        if status == 'PENDING_ENTRY':
            expire_dt = _parse_iso_time(signal.get('pending_expire_time'))
            if expire_dt and now_dt >= expire_dt:
                _fire_event(storage, signal, 'EXPIRED', 'CLOSED_EXPIRED', 'EXPIRED', price, dt_utc, final_for_training=False)
                continue
            if _pending_should_fill(signal, price):
                storage.mark_pending_filled(sid, dt_utc)
                signal['status'] = 'ACTIVE'
                _fire_event(storage, signal, 'ENTRY_FILLED', None, None, price, dt_utc, final_for_training=False)
            else:
                continue

        if direction == 'BUY':
            if status == 'ACTIVE':
                if sl and price <= sl:
                    _fire_event(storage, signal, 'SL_HIT', 'CLOSED_LOSS', 'LOSS', price, dt_utc, final_for_training=True)
                    continue
                if tp1 and price >= tp1:
                    storage.update_signal_sl(sid, entry)
                    _fire_event(storage, signal, 'TP1_HIT', 'PROTECTED', None, price, dt_utc, final_for_training=False)
                    continue
            if status in ('PROTECTED', 'TP1_HIT'):
                if tp3 and price >= tp3:
                    _fire_event(storage, signal, 'TP3_HIT', 'CLOSED_FULL_WIN', 'FULL_WIN', price, dt_utc, final_for_training=True)
                    continue
                if tp2 and price >= tp2:
                    _fire_event(storage, signal, 'TP2_HIT', 'CLOSED_WIN', 'WIN', price, dt_utc, final_for_training=True)
                    continue
                if price <= entry:
                    _fire_event(storage, signal, 'PROTECTED', 'CLOSED_PARTIAL_WIN', 'PARTIAL_WIN', price, dt_utc, final_for_training=True)
                    continue

        elif direction == 'SELL':
            if status == 'ACTIVE':
                if sl and price >= sl:
                    _fire_event(storage, signal, 'SL_HIT', 'CLOSED_LOSS', 'LOSS', price, dt_utc, final_for_training=True)
                    continue
                if tp1 and price <= tp1:
                    storage.update_signal_sl(sid, entry)
                    _fire_event(storage, signal, 'TP1_HIT', 'PROTECTED', None, price, dt_utc, final_for_training=False)
                    continue
            if status in ('PROTECTED', 'TP1_HIT'):
                if tp3 and price <= tp3:
                    _fire_event(storage, signal, 'TP3_HIT', 'CLOSED_FULL_WIN', 'FULL_WIN', price, dt_utc, final_for_training=True)
                    continue
                if tp2 and price <= tp2:
                    _fire_event(storage, signal, 'TP2_HIT', 'CLOSED_WIN', 'WIN', price, dt_utc, final_for_training=True)
                    continue
                if price >= entry:
                    _fire_event(storage, signal, 'PROTECTED', 'CLOSED_PARTIAL_WIN', 'PARTIAL_WIN', price, dt_utc, final_for_training=True)
                    continue
