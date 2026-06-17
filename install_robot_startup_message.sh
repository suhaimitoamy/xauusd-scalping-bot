#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "${1:-$PWD}"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan dari folder repo bot."
  exit 1
fi

python patch_robot_startup_message.py

python - <<'PY'
from pathlib import Path
import py_compile

for p in Path("src").rglob("*.py"):
    if "__pycache__" in p.parts:
        continue
    py_compile.compile(str(p), doraise=True)
print("✅ Python compile OK")
PY

git add .
git commit -m "update startup message to robot style" || true

echo ""
echo "✅ Selesai."
echo "Push:"
echo "git push origin main"
