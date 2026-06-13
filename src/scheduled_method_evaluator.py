"""Scheduled method evaluator for Antigravity / manual cron.

Purpose:
- Evaluate only approved main methods from config.yaml.
- Enforce TP2-only RR 1:2 reporting: TP2/TP3 = +2R, SL = -1R.
- Never auto-edit methods. Output report only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METHOD_RE = re.compile(r"(RR2_GROUP_(?:BUY|SELL)|METHOD_[A-Z0-9_]+)")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    path = path or (PROJECT_ROOT / "config.yaml")
    if not path.exists() or yaml is None:
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def storage_path_from_config(cfg: Dict[str, Any]) -> Path:
    rel = ((cfg.get("storage") or {}).get("sqlite_path") or "data/xauusd_bot.sqlite")
    p = Path(str(rel))
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def main_methods_from_config(cfg: Dict[str, Any]) -> List[str]:
    return list(((cfg.get("adaptive_brain") or {}).get("main_methods") or []))


def locked_methods_from_config(cfg: Dict[str, Any]) -> List[str]:
    adaptive = cfg.get("adaptive_brain") or {}
    gov = adaptive.get("method_governance") or {}
    locked = gov.get("locked_methods") or []
    return list(locked)


def parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def extract_method(row: Dict[str, Any]) -> str:
    raw = row.get("raw_context_json")
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict):
                for key in ("pattern_key", "method", "method_name"):
                    val = data.get(key)
                    if val:
                        return str(val)
                ctx = data.get("brain_context")
                if isinstance(ctx, dict):
                    for key in ("pattern_key", "method", "method_name"):
                        val = ctx.get(key)
                        if val:
                            return str(val)
        except Exception:
            pass
    for field in ("reason", "status", "result"):
        m = METHOD_RE.search(str(row.get(field) or ""))
        if m:
            return m.group(1)
    return "UNKNOWN_METHOD"


def get_signals(db_path: Path, since: datetime, until: datetime) -> Tuple[List[Dict[str, Any]], Dict[int, set]]:
    if not db_path.exists():
        return [], {}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM signals
            WHERE created_at >= ? AND created_at < ?
              AND status != 'NO_TRADE'
            ORDER BY created_at ASC
            """,
            (since.isoformat(), until.isoformat()),
        )
        rows = [dict(r) for r in cur.fetchall()]
        ids = [r.get("id") for r in rows if r.get("id") is not None]
        event_map: Dict[int, set] = defaultdict(set)
        if ids:
            placeholders = ",".join(["?"] * len(ids))
            cur.execute(
                f"""
                SELECT signal_id, event_type FROM signal_events
                WHERE signal_id IN ({placeholders})
                """,
                ids,
            )
            for ev in cur.fetchall():
                event_map[int(ev["signal_id"])].add(str(ev["event_type"]))
        return rows, event_map
    finally:
        conn.close()


@dataclass
class MethodStats:
    method: str
    setup: int = 0
    tp2: int = 0
    sl: int = 0
    tp1_only: int = 0
    expired: int = 0
    active: int = 0
    net_r: int = 0
    wr_tp2: float = 0.0
    status: str = "WATCH"
    locked: bool = False


def classify_result(row: Dict[str, Any], events: set) -> str:
    result = str(row.get("result") or "").upper()
    status = str(row.get("status") or "").upper()
    if "TP3_HIT" in events or "TP2_HIT" in events or result in {"WIN", "FULL_WIN"}:
        return "TP2"
    if "SL_HIT" in events or result == "LOSS" or status == "CLOSED_LOSS":
        return "SL"
    if "TP1_HIT" in events or result == "PARTIAL_WIN" or status in {"PROTECTED", "CLOSED_PARTIAL_WIN"}:
        return "TP1_ONLY"
    if "EXPIRED" in events or result == "EXPIRED" or "EXPIRED" in status:
        return "EXPIRED"
    return "ACTIVE"


