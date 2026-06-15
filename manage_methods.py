import argparse
from src.method_registry import (
    DISABLED,
    EXPERIMENTAL,
    LIVE_MAIN,
    WATCHLIST,
    build_registry,
    get_main_methods,
    load_config,
    save_registry,
    sync_registry,
    update_method_status,
)


def print_methods(title, rows):
    print(f"\n{title}")
    print("=" * len(title))
    if not rows:
        print("(kosong)")
        return
    for name, data in rows:
        print(f"- {name} [{data.get('status')}]")


def main():
    parser = argparse.ArgumentParser(description="Manage metode live/backtest bot XAUUSD")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("sync", help="Scan kode dan update config/method_registry.json")
    sub.add_parser("list", help="Lihat semua metode")
    sub.add_parser("whitelist", help="Lihat metode LIVE_MAIN / whitelist")
    sub.add_parser("experimental", help="Lihat metode experimental")
    sub.add_parser("watchlist", help="Lihat metode watchlist")
    sub.add_parser("disabled", help="Lihat metode disabled")

    add = sub.add_parser("add", help="Tambah metode ke whitelist LIVE_MAIN")
    add.add_argument("method")

    remove = sub.add_parser("remove", help="Hapus metode dari whitelist, pindah ke WATCHLIST")
    remove.add_argument("method")

    promote = sub.add_parser("promote", help="Promote metode ke LIVE_MAIN")
    promote.add_argument("method")

    demote = sub.add_parser("demote", help="Turunkan metode ke WATCHLIST")
    demote.add_argument("method")

    exp = sub.add_parser("experiment", help="Pindahkan metode ke EXPERIMENTAL")
    exp.add_argument("method")

    disable = sub.add_parser("disable", help="Disable metode")
    disable.add_argument("method")

    enable = sub.add_parser("enable", help="Enable metode ke WATCHLIST")
    enable.add_argument("method")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    if args.cmd == "sync":
        registry = sync_registry()
        print(f"✅ Registry disinkronkan. Total metode: {len(registry)}")
        return

    if args.cmd in {"add", "promote"}:
        update_method_status(args.method, LIVE_MAIN)
        print(f"✅ {args.method} masuk whitelist LIVE_MAIN")
        return
    if args.cmd in {"remove", "demote"}:
        update_method_status(args.method, WATCHLIST)
        print(f"✅ {args.method} keluar whitelist, pindah WATCHLIST")
        return
    if args.cmd == "experiment":
        update_method_status(args.method, EXPERIMENTAL)
        print(f"✅ {args.method} pindah EXPERIMENTAL")
        return
    if args.cmd == "disable":
        update_method_status(args.method, DISABLED)
        print(f"✅ {args.method} DISABLED")
        return
    if args.cmd == "enable":
        update_method_status(args.method, WATCHLIST)
        print(f"✅ {args.method} aktif sebagai WATCHLIST")
        return

    registry = build_registry(load_config())
    save_registry(registry)

    if args.cmd == "list":
        print_methods("SEMUA METODE", sorted(registry.items()))
    elif args.cmd == "whitelist":
        live = set(get_main_methods())
        rows = [(m, d) for m, d in sorted(registry.items()) if d.get("status") == LIVE_MAIN or m in live]
        print_methods("WHITELIST / LIVE_MAIN", rows)
    elif args.cmd == "experimental":
        print_methods("EXPERIMENTAL", [(m, d) for m, d in sorted(registry.items()) if d.get("status") == EXPERIMENTAL])
    elif args.cmd == "watchlist":
        print_methods("WATCHLIST", [(m, d) for m, d in sorted(registry.items()) if d.get("status") == WATCHLIST])
    elif args.cmd == "disabled":
        print_methods("DISABLED", [(m, d) for m, d in sorted(registry.items()) if d.get("status") == DISABLED])


if __name__ == "__main__":
    main()
