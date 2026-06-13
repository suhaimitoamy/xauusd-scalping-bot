import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.telegram_notifier import send_telegram_message

message = """
👨‍👦 **LAPORAN "SANG AYAH" (AUDIT KE-6: FITUR BESAR)** 
━━━━━━━━━━━━━━━━━━━━━

Bos, kali ini saya tidak hanya membersihkan, tapi membangun fitur baru yang sangat besar!

🆕 **FITUR BARU: /daily_recap (Rangkuman Harian)**
Sekarang Anda bisa mengetik `/daily_recap`, `/recap`, atau `/hari_ini` di Telegram (atau tekan tombol 📋 Recap di menu) untuk langsung melihat:
• Total trade hari ini (Win/Loss/WR%)
• Net R hari ini
• Breakdown performa per metode (mana yang hijau, mana yang merah)
• Posisi yang masih aktif
• Ringkasan semua event hari ini
Tidak perlu lagi buka laptop — cukup satu ketukan dari HP!

🧠 **4 KNOWLEDGE BARU DITAMBAHKAN:**
Bot Telegram kini lebih pintar menjawab pertanyaan tentang:
• London Killzone Reversal
• NY Killzone Reversal
• Asian Session Trap
• Break-Even / Trailing Stop Logic
Coba tanya di Telegram: "Apa itu London Killzone?" dan bot akan menjawab tanpa butuh AI!

📱 **UPGRADE KEYBOARD TELEGRAM:**
Layout tombol Telegram diperbarui! Tombol baru 📋 Recap kini tampil di barisan utama bersama 📊 Stats.

📝 **UPDATE HELP & METHODS:**
• /help kini mencantumkan /daily_recap
• /methods kini menampilkan 36 metode lengkap (termasuk Killzone, Asian Trap, ICT methods)

Anak kita semakin dewasa, Bos! 🚀
"""

send_telegram_message(message)
print("Berhasil mengirim laporan audit ke-6 ke Telegram.")
