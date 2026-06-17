DISABLE AI + LOCAL BOT EDUCATION

Fungsi:
1. Mematikan AI di config.yaml.
2. Menambahkan src/local_bot_education.py.
3. Edukasi bisa dijawab murni dari signal terakhir bot.
4. Label "Dijawab oleh AI" diganti ke "Dijawab oleh Bot Lokal" jika file handler ditemukan.

Cara pakai:

cd /storage/emulated/0/Download/aplikasi/xauusd-scalping-bot
unzip /storage/emulated/0/Download/disable_ai_local_education_patch.zip
bash install_disable_ai_local_education.sh
git push origin main

Module utama:
src/local_bot_education.py

Function:
answer_education_message(text, storage, symbol="XAU/USD")
