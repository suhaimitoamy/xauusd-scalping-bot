#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path.cwd()
config_path = ROOT / "config.yaml"

if not config_path.exists():
    raise SystemExit("config.yaml tidak ditemukan")

config = config_path.read_text(encoding="utf-8")

replacements = [
    (r"(^ai:\n(?:[ \t].*\n)*?[ \t]enabled:\s*)true", r"\g<1>false"),
    (r"(^[ \t]provider:\s*)deepseek", r"\g<1>local_bot"),
    (r"(^[ \t]allow_ai_for_sweep_break_important:\s*)true", r"\g<1>false"),
    (r"(^[ \t]allow_ai_for_poi_report:\s*)true", r"\g<1>false"),
    (r"(^[ \t]allow_ai_for_premium_signal:\s*)true", r"\g<1>false"),
    (r"(^[ \t]use_ai:\s*)true", r"\g<1>false"),
    (r"(^[ \t]ai_hourly_review:\n(?:[ \t].*\n)*?[ \t]enabled:\s*)true", r"\g<1>false"),
]

new_config = config
for pattern, repl in replacements:
    new_config = re.sub(pattern, repl, new_config, flags=re.MULTILINE)

# fallback precise section edits
new_config = new_config.replace("ai:\n  enabled: true", "ai:\n  enabled: false")
new_config = new_config.replace("  provider: deepseek", "  provider: local_bot")
new_config = new_config.replace("  allow_ai_for_sweep_break_important: true", "  allow_ai_for_sweep_break_important: false")
new_config = new_config.replace("  allow_ai_for_poi_report: true", "  allow_ai_for_poi_report: false")
new_config = new_config.replace("  allow_ai_for_premium_signal: true", "  allow_ai_for_premium_signal: false")
new_config = new_config.replace("  use_ai: true", "  use_ai: false")

config_path.write_text(new_config, encoding="utf-8")
print("✅ AI dinonaktifkan di config.yaml")

# create local bot education module
src_dir = ROOT / "src"
src_dir.mkdir(exist_ok=True)
(Path(__file__).parent / "local_bot_education.py").replace(src_dir / "local_bot_education.py")
print("✅ src/local_bot_education.py dipasang")

# optional auto patch for Telegram handler files
targets = []
for p in ROOT.rglob("*.py"):
    if ".git" in p.parts:
        continue
    if p.name in {"local_bot_education.py"}:
        continue
    try:
        txt = p.read_text(encoding="utf-8")
    except Exception:
        continue
    lowered = txt.lower()
    if (
        "dijawab oleh ai" in lowered
        or "ai + bot data" in lowered
        or "deepseek" in lowered and "telegram" in lowered
        or "edukasi" in lowered and "telegram" in lowered
    ):
        targets.append(p)

for p in targets:
    txt = p.read_text(encoding="utf-8")
    backup = p.with_suffix(p.suffix + ".backup_localbot")
    if not backup.exists():
        backup.write_text(txt, encoding="utf-8")

    # disable obvious AI labels
    txt = txt.replace("🤖 Dijawab oleh Bot Lokal", "🤖 Dijawab oleh Bot Lokal")
    txt = txt.replace("Source: BOT DATA ONLY", "Source: BOT DATA ONLY")
    txt = txt.replace("Dijawab oleh Bot Lokal", "Dijawab oleh Bot Lokal")
    txt = txt.replace("BOT DATA ONLY", "BOT DATA ONLY")

    p.write_text(txt, encoding="utf-8")
    print(f"✅ label AI diganti di {p}")

print("✅ Patch selesai")
