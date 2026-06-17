#!/data/data/com.termux/files/usr/bin/bash
set -e

PROJECT_DIR="${1:-$PWD}"
cd "$PROJECT_DIR"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan dari folder repo bot."
  echo "Contoh:"
  echo "cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot"
  echo "bash install_mapping_assistant_upgrade.sh"
  exit 1
fi

mkdir -p src scripts

cp src/session_context.py src/session_context.py 2>/dev/null || true
cp src/htf_bias_engine.py src/htf_bias_engine.py 2>/dev/null || true
cp src/range_map.py src/range_map.py 2>/dev/null || true
cp src/liquidity_map.py src/liquidity_map.py 2>/dev/null || true
cp src/order_block_engine.py src/order_block_engine.py 2>/dev/null || true
cp src/fvg_mapping.py src/fvg_mapping.py 2>/dev/null || true
cp src/market_narrative.py src/market_narrative.py 2>/dev/null || true
cp src/mapping_assistant.py src/mapping_assistant.py 2>/dev/null || true
cp scripts/send_mapping_summary.py scripts/send_mapping_summary.py 2>/dev/null || true

chmod +x scripts/send_mapping_summary.py

python -m py_compile \
  src/session_context.py \
  src/htf_bias_engine.py \
  src/range_map.py \
  src/liquidity_map.py \
  src/order_block_engine.py \
  src/fvg_mapping.py \
  src/market_narrative.py \
  src/mapping_assistant.py \
  scripts/send_mapping_summary.py

git add \
  src/session_context.py \
  src/htf_bias_engine.py \
  src/range_map.py \
  src/liquidity_map.py \
  src/order_block_engine.py \
  src/fvg_mapping.py \
  src/market_narrative.py \
  src/mapping_assistant.py \
  scripts/send_mapping_summary.py

git commit -m "add mapping assistant engines" || true

echo ""
echo "✅ Mapping assistant upgrade selesai."
echo ""
echo "Test mapping:"
echo "python scripts/send_mapping_summary.py"
echo ""
echo "Kirim Telegram:"
echo "python scripts/send_mapping_summary.py --send"
echo ""
echo "Push:"
echo "git push origin main"