def evaluate_period(days: int = 7, db_path: Optional[Path] = None, until: Optional[datetime] = None) -> Dict[str, Any]:
    cfg = load_config()
    db_path = db_path or storage_path_from_config(cfg)
    until = until or utc_now()
    since = until - timedelta(days=days)
    main_methods = main_methods_from_config(cfg)
    main_set = set(main_methods)
    locked_set = set(locked_methods_from_config(cfg))

    rows, event_map = get_signals(db_path, since, until)
    stats: Dict[str, MethodStats] = {m: MethodStats(method=m, locked=(m in locked_set)) for m in main_methods}
    daily: Dict[str, Counter] = defaultdict(Counter)
    sl_hours: Counter = Counter()

    for row in rows:
        method = extract_method(row)
        if main_set and method not in main_set:
            continue
        rec = stats.setdefault(method, MethodStats(method=method, locked=(method in locked_set)))
        rec.setup += 1
        result = classify_result(row, event_map.get(int(row.get("id") or 0), set()))
        dt = parse_dt(row.get("created_at")) or until
        day_key = dt.date().isoformat()
        daily[day_key]["setup"] += 1
        daily[day_key][method] += 1

        if result == "TP2":
            rec.tp2 += 1
            daily[day_key]["tp2"] += 1
        elif result == "SL":
            rec.sl += 1
            daily[day_key]["sl"] += 1
            sl_hours[dt.hour] += 1
        elif result == "TP1_ONLY":
            rec.tp1_only += 1
            daily[day_key]["tp1_only"] += 1
        elif result == "EXPIRED":
            rec.expired += 1
            daily[day_key]["expired"] += 1
        else:
            rec.active += 1
            daily[day_key]["active"] += 1

    for rec in stats.values():
        closed = rec.tp2 + rec.sl
        rec.wr_tp2 = round((rec.tp2 / closed) * 100, 2) if closed else 0.0
        rec.net_r = (rec.tp2 * 2) - rec.sl
        if rec.locked:
            rec.status = "LOCKED"
        elif closed < 10:
            rec.status = "LOW_SAMPLE"
        elif rec.net_r <= 0 or rec.tp2 <= rec.sl:
            rec.status = "WEAK"
        else:
            rec.status = "WATCH"

    sorted_stats = sorted(stats.values(), key=lambda x: (x.net_r, x.tp2, -x.sl), reverse=True)
    total_setup = sum(x.setup for x in sorted_stats)
    total_tp2 = sum(x.tp2 for x in sorted_stats)
    total_sl = sum(x.sl for x in sorted_stats)
    closed = total_tp2 + total_sl
    total_wr = round((total_tp2 / closed) * 100, 2) if closed else 0.0
    total_net_r = (total_tp2 * 2) - total_sl

    day_rows = []
    for day, counter in sorted(daily.items()):
        dclosed = counter["tp2"] + counter["sl"]
        day_rows.append({
            "date": day,
            "setup": int(counter["setup"]),
            "tp2": int(counter["tp2"]),
            "sl": int(counter["sl"]),
            "tp1_only": int(counter["tp1_only"]),
            "expired": int(counter["expired"]),
            "active": int(counter["active"]),
            "wr_tp2": round((counter["tp2"] / dclosed) * 100, 2) if dclosed else 0.0,
            "net_r": int(counter["tp2"] * 2 - counter["sl"]),
        })

    return {
        "generated_at_utc": until.isoformat(),
        "period_days": days,
        "since_utc": since.isoformat(),
        "until_utc": until.isoformat(),
        "db_path": str(db_path),
        "policy": "TP2 only; RR 1:2; TP2=+2R; SL=-1R; TP1-only is not counted as win.",
        "summary": {
            "main_method_count": len(main_methods),
            "setup": total_setup,
            "tp2": total_tp2,
            "sl": total_sl,
            "wr_tp2": total_wr,
            "net_r": total_net_r,
        },
        "sl_hours_top": sl_hours.most_common(6),
        "methods": [asdict(x) for x in sorted_stats],
        "daily": day_rows,
    }


