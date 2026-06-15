import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone

WIN_RESULTS = {"WIN", "FULL_WIN", "PARTIAL_WIN", "PROTECTED", "TP1_HIT", "TP2_HIT"}
LOSS_RESULTS = {"LOSS"}


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def parse_json(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def nested_raw(signal_json):
    raw = signal_json.get("raw_context_json")
    return parse_json(raw)


def get_pattern_key(row, signal_json):
    nested = nested_raw(signal_json)
    return (
        signal_json.get("pattern_key")
        or nested.get("pattern_key")
        or signal_json.get("method")
        or signal_json.get("source")
        or row.get("signal_class")
        or "UNKNOWN_METHOD"
    )


def get_simulation_id(signal_json):
    nested = nested_raw(signal_json)
    return signal_json.get("simulation_id") or nested.get("simulation_id") or "UNKNOWN_SIM"


def get_dataset_key(signal_json):
    nested = nested_raw(signal_json)
    return signal_json.get("dataset_key") or nested.get("dataset_key") or "UNKNOWN_DATASET"


def normalized_result(row):
    result = (row.get("result") or "").upper()
    status = (row.get("status") or "").upper()
    if result:
        return result
    if status.startswith("CLOSED_"):
        return status.replace("CLOSED_", "")
    return status or "UNKNOWN"


def is_win(result):
    return result in WIN_RESULTS


def is_loss(result):
    return result in LOSS_RESULTS


def ensure_dest_schema(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS backtest_runs (
            run_month TEXT PRIMARY KEY,
            source_db TEXT,
            exported_at TEXT,
            total_signals INTEGER,
            closed_trades INTEGER,
            wins INTEGER,
            losses INTEGER,
            win_rate REAL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS backtest_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_month TEXT,
            source_signal_id INTEGER,
            simulation_id TEXT,
            dataset_key TEXT,
            pattern_key TEXT,
            signal_class TEXT,
            signal_timeframe TEXT,
            symbol TEXT,
            direction TEXT,
            status TEXT,
            result TEXT,
            created_at TEXT,
            result_time TEXT,
            entry_low REAL,
            entry_high REAL,
            sl REAL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            confidence REAL,
            reason TEXT,
            raw_context_json TEXT,
            UNIQUE(run_month, source_signal_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS backtest_method_summary (
            run_month TEXT,
            pattern_key TEXT,
            total_trades INTEGER,
            wins INTEGER,
            losses INTEGER,
            win_rate REAL,
            updated_at TEXT,
            PRIMARY KEY (run_month, pattern_key)
        )
    """)
    conn.commit()


def read_source_signals(source_db):
    if not os.path.exists(source_db):
        raise FileNotFoundError(f"Source DB tidak ditemukan: {source_db}")
    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
    if not cur.fetchone():
        conn.close()
        return []
    cur.execute("SELECT * FROM signals WHERE direction IS NOT NULL AND direction != 'NO_TRADE' ORDER BY id ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def export_results(run_month, source_db, dest_db, report_path):
    os.makedirs(os.path.dirname(dest_db) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)

    rows = read_source_signals(source_db)
    dest = sqlite3.connect(dest_db)
    ensure_dest_schema(dest)
    cur = dest.cursor()

    cur.execute("DELETE FROM backtest_trades WHERE run_month = ?", (run_month,))
    cur.execute("DELETE FROM backtest_method_summary WHERE run_month = ?", (run_month,))
    cur.execute("DELETE FROM backtest_runs WHERE run_month = ?", (run_month,))

    method_stats = {}
    wins = 0
    losses = 0
    closed = 0

    for row in rows:
        signal_json = parse_json(row.get("raw_context_json"))
        pattern_key = get_pattern_key(row, signal_json)
        result = normalized_result(row)
        if result != "UNKNOWN":
            closed += 1
        if is_win(result):
            wins += 1
        if is_loss(result):
            losses += 1

        stats = method_stats.setdefault(pattern_key, {"total": 0, "wins": 0, "losses": 0})
        stats["total"] += 1
        if is_win(result):
            stats["wins"] += 1
        if is_loss(result):
            stats["losses"] += 1

        cur.execute("""
            INSERT OR REPLACE INTO backtest_trades (
                run_month, source_signal_id, simulation_id, dataset_key, pattern_key,
                signal_class, signal_timeframe, symbol, direction, status, result,
                created_at, result_time, entry_low, entry_high, sl, tp1, tp2, tp3,
                confidence, reason, raw_context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_month,
            row.get("id"),
            get_simulation_id(signal_json),
            get_dataset_key(signal_json),
            pattern_key,
            row.get("signal_class"),
            row.get("signal_timeframe"),
            row.get("symbol"),
            row.get("direction"),
            row.get("status"),
            result,
            row.get("created_at"),
            row.get("result_time"),
            row.get("entry_low"),
            row.get("entry_high"),
            row.get("sl"),
            row.get("tp1"),
            row.get("tp2"),
            row.get("tp3"),
            row.get("confidence"),
            row.get("reason"),
            row.get("raw_context_json"),
        ))

    for pattern_key, stats in sorted(method_stats.items(), key=lambda item: item[1]["total"], reverse=True):
        total = stats["total"]
        wr = round((stats["wins"] / total) * 100, 2) if total else 0.0
        cur.execute("""
            INSERT OR REPLACE INTO backtest_method_summary
            (run_month, pattern_key, total_trades, wins, losses, win_rate, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_month, pattern_key, total, stats["wins"], stats["losses"], wr, now_utc()))

    total_signals = len(rows)
    wr_all = round((wins / (wins + losses)) * 100, 2) if (wins + losses) else 0.0
    cur.execute("""
        INSERT OR REPLACE INTO backtest_runs
        (run_month, source_db, exported_at, total_signals, closed_trades, wins, losses, win_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (run_month, source_db, now_utc(), total_signals, closed, wins, losses, wr_all))

    dest.commit()
    write_report(dest, report_path)
    dest.close()

    print(f"✅ Hasil backtest {run_month} disimpan permanen ke {dest_db}")
    print(f"✅ Report otomatis dibuat/update: {report_path}")
    print(f"Total signal: {total_signals} | WIN: {wins} | LOSS: {losses} | WR: {wr_all:.2f}%")


def write_report(conn, report_path):
    cur = conn.cursor()
    updated = now_utc()
    lines = []
    lines.append("# 📊 Persistent Backtest Results")
    lines.append(f"**Updated:** {updated}")
    lines.append("")
    lines.append("## Monthly Summary")
    lines.append("| Month | Total Signal | Closed | WIN | LOSS | Win Rate |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    cur.execute("SELECT * FROM backtest_runs ORDER BY run_month ASC")
    for r in cur.fetchall():
        lines.append(f"| {r[0]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]:.2f}% |")

    lines.append("")
    lines.append("## Method Summary - All Months")
    lines.append("| Method | Total Trade | WIN | LOSS | Win Rate |")
    lines.append("|---|---:|---:|---:|---:|")
    cur.execute("""
        SELECT pattern_key,
               SUM(total_trades) AS total_trades,
               SUM(wins) AS wins,
               SUM(losses) AS losses
        FROM backtest_method_summary
        GROUP BY pattern_key
        ORDER BY total_trades DESC
    """)
    for pattern_key, total, wins, losses in cur.fetchall():
        wr = (wins / total * 100) if total else 0.0
        lines.append(f"| {pattern_key} | {total} | {wins} | {losses} | {wr:.2f}% |")

    lines.append("")
    lines.append("## Method Summary - By Month")
    cur.execute("SELECT DISTINCT run_month FROM backtest_method_summary ORDER BY run_month ASC")
    months = [r[0] for r in cur.fetchall()]
    for month in months:
        lines.append("")
        lines.append(f"### {month}")
        lines.append("| Method | Total Trade | WIN | LOSS | Win Rate |")
        lines.append("|---|---:|---:|---:|---:|")
        cur.execute("""
            SELECT pattern_key, total_trades, wins, losses, win_rate
            FROM backtest_method_summary
            WHERE run_month = ?
            ORDER BY total_trades DESC, win_rate DESC
        """, (month,))
        for pattern_key, total, wins, losses, wr in cur.fetchall():
            lines.append(f"| {pattern_key} | {total} | {wins} | {losses} | {wr:.2f}% |")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Save monthly ghost backtest result into persistent DB")
    parser.add_argument("run_month", help="Format YYYY-MM, contoh 2022-05")
    parser.add_argument("--source-db", default="data/xauusd_bot_ghost.sqlite")
    parser.add_argument("--dest-db", default="data/backtest_results.sqlite")
    parser.add_argument("--report", default="reports/BACKTEST_RESULTS_REPORT.md")
    args = parser.parse_args()
    export_results(args.run_month, args.source_db, args.dest_db, args.report)


if __name__ == "__main__":
    main()
