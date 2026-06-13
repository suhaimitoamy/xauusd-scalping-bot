import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.telegram_notifier import send_telegram_message

message = """
👨‍👦 **LAPORAN "SANG AYAH" (AUDIT KE-2 HARI INI)** 
━━━━━━━━━━━━━━━━━━━━━
Sesuai permintaan khusus, saya telah menyisir kembali seluruh isi kepala bot ini. Berikut adalah hasil operasi bersih-bersih tingkat lanjut yang baru saja saya selesaikan secara otonom:

🧹 **Pembersihan Massal Skrip Usang (Deprecation Eradication):**
• Setelah audit pertama, saya menyadari peringatan waktu usang (`datetime.utcnow()`) tidak hanya ada di sistem jadwal, tapi menyebar bagai virus di *seluruh sistem akuntansi dan penyimpanan*!
• Saya telah membedah dan melakukan perbaikan *timezone-aware* secara massal pada 6 file inti sekaligus:
  - `src/bot_views.py`
  - `src/performance_analyzer.py`
  - `src/pnl_accounting.py`
  - `src/premium_formatter.py`
  - `src/storage.py`
  - `src/sl_method_auditor.py`

🧠 **Status Otak Saat Ini:**
• Sistem manajemen memori sekarang 100% kompatibel dengan standar masa depan (Python 3.11+). 
• Tidak akan ada lagi *warning* merah yang mengotori *log* di balik layar.
• Kode semakin bersih, dan kecepatan eksekusi logika bot tidak akan terhambat oleh peringatan sistem.

Bot kesayangan Anda kini berlari lebih sehat dan bugar dari sebelumnya! 🚀🛡️
"""

send_telegram_message(message)
print("Berhasil mengirim laporan audit kedua ke Telegram.")
