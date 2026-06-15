import os
import sqlite3
from datetime import datetime, timezone

from src.method_health import all_method_health
from src.method_registry import build_registry, classify_for_report, load_config, save_registry

DB_PATH = "data/backtest_results.sqlite"
REPORT_PATH = "reports/BACKTEST_RESULTS_REPORT.md"


def table_line(values):
    return "| " + " | ".join(str(v) for v in values) + " |"


def generate_report(db_path=DB_PATH, report_path=REPORT_PATH):
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    if not os.path.exists(db_path):
        print(f"DB belum ada: {db_path}")
        return False

    registry = build_registry(load_config())
    save_registry(registry)
    health = all_method_health(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    lines = []
    lines.append("# 📊 BACKTEST RESULTS REPORT V2")
    lines.append(f"Updated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Ringkasan Bulanan")
    lines.append(table_line(["Month", "Signal", "Closed", "WIN", "LOSS", "WR"]))
    lines.append(table_line(["---", "---:", "---:", "---:", "---:", "---:"]))
    try:
        cur.execute("SELECT run_month, total_signals, closed_trades, wins, losses, win_rate FROM backtest_runs ORDER BY run_month ASC")
        for r in cur.fetchall():
            lines.append(table_line([r["run_month"], r["total_signals"], r["closed_trades"], r["wins"], r["losses"], f"{float(r['win_rate'] or 0):.2f}%"]))
    except Exception:
        lines.append("| belum ada data | 0 | 0 | 0 | 0 | 0.00% |")

    lines.append("")
    lines.append("## Health Score Semua Metode")
    lines.append(table_line(["Status", "Method", "Trade", "WIN", "LOSS", "WR", "Active Months", "Consistency", "Score", "Verdict"]))
    lines.append(table_line(["---", "---", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---"]))
    for method, h in sorted(health.items(), key=lambda item: (-item[1]["score"], -item[1]["total"], item[0])):
        lines.append(table_line([
            classify_for_report(method),
            method,
            h["total"],
            h["wins"],
            h["losses"],
            f"{h['win_rate']:.2f}%",
            h["active_months"],
            f"{h['consistency']:.2f}%",
            h["score"],
            h["verdict"],
        ]))

    promote = [(m, h) for m, h in health.items() if h["verdict"] == "LAYAK_PROMOTE" and classify_for_report(m) != "LIVE_MAIN"]
    demote = [(m, h) for m, h in health.items() if h["verdict"] == "LAYAK_DEMOTE" and classify_for_report(m) == "LIVE_MAIN"]
    not_enough = [(m, h) for m, h in health.items() if h["verdict"] == "BELUM_CUKUP_DATA"]

    lines.append("")
    lines.append("## Rekomendasi Promote ke Whitelist")
    if promote:
        for m, h in sorted(promote, key=lambda item: -item[1]["score"]):
            lines.append(f"- {m}: WR {h['win_rate']:.2f}% | Trade {h['total']} | Score {h['score']}")
    else:
        lines.append("- Belum ada kandidat promote.")

    lines.append("")
    lines.append("## Rekomendasi Keluar dari Whitelist")
    if demote:
        for m, h in sorted(demote, key=lambda item: item[1]["score"]):
            lines.append(f"- {m}: WR {h['win_rate']:.2f}% | Loss {h['losses']} | Score {h['score']}")
    else:
        lines.append("- Belum ada kandidat demote.")

    lines.append("")
    lines.append("## Metode Belum Cukup Data")
    for m, h in sorted(not_enough, key=lambda item: item[0])[:80]:
        lines.append(f"- {m}: Trade {h['total']}")
    if len(not_enough) > 80:
        lines.append(f"- ... {len(not_enough) - 80} metode lain")

    lines.append("")
    lines.append("## Detail Per Bulan")
    try:
        cur.execute("SELECT DISTINCT run_month FROM backtest_method_summary ORDER BY run_month ASC")
        months = [r[0] for r in cur.fetchall()]
        for month in months:
            lines.append("")
            lines.append(f"### {month}")
            lines.append(table_line(["Status", "Method", "Trade", "WIN", "LOSS", "WR"]))
            lines.append(table_line(["---", "---", "---:", "---:", "---:", "---:"]))
            cur.execute(
                """
                SELECT pattern_key, total_trades, wins, losses, win_rate
                FROM backtest_method_summary
                WHERE run_month = ?
                ORDER BY total_trades DESC, win_rate DESC
                """,
                (month,),
            )
            for r in cur.fetchall():
                lines.append(table_line([
                    classify_for_report(r["pattern_key"]),
                    r["pattern_key"],
                    r["total_trades"],
                    r["wins"],
                    r["losses"],
                    f"{float(r['win_rate'] or 0):.2f}%",
                ]))
    except Exception as e:
        lines.append(f"Gagal baca detail bulanan: {e}")

    conn.close()
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✅ Report V2 dibuat: {report_path}")
    return True


if __name__ == "__main__":
    generate_report()
