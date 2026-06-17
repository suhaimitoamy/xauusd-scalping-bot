#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path.cwd()

NEW_MSG = "🤖 BOT AKTIF\\n\\nSistem sudah online.\\nSilakan kirim pertanyaan di kolom komentar."

TARGET_EXTS = {".py", ".txt", ".md"}
SKIP_PARTS = {".git", "__pycache__", "venv", ".venv", "node_modules"}

changed = []

def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)

for path in ROOT.rglob("*"):
    if should_skip(path) or not path.is_file() or path.suffix not in TARGET_EXTS:
        continue

    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue

    original = text

    # Telegram startup message compact / multi-line.
    text = re.sub(
        r"🧠\s*BOT AKTIF ONLINE.*?Source:\s*LOCAL BRAIN\s*\+\s*AI TRAINER",
        NEW_MSG,
        text,
        flags=re.DOTALL,
    )

    # If message is assembled in fragments, replace known lines.
    if "BOT AKTIF ONLINE" in text:
        text = text.replace("🤖 BOT AKTIF", "🤖 BOT AKTIF")
        text = re.sub(r"M1\s*\+\s*M5 signals independent\\?n?", "", text)
        text = re.sub(r"\"]*\}?.*?\\n", "", text)
        text = re.sub(r"News filter:\s*OFF\\?n?", "", text)
        text = re.sub(r"Source:\s*LOCAL BRAIN\s*\+\s*AI TRAINER", "Sistem sudah online.\\nSilakan kirim pertanyaan di kolom komentar.", text)

    # Console header still may use the same old label without ONLINE.
    if "BOT AKTIF" in text and "Commands:" in text:
        text = text.replace("BOT AKTIF", "BOT AKTIF")

    if text != original:
        path.write_text(text, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))

if changed:
    print("✅ File diubah:")
    for item in changed:
        print("-", item)
else:
    print("⚠️ Tidak ada file yang cocok. Jalankan grep:")
    print('grep -R "BOT AKTIF" -n .')
    print('grep -R "LOCAL BRAIN + AI TRAINER" -n .')

print("✅ Patch startup message selesai")
