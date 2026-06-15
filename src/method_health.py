from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

WIN_RESULTS = {"WIN", "FULL_WIN", "PARTIAL_WIN", "PROTECTED", "TP1_HIT", "TP2_HIT"}
LOSS_RESULTS = {"LOSS"}


def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def load_method_months(db_path: str, method: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT run_month, pattern_key, total_trades, wins, losses, win_rate
        FROM backtest_method_summary
        WHERE pattern_key = ?
        ORDER BY run_month ASC
        """,
        (method,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def method_health_from_months(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = sum(int(r.get("total_trades") or 0) for r in rows)
    wins = sum(int(r.get("wins") or 0) for r in rows)
    losses = sum(int(r.get("losses") or 0) for r in rows)
    wr = _safe_div(wins, total) * 100.0

    active_months = [r for r in rows if int(r.get("total_trades") or 0) > 0]
    good_months = [r for r in active_months if float(r.get("win_rate") or 0) >= 60.0]
    bad_months = [r for r in active_months if float(r.get("win_rate") or 0) < 50.0]
    consistency = _safe_div(len(good_months), len(active_months)) * 100.0
    bad_ratio = _safe_div(len(bad_months), len(active_months)) * 100.0

    sample_score = min(100.0, total / 50.0 * 100.0)
    wr_score = max(0.0, min(100.0, wr))
    consistency_score = max(0.0, min(100.0, consistency))
    loss_penalty = min(30.0, bad_ratio * 0.30)

    score = (wr_score * 0.50) + (sample_score * 0.20) + (consistency_score * 0.30) - loss_penalty
    score = max(0.0, min(100.0, score))

    if total < 10:
        verdict = "BELUM_CUKUP_DATA"
    elif score >= 75 and wr >= 65:
        verdict = "LAYAK_PROMOTE"
    elif score >= 60 and wr >= 55:
        verdict = "WATCHLIST"
    elif losses >= 20 or (total >= 20 and wr < 45):
        verdict = "LAYAK_DEMOTE"
    else:
        verdict = "PERLU_PANTAU"

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wr, 2),
        "active_months": len(active_months),
        "good_months": len(good_months),
        "bad_months": len(bad_months),
        "consistency": round(consistency, 2),
        "score": round(score, 2),
        "verdict": verdict,
    }


def method_health(db_path: str, method: str) -> Dict[str, Any]:
    return method_health_from_months(load_method_months(db_path, method))


def all_method_health(db_path: str) -> Dict[str, Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT pattern_key FROM backtest_method_summary ORDER BY pattern_key")
        methods = [r[0] for r in cur.fetchall()]
    except Exception:
        methods = []
    conn.close()
    return {m: method_health(db_path, m) for m in methods}
