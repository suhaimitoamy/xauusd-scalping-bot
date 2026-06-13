import sqlite3
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.telegram_notifier import send_telegram_message

DB_PATH = "data/xauusd_bot.sqlite"

def get_trend(candles, period1=20, period2=50):
    if len(candles) < period2:
        return "NEUTRAL", "Kurang data"
    
    closes = [c['close'] for c in candles]
    sma20 = sum(closes[:period1]) / period1
    sma50 = sum(closes[:period2]) / period2
    
    if sma20 > sma50 + 1.0:
        return "BULLISH 🟢", "Uptrend kuat (Fokus mencari Setup BUY)"
    elif sma20 < sma50 - 1.0:
        return "BEARISH 🔴", "Downtrend kuat (Fokus mencari Setup SELL)"
    else:
        return "RANGING 🟡", "Konsolidasi (Waspada Choppy Market)"

def get_nearest_poi(cur, price, poi_type, table, type_col="direction", val_col="low", status_col="status", active_val="VALID"):
    cur.execute(f"SELECT * FROM {table} WHERE {type_col} = ? AND {status_col} = ? ORDER BY {val_col} DESC LIMIT 5", (poi_type, active_val))
    rows = cur.fetchall()
    if not rows:
        return "Tidak ada"
        
    nearest = min(rows, key=lambda x: min(abs(price - x['low']), abs(price - x['high'])))
    return f"{nearest['low']:.2f} - {nearest['high']:.2f}"

def main():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("SELECT close FROM candles ORDER BY open_time DESC LIMIT 1")
    row = cur.fetchone()
    current_price = row['close'] if row else 0.0
    
    # H4 Trend
    cur.execute("SELECT close FROM candles WHERE timeframe='H4' ORDER BY open_time DESC LIMIT 60")
    h4_candles = cur.fetchall()
    h4_trend, h4_desc = get_trend(h4_candles)
    
    # D1 Trend
    cur.execute("SELECT close FROM candles WHERE timeframe='D1' ORDER BY open_time DESC LIMIT 60")
    d1_candles = cur.fetchall()
    d1_trend, d1_desc = get_trend(d1_candles)
    
    # Get Key Levels
    key_res = get_nearest_poi(cur, current_price, 'Bearish', 'active_order_blocks', 'type')
    key_sup = get_nearest_poi(cur, current_price, 'Bullish', 'active_order_blocks', 'type')
    
    msg = (
        "📰 **DAILY BIAS OUTLOOK (XAUUSD)**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Harga Saat Ini: **{current_price:.2f}**\n\n"
        "🔭 **Market Structure / Trend:**\n"
        f"• Daily (D1): {d1_trend}\n"
        f"• 4-Hour (H4): {h4_trend}\n"
        f"💡 Rekomendasi: _{h4_desc}_\n\n"
        "🛡️ **Key POI Levels (SMC):**\n"
        f"• Nearest Resistance (Bearish OB): {key_res}\n"
        f"• Nearest Support (Bullish OB): {key_sup}\n\n"
        "🤖 _Pesan ini di-generate otomatis oleh Antigravity Morning Routine._"
    )
    
    print(msg)
    send_telegram_message(msg)
    conn.close()

if __name__ == "__main__":
    main()
