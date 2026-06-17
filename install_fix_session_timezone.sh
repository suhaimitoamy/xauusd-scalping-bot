#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "${1:-$PWD}"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan dari folder repo bot."
  exit 1
fi

cp src/session_context.py "src/session_context.py.backup.$(date +%Y%m%d_%H%M%S)"
cp fix_session_context.py src/session_context.py

python -m py_compile src/session_context.py
python scripts/send_mapping_summary.py

git add src/session_context.py
git commit -m "fix session timezone fallback for Termux" || true

echo ""
echo "✅ Fix timezone selesai."
echo "Push:"
echo "git push origin main"
