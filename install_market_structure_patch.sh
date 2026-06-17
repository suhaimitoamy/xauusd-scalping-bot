#!/data/data/com.termux/files/usr/bin/bash
set -e

PROJECT_DIR="${1:-$PWD}"

cd "$PROJECT_DIR"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan script ini dari folder repo bot kamu."
  echo "Contoh:"
  echo "cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot"
  echo "bash install_market_structure_patch.sh"
  exit 1
fi

if [ ! -d "src" ]; then
  echo "❌ Folder src tidak ditemukan."
  exit 1
fi

BACKUP="src/market_structure.py.backup.$(date +%Y%m%d_%H%M%S)"

if [ -f "src/market_structure.py" ]; then
  cp src/market_structure.py "$BACKUP"
  echo "✅ Backup dibuat: $BACKUP"
fi

cp market_structure.py src/market_structure.py

python -m py_compile src/market_structure.py

git add src/market_structure.py
git commit -m "upgrade market structure validation and invalidation alerts" || true

echo ""
echo "✅ Patch selesai."
echo "✅ Market structure sekarang membaca:"
echo "- BOS valid / invalid"
echo "- MSS / CHOCH valid / invalid"
echo "- Support break valid / invalid"
echo "- Resistance break valid / invalid"
echo "- Sweep reclaim valid / invalid"
echo "- Invalidasi bullish di Higher Low"
echo "- Invalidasi bearish di Lower High"
echo "- Telegram alert market structure"
echo ""
echo "Push manual:"
echo "git push origin main"
