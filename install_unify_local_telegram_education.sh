#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "${1:-$PWD}"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan dari folder repo bot."
  exit 1
fi

if [ ! -f "src/local_knowledge_agent.py" ]; then
  echo "❌ src/local_knowledge_agent.py tidak ditemukan."
  exit 1
fi

if [ ! -f "src/telegram_interactive.py" ]; then
  echo "❌ src/telegram_interactive.py tidak ditemukan."
  exit 1
fi

cp src/local_knowledge_agent.py "src/local_knowledge_agent.py.backup.$(date +%Y%m%d_%H%M%S)"
cp src/telegram_interactive.py "src/telegram_interactive.py.backup.$(date +%Y%m%d_%H%M%S)"
cp config.yaml "config.yaml.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true

python patch_unify_local_telegram_education.py

python -m py_compile src/local_knowledge_agent.py src/telegram_interactive.py

git add src/local_knowledge_agent.py src/telegram_interactive.py config.yaml
git rm -f src/local_bot_education.py 2>/dev/null || true
git commit -m "unify telegram local education and disable ai fallback" || true

echo ""
echo "✅ Selesai."
echo "Sekarang:"
echo "- Enaknya sell atau buy = local_knowledge_agent.py"
echo "- Kenapa/alasan/detail = local_knowledge_agent.py"
echo "- Knowledge konsep tetap local_knowledge_agent.py + knowledge_seed.json"
echo "- AI fallback Telegram default OFF"
echo "- local_bot_education.py dihapus agar tidak dobel sistem"
echo ""
echo "Push:"
echo "git push origin main"
