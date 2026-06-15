import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
BRAIN_PATH = ROOT / "src" / "market_brain.py"
SNAPSHOT_DIR = ROOT / "snapshots"
DB_PATH = ROOT / "data" / "backtest_results.sqlite"


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def ensure_db_schema(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS config_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            snapshot_key TEXT UNIQUE,
            mode TEXT,
            run_month TEXT,
            git_commit TEXT,
            config_sha256 TEXT,
            brain_sha256 TEXT,
            snapshot_path TEXT,
            notes TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def create_snapshot(run_month="", mode="manual", notes="", db_path=DB_PATH):
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    safe_month = run_month or "manual"
    snapshot_key = f"{safe_month}_{mode}_{created_at.replace(':', '').replace('+', 'Z')}"
    path = SNAPSHOT_DIR / f"{snapshot_key}.json"

    config_text = CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else ""
    payload = {
        "created_at": created_at,
        "snapshot_key": snapshot_key,
        "mode": mode,
        "run_month": run_month,
        "git_commit": git_commit(),
        "config_sha256": sha256_file(CONFIG_PATH),
        "brain_sha256": sha256_file(BRAIN_PATH),
        "config_yaml": config_text,
        "notes": notes,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    ensure_db_schema(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO config_snapshots
        (created_at, snapshot_key, mode, run_month, git_commit, config_sha256, brain_sha256, snapshot_path, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            created_at,
            snapshot_key,
            mode,
            run_month,
            payload["git_commit"],
            payload["config_sha256"],
            payload["brain_sha256"],
            str(path.relative_to(ROOT)),
            notes,
        ),
    )
    conn.commit()
    conn.close()
    print(f"✅ Snapshot dibuat: {path.relative_to(ROOT)}")
    return str(path)


def main():
    parser = argparse.ArgumentParser(description="Create config/code snapshot")
    parser.add_argument("--run-month", default="")
    parser.add_argument("--mode", default="manual")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    create_snapshot(args.run_month, args.mode, args.notes)


if __name__ == "__main__":
    main()
