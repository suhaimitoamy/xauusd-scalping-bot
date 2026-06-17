#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "${1:-$PWD}"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan dari folder repo bot."
  exit 1
fi

if [ ! -f "config.yaml" ]; then
  echo "❌ config.yaml tidak ditemukan."
  exit 1
fi

if [ ! -f "src/market_brain.py" ]; then
  echo "❌ src/market_brain.py tidak ditemukan."
  exit 1
fi

cp config.yaml "config.yaml.backup.$(date +%Y%m%d_%H%M%S)"
cp src/market_brain.py "src/market_brain.py.backup.$(date +%Y%m%d_%H%M%S)"

python patch_signal_limit_and_choch_sl.py
python -m py_compile src/market_brain.py

git add config.yaml src/market_brain.py
git commit -m "remove daily signal cap and widen choch sell sl" || true

echo ""
echo "✅ Selesai."
echo "Yang diubah:"
echo "- max_signals_per_day: 999"
echo "- SL khusus METHOD_CHOCH_REVERSAL_SELL saja"
echo ""
echo "Push:"
echo "git push origin main"
