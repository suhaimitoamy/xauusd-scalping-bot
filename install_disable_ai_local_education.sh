#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "${1:-$PWD}"

if [ ! -d ".git" ]; then
  echo "❌ Jalankan dari folder repo bot."
  exit 1
fi

cp config.yaml "config.yaml.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true

python patch_disable_ai_local_education.py
python -m py_compile src/local_bot_education.py

git add config.yaml src/local_bot_education.py
git add . || true
git commit -m "disable ai and add local bot education replies" || true

echo ""
echo "✅ Selesai."
echo "AI dimatikan."
echo "Edukasi lokal murni bot sudah ditambahkan."
echo ""
echo "Push:"
echo "git push origin main"
