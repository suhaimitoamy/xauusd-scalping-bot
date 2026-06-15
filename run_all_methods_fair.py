import os
import subprocess
import sys

from src.method_registry import build_registry, load_config, save_registry

if len(sys.argv) < 2:
    print("Cara penggunaan:")
    print("  python3 run_all_methods_fair.py YYYY-MM")
    print("Contoh:")
    print("  python3 run_all_methods_fair.py 2022-05")
    sys.exit(1)

month = sys.argv[1].strip()
registry = build_registry(load_config())
save_registry(registry)
methods = [m for m, d in sorted(registry.items()) if d.get("status") != "DISABLED"]

print(f"Total metode yang akan di-fair-test: {len(methods)}")
failed = []
for i, method in enumerate(methods, start=1):
    print("\n" + "=" * 70)
    print(f"[{i}/{len(methods)}] FAIR TEST: {method} | {month}")
    print("=" * 70)
    env = os.environ.copy()
    env["FAIR_TEST"] = "true"
    env["FAIR_TEST_METHOD"] = method
    env["METHOD_UNDER_TEST"] = method
    env["BACKTEST_ALL_METHODS"] = "true"
    env["DRY_RUN"] = "true"
    result = subprocess.run([sys.executable, "run_bulan.py", month], env=env)
    if result.returncode != 0:
        failed.append(method)

print("\n" + "=" * 70)
print("FAIR TEST SELESAI")
print(f"Total metode: {len(methods)}")
print(f"Failed: {len(failed)}")
if failed:
    for method in failed:
        print(f"- {method}")
print("=" * 70)
