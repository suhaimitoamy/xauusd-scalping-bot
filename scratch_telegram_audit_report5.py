import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.telegram_notifier import send_telegram_message

message = """
👨‍👦 **LAPORAN "SANG AYAH" (AUDIT KE-5: DEEP SURGERY)** 
━━━━━━━━━━━━━━━━━━━━━

Bos, saya baru saja menyelesaikan operasi bedah mendalam pada seluruh organ vital bot kita. Berikut ringkasannya:

🚀 **2 METODE TEMPUR BARU DITAMBAHKAN:**

1. **METHOD_LONDON_KILLZONE_REVERSAL** (BUY/SELL)
   Menangkap reversal keras di sesi London Open (07:00-10:00 UTC). London adalah sesi paling volatil untuk XAUUSD setelah NY. Bot kini punya senjata khusus untuk mengeksploitasi pembukaan pasar Eropa!

2. **METHOD_ASIAN_TRAP** (BUY/SELL)
   Mendeteksi jebakan false breakout di sesi Asia (23:00-02:00 UTC). Saat likuiditas rendah, banyak trader retail terjebak oleh sweep palsu. Bot kini bisa memanfaatkan kepanikan mereka sebagai titik entry!

🛡️ **UPGRADE PERTAHANAN TELEGRAM:**
Bot Anda tadi kebanjiran error "429 Too Many Requests" saat backtest karena Telegram menolak pesan yang terlalu cepat. Saya telah menyuntikkan sistem **Exponential Backoff Retry** ke dalam `telegram_notifier.py`:
- Jika Telegram menolak, bot akan menunggu dengan sabar lalu mencoba lagi (max 3x)
- Delay antar pesan dinaikkan dari 50ms ke 350ms untuk menghindari rate limit

🧹 **PEMBERSIHAN KODE:**
- 3 buah `bare except:` (anti-pattern Python) ditemukan dan diperbaiki menjadi `except Exception:` agar tidak menyembunyikan error kritis
- File yang diperbaiki: `market_brain.py`, `run_simulator.py`

🧠 **Total Metode Tempur Saat Ini: 36 metode**
Bot kesayangan Anda semakin pintar dan tangguh setiap jam! 💪
"""

send_telegram_message(message)
print("Berhasil mengirim laporan audit ke-5 ke Telegram.")
