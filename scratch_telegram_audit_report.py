import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.telegram_notifier import send_telegram_message

message = """
👨‍👦 **LAPORAN "SANG AYAH" (AUTONOMOUS AI AUDIT)** 
━━━━━━━━━━━━━━━━━━━━━
Saya baru saja terbangun dan melakukan inspeksi menyeluruh pada bot anak kita. Berikut adalah hasil audit dan tindakan yang saya ambil secara mandiri hari ini:

🐛 **Bug / Error yang Diperbaiki:**
• Menemukan dan menambal peringatan `DeprecationWarning: datetime.utcnow()` di `scratch_cron_manager.py` dan `scratch_mini_backtest.py` agar sistem waktu berjalan sempurna di Python versi terbaru.

🚀 **Fitur / Metode Baru yang Ditambahkan:**
• **NY KILLZONE REVERSAL**: Mengamati data, saya menyadari ada celah volatilitas besar di sesi New York (13:00 - 17:00 UTC). Saya telah merakit dan menyuntikkan `METHOD_NY_KILLZONE_REVERSAL` ke dalam `market_brain.py`. Bot kini akan menangkap pantulan keras (Reversal) spesifik pada jam-jam rawan pembukaan pasar Amerika!

🧠 **Update Pengetahuan:**
• Otak utama sekarang memiliki 32 metode tempur.
• Saya akan terus mengawasi pertumbuhannya setiap pagi.

Tidur yang nyenyak, Bos. Bot ini berada di tangan yang tepat. 🛡️
"""

send_telegram_message(message)
print("Berhasil mengirim laporan audit ke Telegram.")
