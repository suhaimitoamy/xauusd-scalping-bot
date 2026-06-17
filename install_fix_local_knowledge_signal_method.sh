#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "${1:-$PWD}"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan dari folder repo bot."
  exit 1
fi

cp src/local_knowledge_agent.py "src/local_knowledge_agent.py.backup.methodfix.$(date +%Y%m%d_%H%M%S)"

python patch_fix_local_knowledge_signal_method.py
python -m py_compile src/local_knowledge_agent.py

git add src/local_knowledge_agent.py
git commit -m "fix local knowledge signal education method" || true

echo ""
echo "✅ Error _handle_signal_education_question sudah diperbaiki."
echo "Push:"
echo "git push origin main"
