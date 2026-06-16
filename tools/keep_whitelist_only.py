import json
from pathlib import Path

KEEP = {
    "METHOD_M5_BREAK_6_SELL": "METHOD_M5_BREAK_6",
    "METHOD_M5_BREAK_8_SELL": "METHOD_M5_BREAK_8",
    "METHOD_CRT_H4_SWEEP_BUY": "METHOD_CRT_H4_SWEEP",
    "METHOD_M5_BREAK_12_SELL": "METHOD_M5_BREAK_12",
    "METHOD_M5_BREAK_12_BUY": "METHOD_M5_BREAK_12",
    "METHOD_CRT_H4_SWEEP_SELL": "METHOD_CRT_H4_SWEEP",
    "METHOD_M5_BREAK_8_BUY": "METHOD_M5_BREAK_8",
    "METHOD_CRT_D1_SWEEP_SELL": "METHOD_CRT_D1_SWEEP",
    "METHOD_M5_BREAK_6_BUY": "METHOD_M5_BREAK_6",
    "METHOD_SESSION_OPEN_BREAKOUT_SELL": "METHOD_SESSION_OPEN_BREAKOUT",
    "METHOD_HIGH_WR_M15_SWEEP_SCALP_SELL": "METHOD_HIGH_WR_M15_SWEEP_SCALP",
}

path = Path("config/method_registry.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["description"] = "Method status registry. Only whitelist/LIVE_MAIN methods are kept."
payload["methods"] = {
    name: {"status": "LIVE_MAIN", "base": base, "notes": ""}
    for name, base in KEEP.items()
}
path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print("OK: registry now contains", len(KEEP), "LIVE_MAIN methods")
for name in KEEP:
    print("-", name)
