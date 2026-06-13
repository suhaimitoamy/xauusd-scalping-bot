import logging
import sys


def setup_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
    return logger


def _fmt(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return "N/A"


def format_signal(signal, current_price=None, ai_used=False):
    source_label = "Source: RULE ENGINE + AI ADVISOR" if ai_used else "Source: RULE ENGINE"
    if not signal or signal.get('direction') == 'NO_TRADE':
        reason = signal.get('reason', 'Tunggu setup valid') if signal else 'Tunggu setup valid'
        conf = signal.get('confidence', 0) if signal else 0
        return (
            f"XAUUSD — NO TRADE\n"
            f"{source_label}\n\n"
            f"Harga: {_fmt(current_price)}\n"
            f"Confidence: {conf}%\n\n"
            f"Alasan:\n{reason}\n\n"
            f"Action:\nTunggu setup valid dari rule engine."
        )
    direction = signal.get('direction')
    emoji = '🟢' if direction == 'BUY' else '🔴'
    return (
        f"{emoji} XAUUSD {direction} SETUP\n"
        f"{source_label}\n\n"
        f"Harga sekarang: {_fmt(current_price)}\n"
        f"Area entry: {_fmt(signal.get('entry_low'))} - {_fmt(signal.get('entry_high'))}\n"
        f"SL: {_fmt(signal.get('sl'))}\n"
        f"TP1: {_fmt(signal.get('tp1'))}\n"
        f"TP2: {_fmt(signal.get('tp2'))}\n"
        f"Confidence: {signal.get('confidence', 0)}%\n"
        f"Invalid: {_fmt(signal.get('invalid_level'))}\n\n"
        f"Alasan:\n{signal.get('reason', 'N/A')}"
    )
