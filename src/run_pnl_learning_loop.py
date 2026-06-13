import argparse
import glob
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def month_range(start_month, end_month):
    months = []
    year = int(start_month[:4])
    month = int(start_month[4:])
    end_year = int(end_month[:4])
    end_m = int(end_month[4:])
    while (year, month) <= (end_year, end_m):
        months.append(f"{year}{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def load_config():
    import yaml
    try:
        with open(os.path.join(ROOT, "config.yaml"), "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def db_path():
    cfg = load_config()
    return os.path.join(ROOT, cfg.get("db_path", "data/xauusd_bot.sqlite"))


def backup_main_db(path):
    if not os.path.exists(path):
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{path}.bak_pnl_loop_{stamp}"
    shutil.copy2(path, backup)
    return backup


def ensure_registry(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS method_registry (
            method_name TEXT PRIMARY KEY,
            status TEXT,
            confidence REAL,
            trades INTEGER,
            wins INTEGER,
            losses INTEGER,
            net_pl REAL,
            profit_factor REAL,
            max_dd_pct REAL,
            stable_months INTEGER,
            cooldown_until TEXT,
            updated_at TEXT,
            notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pnl_learning_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            cycle INTEGER,
            month TEXT,
            report_json TEXT
        )
        """
    )
    conn.commit()


def run_cmd(cmd):
    print("[RUN]", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr)
        raise SystemExit(result.returncode)
    return result


def read_report():
    path = os.path.join(ROOT, "data", "virtual_sim_report.json")
    with open(path, "r") as f:
        return json.load(f)


def latest_candidate_file():
    files = glob.glob(os.path.join(ROOT, "brain_versions", "ai_method_candidates_*.json"))
    return max(files, key=os.path.getctime) if files else None


def status_from_stats(stats, monthly_good, monthly_bad):
    trades = int(stats.get("trades") or 0)
    wins = int(stats.get("wins") or 0)
    losses = int(stats.get("losses") or 0)
    net_pl = float(stats.get("net_pl") or 0)
    pf = float(stats.get("profit_factor") or 0)
    dd = float(stats.get("max_dd_pct") or 0)
    wr = (wins / trades * 100.0) if trades else 0.0

    if trades >= 30 and wr < 20 and (net_pl < -300 or dd >= 35):
        return "DISABLED_ONLY_IF_EXTREME", 5, "Extreme: WR<20%, trade cukup, dan PNL/DD buruk"
    if dd >= 25 or net_pl < -150:
        return "COOLDOWN", 15, "Drawdown/PNL buruk, masuk cooldown sementara"
    if monthly_good >= 3 and net_pl > 0 and pf >= 1.2 and trades >= 30 and dd <= 18:
        return "ACTIVE", 80, "Profit stabil lintas bulan"
    if monthly_good >= 1 and net_pl > 0 and pf >= 1.0:
        return "PROBATION", 60, "PNL positif, masih butuh validasi stabilitas"
    if monthly_bad and net_pl >= -150:
        return "RECOVERY_TEST", 40, "Pernah rugi tapi belum extreme, uji recovery"
    return "PROBATION", 50, "Data belum cukup untuk keputusan kuat"


def update_method_registry(conn, aggregate, monthly_pattern_pnl):
    changes = []
    for method, stats in aggregate.items():
        month_values = monthly_pattern_pnl.get(method, [])
        monthly_good = sum(1 for x in month_values if x > 0)
        monthly_bad = sum(1 for x in month_values if x < 0)
        status, confidence, note = status_from_stats(stats, monthly_good, monthly_bad)
        cooldown_until = None
        if status == "COOLDOWN":
            cooldown_until = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        prev = conn.execute(
            "SELECT status FROM method_registry WHERE method_name=?",
            (method,),
        ).fetchone()
        prev_status = prev[0] if prev else None
        if prev_status != status:
            changes.append({"method": method, "from": prev_status, "to": status, "note": note})

        conn.execute(
            """
            INSERT INTO method_registry
            (method_name, status, confidence, trades, wins, losses, net_pl, profit_factor,
             max_dd_pct, stable_months, cooldown_until, updated_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(method_name) DO UPDATE SET
                status=excluded.status,
                confidence=excluded.confidence,
                trades=excluded.trades,
                wins=excluded.wins,
                losses=excluded.losses,
                net_pl=excluded.net_pl,
                profit_factor=excluded.profit_factor,
                max_dd_pct=excluded.max_dd_pct,
                stable_months=excluded.stable_months,
                cooldown_until=excluded.cooldown_until,
                updated_at=excluded.updated_at,
                notes=excluded.notes
            """,
            (
                method,
                status,
                confidence,
                int(stats.get("trades") or 0),
                int(stats.get("wins") or 0),
                int(stats.get("losses") or 0),
                round(float(stats.get("net_pl") or 0), 2),
                round(float(stats.get("profit_factor") or 0), 4),
                round(float(stats.get("max_dd_pct") or 0), 4),
                monthly_good,
                cooldown_until,
                utc_now(),
                note,
            ),
        )
    conn.commit()
    return changes


def merge_pattern_stats(report, aggregate, monthly_pattern_pnl):
    for pattern, stats in report.get("patterns", {}).items():
        agg = aggregate.setdefault(
            pattern,
            {"trades": 0, "wins": 0, "losses": 0, "net_pl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0, "max_dd_pct": 0.0},
        )
        agg["trades"] += int(stats.get("trades") or 0)
        agg["wins"] += int(stats.get("wins") or 0)
        agg["losses"] += int(stats.get("losses") or 0)
        net_pl = float(stats.get("net_pl") or 0)
        agg["net_pl"] += net_pl
        agg["gross_profit"] += float(stats.get("gross_profit") or 0)
        agg["gross_loss"] += float(stats.get("gross_loss") or 0)
        agg["max_dd_pct"] = max(agg["max_dd_pct"], float(report.get("max_dd_pct") or 0))
        monthly_pattern_pnl.setdefault(pattern, []).append(net_pl)

    for stats in aggregate.values():
        gl = float(stats.get("gross_loss") or 0)
        gp = float(stats.get("gross_profit") or 0)
        stats["profit_factor"] = (gp / gl) if gl else (999.0 if gp else 0.0)


def main():
    parser = argparse.ArgumentParser(description="PNL-focused AI learning loop with natural selection")
    parser.add_argument("--start-month", default="202501")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--initial-balance", type=float, default=3000)
    parser.add_argument("--risk-percent", type=float, default=1.0)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--main-db", action="store_true", help="Allow simulator/registry updates to main DB")
    parser.add_argument("--natural-selection", action="store_true")
    parser.add_argument("--sandbox-brain", default="brain_versions/sandbox_brain_current.json")
    parser.add_argument("--skip-research", action="store_true", help="Only run simulations and update PNL statuses")
    args = parser.parse_args()

    os.chdir(ROOT)
    os.makedirs("brain_versions/pnl_learning_reports", exist_ok=True)

    main_db = db_path()
    db_backup = backup_main_db(main_db) if args.main_db else None
    if db_backup:
        print(f"[BACKUP] Main DB: {db_backup}")

    conn = sqlite3.connect(main_db)
    ensure_registry(conn)

    months = month_range(args.start_month, args.end_month)
    loop_report = {
        "started_at": utc_now(),
        "start_month": args.start_month,
        "end_month": args.end_month,
        "cycles": [],
        "db_backup": db_backup,
    }

    for cycle in range(1, args.cycles + 1):
        print(f"\n=== PNL LOOP CYCLE {cycle}/{args.cycles} ===")
        aggregate = {}
        monthly_pattern_pnl = {}
        cycle_reports = []

        for month in months:
            cmd = [
                sys.executable, "src/run_simulator.py",
                "--month", month,
                "--keep-ghost",
                "--replace-month",
                "--initial-balance", str(args.initial_balance),
                "--risk-percent", str(args.risk_percent),
                "--fast",
                "--progress-every", "10000",
            ]
            if os.path.exists(args.sandbox_brain):
                cmd += ["--sandbox-brain", args.sandbox_brain]

            run_cmd(cmd)
            report = read_report()
            merge_pattern_stats(report, aggregate, monthly_pattern_pnl)
            cycle_reports.append(
                {
                    "month": month,
                    "ending_balance": report.get("ending_balance"),
                    "net_pl": report.get("net_pl"),
                    "profit_factor": report.get("profit_factor"),
                    "max_dd_pct": report.get("max_dd_pct"),
                    "total_trades": report.get("total_trades"),
                }
            )
            conn.execute(
                "INSERT INTO pnl_learning_runs (created_at, cycle, month, report_json) VALUES (?, ?, ?, ?)",
                (utc_now(), cycle, month, json.dumps(report)),
            )
            conn.commit()

        changes = update_method_registry(conn, aggregate, monthly_pattern_pnl) if args.natural_selection else []

        if not args.skip_research:
            run_cmd([sys.executable, "src/ghost_trade_research.py", "--sim-type", "MAIN"])
            candidate = latest_candidate_file()
            run_cmd([sys.executable, "src/candidate_method_tester.py"])
            if candidate:
                run_cmd([sys.executable, "src/sandbox_candidate_helper.py", "--candidate", candidate, "--sandbox", args.sandbox_brain])

        best_method = max(aggregate.items(), key=lambda item: item[1].get("net_pl", 0), default=(None, {}))
        worst_dd = max(aggregate.items(), key=lambda item: item[1].get("max_dd_pct", 0), default=(None, {}))
        cycle_summary = {
            "cycle": cycle,
            "months": cycle_reports,
            "best_method_by_pnl": {"method": best_method[0], **best_method[1]} if best_method[0] else None,
            "worst_method_by_drawdown": {"method": worst_dd[0], **worst_dd[1]} if worst_dd[0] else None,
            "status_changes": changes,
        }
        loop_report["cycles"].append(cycle_summary)

        print(f"Best by PNL: {cycle_summary['best_method_by_pnl']}")
        print(f"Status changes: {len(changes)}")

    out = f"brain_versions/pnl_learning_reports/pnl_loop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w") as f:
        json.dump(loop_report, f, indent=2)
    conn.close()

    print(f"\n[OK] PNL learning report: {out}")
    print("Lihat status metode:")
    print("sqlite3 data/xauusd_bot.sqlite \"SELECT method_name,status,confidence,trades,net_pl,profit_factor,max_dd_pct FROM method_registry ORDER BY net_pl DESC LIMIT 20;\"")


if __name__ == "__main__":
    main()
