#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "${1:-$PWD}"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan dari folder repo bot."
  exit 1
fi

if [ ! -f "src/market_structure.py" ]; then
  echo "❌ src/market_structure.py tidak ditemukan."
  exit 1
fi

cp src/market_structure.py "src/market_structure.py.backup.$(date +%Y%m%d_%H%M%S)"
cp market_structure.py src/market_structure.py

python -m py_compile src/market_structure.py

git add src/market_structure.py
git commit -m "add early warning market structure alerts" || true

echo ""
echo "✅ Early warning selesai."
echo "Yang ditambahkan:"
echo "- EARLY support sweep"
echo "- EARLY resistance sweep"
echo "- EARLY BOS bullish/bearish"
echo "- EARLY CHOCH/MSS bullish/bearish"
echo "- EARLY trend invalidation"
echo "- Confirmed VALID/INVALID tetap jalan"
echo ""
echo "ENV:"
echo "EARLY_STRUCTURE_TELEGRAM_ALERTS=false  # matikan early warning"
echo "EARLY_STRUCTURE_ALERT_COOLDOWN_SECONDS=180"
echo ""
echo "Push:"
echo "git push origin main"
