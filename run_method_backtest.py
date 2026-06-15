import os
import subprocess
import sys

if len(sys.argv) < 3:
    print("Cara penggunaan:")
    print("  python3 run_method_backtest.py METHOD_NAME YYYY-MM")
    print("Contoh:")
    print("  python3 run_method_backtest.py METHOD_CRT_H4_SWEEP_SELL 2022-05")
    sys.exit(1)

method = sys.argv[1].strip().upper()
month = sys.argv[2].strip()

env = os.environ.copy()
env["FAIR_TEST"] = "true"
env["FAIR_TEST_METHOD"] = method
env["METHOD_UNDER_TEST"] = method
env["BACKTEST_ALL_METHODS"] = "true"
env["DRY_RUN"] = "true"

print(f"\n🧪 FAIR TEST METHOD: {method}")
print(f"📅 MONTH: {month}\n")

result = subprocess.run([sys.executable, "run_bulan.py", month], env=env)
sys.exit(result.returncode)
