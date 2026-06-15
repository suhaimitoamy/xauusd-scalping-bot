import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = "data/xauusd_bot.sqlite"
REPORT_PATH = "reports/DAILY_AUDIT.md"

WIN_RESULTS = {"WIN", "FULL_WIN", "PARTIAL_WIN"}
LOSS_RESULTS = {"LOSS"}


def generate_daily_audit(db_path=DB_PATH, report_path=REPORT_PATH, day=None):
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    if day is None:
        day = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()

    if not os.path.exists(db_path):
        print(f"DB tidak ditemukan: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM signals
        WHERE status LIKE 'CLOSED%'
          AND COALESCE(result_time, created_at) LIKE ?
        ORDER BY COALESCE(result_time, created_at) ASC
        """,
        (f"{day}%",),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    total = len(rows)
    wins = sum(1 for r in rows if str(r.get("result") or "").upper() in WIN_RESULTS)
    losses = sum(1 for r in rows if str(r.get("result") or "").upper() in LOSS_RESULTS)
    wr = (wins / total * 100) if total else 0.0

    by_method = {}
    by_hour = {}
    for r in rows:
        method = r.get("pattern_key") or r.get("signal_class") or "UNKNOWN"
        result = str(r.get("result") or "").upper()
        m = by_method.setdefault(method, {"total": 0, "win": 0, "loss": 0})
        m["total"] += 1
        if result in WIN_RESULTS:
            m["win"] += 1
        if result in LOSS_RESULTS:
            m["loss"] += 1
        t = r.get("result_time") or r.get("created_at") or ""
        hour = t[11:13] if len(t) >= 13 else "??"
        h = by_hour.setdefault(hour, {"total": 0, "win": 0, "loss": 0})
        h["total"] += 1
        if result in WIN_RESULTS:
            h["win"] += 1
        if result in LOSS_RESULTS:
            h["loss"] += 1

    lines = []
    lines.append("# 🌅 DAILY AUDIT XAUUSD BOT")
    lines.append(f"Tanggal audit: {day} UTC")
    lines.append("")
    lines.append(f"Total closed trade: {total}")
    lines.append(f"WIN: {wins}")
    lines.append(f"LOSS: {losses}")
    lines.append(f"WR: {wr:.2f}%")
    lines.append("")
    lines.append("## Metode")
    lines.append("| Method | Total | WIN | LOSS | WR |")
    lines.append("|---|---:|---:|---:|---:|")
    for method, s in sorted(by_method.items(), key=lambda item: (-item[1]["total"], item[0])):
        mwr = (s["win"] / s["total"] * 100) if s["total"] else 0.0
        lines.append(f"| {method} | {s['total']} | {s['win']} | {s['loss']} | {mwr:.2f}% |")

    lines.append("")
    lines.append("## Jam Trading")
    lines.append("| Hour UTC | Total | WIN | LOSS | WR |")
    lines.append("|---|---:|---:|---:|---:|")
    for hour, s in sorted(by_hour.items()):
        hwr = (s["win"] / s["total"] * 100) if s["total"] else 0.0
        lines.append(f"| {hour} | {s['total']} | {s['win']} | {s['loss']} | {hwr:.2f}% |")

    lines.append("")
    if losses >= 3:
        lines.append("Status: ⚠️ Perlu hati-hati, loss harian cukup banyak.")
    elif total == 0:
        lines.append("Status: Netral, belum ada closed trade.")
    else:
        lines.append("Status: ✅ Aman dipantau lanjut.")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✅ Daily audit dibuat: {report_path}")
    return True


if __name__ == "__main__":
    generate_daily_audit()
