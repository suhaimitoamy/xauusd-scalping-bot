import sqlite3
import sys

DB_PATH = "data/backtest_results.sqlite"


def print_table(headers, rows):
    if not rows:
        print("(kosong)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(str(value)))
    fmt = " | ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*[str(v) for v in row]))


def main():
    month = sys.argv[1] if len(sys.argv) > 1 else None
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if month:
        print(f"\n📅 BACKTEST MONTH: {month}\n")
        cur.execute("""
            SELECT pattern_key, total_trades, wins, losses, printf('%.2f%%', win_rate)
            FROM backtest_method_summary
            WHERE run_month = ?
            ORDER BY total_trades DESC, win_rate DESC
        """, (month,))
        print_table(["Method", "Total", "WIN", "LOSS", "WR"], cur.fetchall())
    else:
        print("\n📊 MONTHLY SUMMARY\n")
        cur.execute("""
            SELECT run_month, total_signals, closed_trades, wins, losses, printf('%.2f%%', win_rate)
            FROM backtest_runs
            ORDER BY run_month ASC
        """)
        print_table(["Month", "Signal", "Closed", "WIN", "LOSS", "WR"], cur.fetchall())

        print("\n🧠 METHOD SUMMARY - ALL MONTHS\n")
        cur.execute("""
            SELECT pattern_key,
                   SUM(total_trades),
                   SUM(wins),
                   SUM(losses),
                   printf('%.2f%%', CASE WHEN SUM(total_trades) > 0 THEN 100.0 * SUM(wins) / SUM(total_trades) ELSE 0 END)
            FROM backtest_method_summary
            GROUP BY pattern_key
            ORDER BY SUM(total_trades) DESC
        """)
        print_table(["Method", "Total", "WIN", "LOSS", "WR"], cur.fetchall())

    conn.close()


if __name__ == "__main__":
    main()
