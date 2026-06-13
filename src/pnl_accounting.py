import json
from collections import defaultdict
from datetime import datetime, timezone


CLOSED_RESULTS = {"LOSS", "PARTIAL_WIN", "WIN", "FULL_WIN"}

RESULT_R = {
    "LOSS": -1.0,
    "PARTIAL_WIN": 0.5,
    "WIN": 2.0,
    "FULL_WIN": 3.0,
}


def _loads_json(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _raw_meta(raw):
    meta = dict(raw)
    nested = _loads_json(raw.get("raw_context_json"))
    for key in ("simulation_id", "dataset_key", "sim_type", "pattern_key"):
        if key not in meta and key in nested:
            meta[key] = nested.get(key)
    return meta


def signal_belongs_to_run(raw_json, sim_id=None, dataset_keys=None, sim_type=None):
    meta = _raw_meta(_loads_json(raw_json))
    if sim_id:
        return meta.get("simulation_id") == sim_id

    if dataset_keys:
        if meta.get("dataset_key") not in set(dataset_keys):
            return False
        if sim_type and meta.get("sim_type", "MAIN") != sim_type:
            return False
        return True

    return False


def normalize_trade_result(signal_result, signal_status, event_types):
    result = (signal_result or "").upper()
    status = (signal_status or "").upper()
    events = [str(e or "").upper() for e in event_types]
    event_set = set(events)

    if result in CLOSED_RESULTS:
        if result == "LOSS" and {"TP1_HIT", "PROTECTED"} & event_set:
            return "PARTIAL_WIN"
        return result

    if "TP3_HIT" in event_set:
        return "FULL_WIN"
    if "TP2_HIT" in event_set:
        return "WIN"
    if "PROTECTED" in event_set or "TP1_HIT" in event_set or "PARTIAL" in status:
        return "PARTIAL_WIN"
    if "SL_HIT" in event_set or "LOSS" in status:
        return "LOSS"
    return None


def fetch_closed_trades(conn, sim_id=None, dataset_keys=None, sim_type=None):
    conn.row_factory = __import__("sqlite3").Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            s.id, s.direction, s.status, s.result, s.result_time, s.reason,
            s.raw_context_json,
            GROUP_CONCAT(e.event_type, ',') AS events
        FROM signals s
        LEFT JOIN signal_events e ON e.signal_id = s.id
        GROUP BY s.id
        ORDER BY s.id ASC
        """
    )

    trades = []
    for row in cur.fetchall():
        if not signal_belongs_to_run(row["raw_context_json"], sim_id, dataset_keys, sim_type):
            continue

        raw = _loads_json(row["raw_context_json"])
        meta = _raw_meta(raw)
        event_types = [e for e in (row["events"] or "").split(",") if e]
        result = normalize_trade_result(row["result"], row["status"], event_types)
        if result not in CLOSED_RESULTS:
            continue

        trades.append(
            {
                "signal_id": row["id"],
                "direction": row["direction"],
                "status": row["status"],
                "result": result,
                "stored_result": row["result"],
                "result_time": row["result_time"],
                "reason": row["reason"] or "",
                "pattern_key": meta.get("pattern_key") or raw.get("pattern_key") or "UNKNOWN",
                "dataset_key": meta.get("dataset_key"),
                "sim_type": meta.get("sim_type", "MAIN"),
                "events": event_types,
            }
        )
    return trades


def calculate_virtual_balance_report(
    conn,
    initial_balance,
    risk_percent,
    sim_id=None,
    dataset_keys=None,
    sim_type=None,
):
    trades = fetch_closed_trades(conn, sim_id=sim_id, dataset_keys=dataset_keys, sim_type=sim_type)
    initial_balance = float(initial_balance or 0)
    risk_pct = float(risk_percent or 0) / 100.0
    balance = initial_balance
    peak_balance = initial_balance
    max_dd_pct = 0.0
    max_dd_amount = 0.0

    gross_profit = 0.0
    gross_loss = 0.0
    win_amounts = []
    loss_amounts = []
    equity_curve = []
    monthly = defaultdict(lambda: {"trades": 0, "wins": 0, "losses": 0, "net_pl": 0.0})
    by_pattern = defaultdict(
        lambda: {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "net_pl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
        }
    )

    win_streak = 0
    loss_streak = 0
    max_win_streak = 0
    max_loss_streak = 0

    for trade in trades:
        result = trade["result"]
        r_mult = RESULT_R[result]
        risk_amount = balance * risk_pct
        pnl = risk_amount * r_mult
        balance += pnl

        if pnl >= 0:
            gross_profit += pnl
            win_amounts.append(pnl)
            win_streak += 1
            loss_streak = 0
        else:
            loss_abs = abs(pnl)
            gross_loss += loss_abs
            loss_amounts.append(loss_abs)
            loss_streak += 1
            win_streak = 0

        max_win_streak = max(max_win_streak, win_streak)
        max_loss_streak = max(max_loss_streak, loss_streak)
        peak_balance = max(peak_balance, balance)
        dd_amount = peak_balance - balance
        dd_pct = (dd_amount / peak_balance * 100.0) if peak_balance else 0.0
        max_dd_amount = max(max_dd_amount, dd_amount)
        max_dd_pct = max(max_dd_pct, dd_pct)

        month = trade.get("dataset_key") or "UNKNOWN"
        monthly[month]["trades"] += 1
        monthly[month]["net_pl"] += pnl
        pattern = trade.get("pattern_key") or "UNKNOWN"
        by_pattern[pattern]["trades"] += 1
        by_pattern[pattern]["net_pl"] += pnl
        if pnl >= 0:
            by_pattern[pattern]["gross_profit"] += pnl
        else:
            by_pattern[pattern]["gross_loss"] += abs(pnl)

        if result == "LOSS":
            monthly[month]["losses"] += 1
            by_pattern[pattern]["losses"] += 1
        else:
            monthly[month]["wins"] += 1
            by_pattern[pattern]["wins"] += 1

        equity_curve.append(
            {
                "signal_id": trade["signal_id"],
                "result": result,
                "r_multiple": r_mult,
                "pnl": round(pnl, 2),
                "balance": round(balance, 2),
                "drawdown_pct": round(dd_pct, 4),
                "pattern_key": pattern,
                "dataset_key": month,
            }
        )

    wins = sum(1 for t in trades if t["result"] != "LOSS")
    losses = sum(1 for t in trades if t["result"] == "LOSS")
    partial_wins = sum(1 for t in trades if t["result"] == "PARTIAL_WIN")
    full_wins = sum(1 for t in trades if t["result"] == "FULL_WIN")
    normal_wins = sum(1 for t in trades if t["result"] == "WIN")
    total_trades = len(trades)
    net_pl = balance - initial_balance

    patterns = {}
    for pattern, stats in sorted(by_pattern.items()):
        gross_loss_pattern = float(stats.get("gross_loss") or 0)
        gross_profit_pattern = float(stats.get("gross_profit") or 0)
        patterns[pattern] = {
            "trades": int(stats.get("trades") or 0),
            "wins": int(stats.get("wins") or 0),
            "losses": int(stats.get("losses") or 0),
            "net_pl": round(float(stats.get("net_pl") or 0), 2),
            "gross_profit": round(gross_profit_pattern, 2),
            "gross_loss": round(gross_loss_pattern, 2),
            "profit_factor": round(
                (gross_profit_pattern / gross_loss_pattern)
                if gross_loss_pattern
                else (999.0 if gross_profit_pattern else 0.0),
                4,
            ),
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "simulation_id": sim_id,
        "dataset_keys": sorted(set(dataset_keys or [])),
        "sim_type": sim_type,
        "initial_balance": round(initial_balance, 2),
        "ending_balance": round(balance, 2),
        "net_pl": round(net_pl, 2),
        "net_pl_pct": round((net_pl / initial_balance * 100.0) if initial_balance else 0.0, 4),
        "risk_percent": round(float(risk_percent or 0), 4),
        "risk_model": {
            "loss_r": RESULT_R["LOSS"],
            "partial_win_r": RESULT_R["PARTIAL_WIN"],
            "win_r": RESULT_R["WIN"],
            "full_win_r": RESULT_R["FULL_WIN"],
            "compounding": True,
        },
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "tp2_wins": normal_wins,
        "partial_wins": partial_wins,
        "full_wins": full_wins,
        "winrate": round((wins / total_trades * 100.0) if total_trades else 0.0, 4),
        "profit_factor": round((gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit else 0.0), 4),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "average_win": round((sum(win_amounts) / len(win_amounts)) if win_amounts else 0.0, 2),
        "average_loss": round((sum(loss_amounts) / len(loss_amounts)) if loss_amounts else 0.0, 2),
        "max_drawdown": round(max_dd_amount, 2),
        "max_dd_pct": round(max_dd_pct, 4),
        "largest_win_streak": max_win_streak,
        "largest_loss_streak": max_loss_streak,
        "monthly": dict(sorted(monthly.items())),
        "patterns": patterns,
        "equity_curve": equity_curve,
    }
    return report
