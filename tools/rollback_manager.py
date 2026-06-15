import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "snapshots"
CONFIG_PATH = ROOT / "config.yaml"


def list_snapshots():
    if not SNAPSHOT_DIR.exists():
        return []
    rows = []
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows.append((path.name, data))
        except Exception:
            pass
    return rows


def restore(snapshot_name: str):
    path = SNAPSHOT_DIR / snapshot_name
    if not path.exists():
        matches = list(SNAPSHOT_DIR.glob(f"*{snapshot_name}*.json"))
        if not matches:
            raise FileNotFoundError(f"Snapshot tidak ditemukan: {snapshot_name}")
        path = matches[-1]
    data = json.loads(path.read_text(encoding="utf-8"))
    config_yaml = data.get("config_yaml")
    if not config_yaml:
        raise ValueError("Snapshot tidak punya config_yaml")
    backup = CONFIG_PATH.with_suffix(".yaml.before_rollback")
    if CONFIG_PATH.exists():
        backup.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    CONFIG_PATH.write_text(config_yaml, encoding="utf-8")
    print(f"✅ Rollback config selesai dari {path.name}")
    print(f"Backup config sebelum rollback: {backup.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description="Rollback config from snapshots")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("list")
    r = sub.add_parser("restore")
    r.add_argument("snapshot")
    args = parser.parse_args()

    if args.cmd == "list":
        rows = list_snapshots()
        if not rows:
            print("Belum ada snapshot.")
            return
        for name, data in rows:
            print(f"- {name} | {data.get('run_month')} | {data.get('mode')} | {data.get('created_at')}")
        return
    if args.cmd == "restore":
        restore(args.snapshot)
        return
    parser.print_help()


if __name__ == "__main__":
    main()