def build_ai_note(payload: Dict[str, Any]) -> str:
    fallback = "AI note offline. Pakai data rule engine saja; tidak ada perubahan metode otomatis."
    try:
        from src.ai_advisor import get_ai_response
        compact = {
            "policy": payload.get("policy"),
            "summary": payload.get("summary"),
            "sl_hours_top": payload.get("sl_hours_top"),
            "methods": payload.get("methods", [])[:12],
        }
        prompt = (
            "Kamu adalah evaluator bot XAUUSD. Tugasmu hanya audit performa, bukan mengubah rule. "
            "Metode LOCKED tidak boleh disarankan untuk diubah. Berikan laporan sangat ringkas dalam Bahasa Indonesia: "
            "1) kondisi umum, 2) metode terkuat, 3) metode yang perlu dipantau, 4) jam rawan SL, 5) aksi tanpa edit rule.\n\n"
            + json.dumps(compact, ensure_ascii=False)
        )
        messages = [
            {"role": "system", "content": "You are a strict trading-method auditor. Do not suggest changing locked methods. No chain-of-thought."},
            {"role": "user", "content": prompt},
        ]
        note, _ = get_ai_response(messages, fallback, max_tokens=450, timeout=30)
        return note
    except Exception:
        return fallback


def render_markdown(payload: Dict[str, Any], include_ai: bool = True) -> str:
    s = payload["summary"]
    lines = [
        f"# XAUUSD Method Evaluation Report",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Period: {payload['period_days']} days",
        f"Policy: {payload['policy']}",
        "",
        "## Summary",
        "",
        "| Main Methods | Setup | TP2 | SL | WR TP2 | Net R |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {s['main_method_count']} | {s['setup']} | {s['tp2']} | {s['sl']} | {s['wr_tp2']}% | {s['net_r']}R |",
        "",
        "## Method Performance",
        "",
        "| Method | Status | Setup | TP2 | SL | TP1-only | Expired | Active | WR TP2 | Net R |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in payload.get("methods", []):
        lines.append(
            f"| `{m['method']}` | {m['status']} | {m['setup']} | {m['tp2']} | {m['sl']} | "
            f"{m['tp1_only']} | {m['expired']} | {m['active']} | {m['wr_tp2']}% | {m['net_r']}R |"
        )
    lines += ["", "## Daily Summary", "", "| Date | Setup | TP2 | SL | TP1-only | WR TP2 | Net R |", "|---|---:|---:|---:|---:|---:|---:|"]
    for d in payload.get("daily", []):
        lines.append(f"| {d['date']} | {d['setup']} | {d['tp2']} | {d['sl']} | {d['tp1_only']} | {d['wr_tp2']}% | {d['net_r']}R |")
    lines += ["", "## Top SL Hours UTC", ""]
    if payload.get("sl_hours_top"):
        for hour, count in payload["sl_hours_top"]:
            lines.append(f"- {hour:02d}:00 UTC = {count} SL")
    else:
        lines.append("- Tidak ada SL di periode ini.")
    if include_ai:
        lines += ["", "## AI Note", "", build_ai_note(payload)]
    lines += ["", "## Rule Safety", "", "Tidak ada perubahan metode otomatis. Semua edit metode wajib approval owner."]
    return "\n".join(lines).strip() + "\n"


def write_outputs(payload: Dict[str, Any], label: str, out_dir: Optional[Path] = None, include_ai: bool = True) -> Tuple[Path, Path]:
    out_dir = out_dir or (PROJECT_ROOT / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"{label}_method_eval_{stamp}.json"
    md_path = out_dir / f"{label}_method_eval_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(payload, include_ai=include_ai), encoding="utf-8")
    return md_path, json_path


def send_telegram(markdown_text: str) -> bool:
    try:
        from src.telegram_notifier import send_telegram_message, telegram_is_configured
        if not telegram_is_configured():
            return False
        # Keep Telegram plain text; strip markdown table is still readable.
        return send_telegram_message(markdown_text[:12000])
    except Exception:
        return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scheduled method evaluator for XAUUSD bot")
    parser.add_argument("--period", choices=["weekly", "monthly"], default="weekly")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--send-telegram", action="store_true")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI note; report remains rule-engine only")
    args = parser.parse_args(argv)

    days = args.days if args.days is not None else (7 if args.period == "weekly" else 30)
    payload = evaluate_period(days=days)
    md_path, json_path = write_outputs(payload, args.period, include_ai=not args.no_ai)
    text = md_path.read_text(encoding="utf-8")
    if args.send_telegram:
        send_telegram(text)
    print(f"Report saved: {md_path}")
    print(f"JSON saved: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
