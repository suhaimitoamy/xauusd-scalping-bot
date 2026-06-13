"""SL method auditor for approved main methods.

Records SL hits per method, collects compact failure reasons, and sends a
Telegram report when a main method reaches the configured SL thresholds.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.telegram_notifier import send_telegram_message, telegram_is_configured


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_config() -> Dict[str, Any]:
    try:
        import yaml
        cfg_path = _project_root() / "config.yaml"
        if cfg_path.exists():
            return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _extract_raw(signal: Dict[str, Any]) -> Dict[str, Any]:
    raw = signal.get("raw_context_json")
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _pattern_key(signal: Dict[str, Any]) -> str:
    raw = _extract_raw(signal)
    return str(signal.get("pattern_key") or raw.get("pattern_key") or "UNKNOWN_METHOD")


def _brain_context(signal: Dict[str, Any]) -> Dict[str, Any]:
    raw = _extract_raw(signal)
    ctx = raw.get("brain_context") or signal.get("brain_context") or {}
    return ctx if isinstance(ctx, dict) else {}


def _reason_text(signal: Dict[str, Any]) -> str:
    raw = _extract_raw(signal)
    return str(signal.get("reason") or raw.get("reason") or "")


def _load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"methods": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"methods": {}}


def _save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _classify_failure(method: str, signal: Dict[str, Any], current_price: float) -> List[str]:
    reason = _reason_text(signal).lower()
    ctx = _brain_context(signal)
    direction = str(signal.get("direction") or "").upper()
    tags: List[str] = []

    if method.startswith("METHOD_H1_BREAK"):
        tags.append("break H1 tidak lanjut setelah pullback/retest")
    elif method.startswith(("METHOD_CRT_H4", "METHOD_CRT_D1")):
        tags.append("CRT sweep/reclaim gagal bertahan")
    elif method.startswith(("METHOD_HW_SWEEP", "METHOD_M1_SWEEP", "METHOD_M5_SWEEP", "METHOD_HIGH_WR_M15_SWEEP")):
        tags.append("sweep reclaim gagal follow-through")
    elif method.startswith(("METHOD_HW_BREAK", "METHOD_M1_BREAK", "METHOD_M5_BREAK")):
        tags.append("break continuation gagal follow-through")
    elif method.startswith("METHOD_PATTERN"):
        tags.append("pattern candle gagal follow-through")
    elif method.startswith("METHOD_ICT_TURTLE"):
        tags.append("liquidity sweep/turtle soup gagal reversal")
    elif method.startswith("METHOD_ICT_UNICORN"):
        tags.append("FVG/Unicorn retest gagal hold")
    elif method.startswith("METHOD_ICT_AMD"):
        tags.append("AMD reversal gagal distribusi")
    else:
        tags.append("setup gagal follow-through")

    if ctx.get("choppy"):
        tags.append("market choppy")

    m15_bias = str(ctx.get("m15_bias") or "").lower()
    h1_bias = str(ctx.get("h1_bias") or "").lower()
    if direction == "BUY" and (m15_bias == "bearish" or h1_bias == "bearish"):
        tags.append("bias M15/H1 melawan BUY")
    if direction == "SELL" and (m15_bias == "bullish" or h1_bias == "bullish"):
        tags.append("bias M15/H1 melawan SELL")

    if "sweep" in reason and "reclaim" in reason:
        tags.append("reclaim tidak cukup kuat")
    if "break" in reason and "pullback" in reason:
        tags.append("pullback berubah jadi reversal")

    entry_low = signal.get("entry_low")
    entry_high = signal.get("entry_high")
    sl = signal.get("sl")
    try:
        entry_mid = (float(entry_low) + float(entry_high)) / 2
        sl_dist = abs(entry_mid - float(sl))
        if sl_dist <= 2.0:
            tags.append("SL sangat ketat")
        elif sl_dist >= 8.0:
            tags.append("SL lebar tapi tetap ditembus")
    except Exception:
        pass

    return list(dict.fromkeys(tags))[:5]


def _format_report(method: str, rec: Dict[str, Any], level: int) -> str:
    losses = rec.get("losses") or []
    tag_counter: Counter[str] = Counter()
    last_examples = losses[-5:]
    for item in losses:
        for tag in item.get("tags", []):
            tag_counter[tag] += 1

    top_reasons = tag_counter.most_common(6)
    reason_lines = "\n".join([f"- {name}: {count}x" for name, count in top_reasons]) or "- Belum ada klasifikasi detail"

    example_lines = []
    for item in last_examples:
        example_lines.append(
            f"- #{item.get('signal_id')} {item.get('direction')} price {item.get('sl_price')} | "
            f"{', '.join(item.get('tags', [])[:3])}"
        )
    examples = "\n".join(example_lines) or "- Tidak ada contoh"

    label = "WARNING" if level <= 10 else "CRITICAL"
    return (
        f"🧠 AI SL METHOD REPORT [{label}]\n"
        f"Method: {method}\n"
        f"Total SL terkumpul: {rec.get('total_sl', 0)}\n\n"
        f"Alasan dominan:\n{reason_lines}\n\n"
        f"Contoh SL terakhir:\n{examples}\n\n"
        f"Aksi: review metode ini sebelum dipakai lebih agresif."
    )


def record_sl(storage: Any, signal: Dict[str, Any], current_price: float, event_time: Optional[str] = None) -> Optional[str]:
    cfg = _load_config()
    ai_cfg = ((cfg.get("adaptive_brain") or {}).get("sl_intelligence") or {})
    if not bool(ai_cfg.get("enabled", True)):
        return None

    method = _pattern_key(signal)
    main_methods = set((cfg.get("adaptive_brain") or {}).get("main_methods") or [])
    if bool(ai_cfg.get("main_methods_only", True)) and method not in main_methods:
        return None

    rel_path = str(ai_cfg.get("storage_path") or "data/sl_method_audit.json")
    path = Path(rel_path)
    if not path.is_absolute():
        path = _project_root() / path

    state = _load_state(path)
    methods = state.setdefault("methods", {})
    rec = methods.setdefault(method, {"total_sl": 0, "last_report_level": 0, "losses": []})
    rec["total_sl"] = int(rec.get("total_sl") or 0) + 1

    item = {
        "signal_id": signal.get("id"),
        "time": event_time or datetime.now(timezone.utc).isoformat(),
        "direction": signal.get("direction"),
        "sl_price": round(float(current_price), 3),
        "entry_low": signal.get("entry_low"),
        "entry_high": signal.get("entry_high"),
        "sl": signal.get("sl"),
        "tp1": signal.get("tp1"),
        "tp2": signal.get("tp2"),
        "tags": _classify_failure(method, signal, float(current_price)),
        "reason": _reason_text(signal)[:300],
    }
    losses = rec.setdefault("losses", [])
    losses.append(item)
    max_examples = max(5, int(ai_cfg.get("max_examples_per_method", 25)))
    rec["losses"] = losses[-max_examples:]
    rec["updated_at"] = datetime.now(timezone.utc).isoformat()

    total_sl = int(rec.get("total_sl") or 0)
    warning = int(ai_cfg.get("warning_sl_count", 10))
    critical = int(ai_cfg.get("critical_sl_count", 20))
    repeat = int(ai_cfg.get("repeat_after_critical_every", 10))
    last_level = int(rec.get("last_report_level") or 0)

    report_level = 0
    if total_sl >= critical and total_sl > last_level:
        if last_level < critical or (repeat > 0 and total_sl % repeat == 0):
            report_level = total_sl
    elif total_sl >= warning and last_level < warning:
        report_level = warning

    report = None
    if report_level:
        rec["last_report_level"] = report_level
        report = _format_report(method, rec, report_level)

    _save_state(path, state)

    if report and bool(ai_cfg.get("send_to_telegram", True)) and telegram_is_configured():
        send_telegram_message(report)

    return report
