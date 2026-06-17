import argparse
import sys
import os
import json
import logging
import uuid
from datetime import datetime, timezone

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.storage import Storage
from src.ai_advisor import get_ai_response
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def get_extreme_moves(storage: Storage, limit: int = 50):
    conn = storage.get_connection()
    conn.row_factory = __import__('sqlite3').Row
    cur = conn.cursor()
    
    # Cari candle M5 dengan body yang sangat besar (pergerakan ekstrem)
    cur.execute('''
        SELECT * FROM candles 
        WHERE timeframe='M5' AND ABS(close - open) > 2.0
        ORDER BY RANDOM() 
        LIMIT ?
    ''', (limit * 2,)) # Ambil 2x lipat untuk difilter
    
    extreme_candles = [dict(r) for r in cur.fetchall()]
    
    contexts = []
    for ec in extreme_candles:
        # Ambil 5 candle M5 persis sebelum extreme candle ini
        cur.execute('''
            SELECT * FROM candles
            WHERE timeframe='M5' AND open_time < ?
            ORDER BY open_time DESC
            LIMIT 5
        ''', (ec['open_time'],))
        prev_candles = [dict(r) for r in cur.fetchall()][::-1]
        
        if len(prev_candles) == 5:
            move_type = "BULLISH_EXPLOSION" if ec['close'] > ec['open'] else "BEARISH_DUMP"
            contexts.append({
                'move_type': move_type,
                'explosion_candle': {
                    'open': ec['open'], 'high': ec['high'], 'low': ec['low'], 'close': ec['close']
                },
                'previous_5_candles': [
                    {'open': p['open'], 'high': p['high'], 'low': p['low'], 'close': p['close']} for p in prev_candles
                ]
            })
            
            if len(contexts) >= limit:
                break
                
    conn.close()
    return contexts

def discover_patterns(storage: Storage, contexts: list):
    logging.info(f"Mengirim {len(contexts)} data ekstrem ke AI (DeepSeek/Gemini) untuk analisa...")
    
    prompt = f"""
Anda adalah Senior Quantitative Researcher untuk algoritma trading XAUUSD.
Berikut adalah {len(contexts)} data histori acak di mana harga mengalami PERGERAKAN EKSTREM (Ledakan/Dump) pada timeframe M5.
Setiap data berisi 'previous_5_candles' (5 candle sebelum ledakan) dan 'explosion_candle' (candle yang meledak).

TUGAS ANDA:
1. Analisa kesamaan dari 'previous_5_candles' sebelum ledakan terjadi.
2. Apakah ada pola berulang? (Misalnya: 3 candle bearish berturut-turut lalu doji, atau sumbu bawah panjang, atau kompresi body).
3. Ciptakan 1 hingga 3 Aturan Trading Dinamis (Dynamic Rules) berdasarkan temuan Anda.

FORMAT OUTPUT HARUS JSON (Tanpa teks lain, tanpa markdown ```json):
[
    {{
        "pattern_key": "AI_DISCOVERY_BULL_01",
        "description": "Ditemukan pola 3 bearish lalu 1 pinbar",
        "direction": "BUY",
        "rules": {{
            "momentum_bias": "bearish",
            "max_body_ratio": 0.4,
            "requires_wick": "lower",
            "min_candles_checked": 4
        }}
    }}
]

DATA:
{json.dumps(contexts, indent=2)}
"""

    messages = [
        {"role": "system", "content": "You are a quantitative researcher."},
        {"role": "user", "content": prompt}
    ]
    response, success = get_ai_response(messages, fallback_text="Admin Review", timeout=120)
    if not success or not response or response.startswith("Admin Review"):
        logging.error("Gagal mendapatkan respons valid dari AI.")
        return None
        
    try:
        # Bersihkan markdown jika AI membandel
        cleaned = response.replace("```json", "").replace("```", "").strip()
        rules = json.loads(cleaned)
        return rules
    except Exception as e:
        logging.error(f"Gagal parse JSON dari AI: {e}")
        logging.debug(f"Raw response: {response}")
        return None

def save_dynamic_rules(storage: Storage, rules: list):
    conn = storage.get_connection()
    cur = conn.cursor()
    
    count = 0
    for rule in rules:
        pattern_key = rule.get('pattern_key')
        if not pattern_key: continue
        
        # Tambahkan UUID agar tidak pernah menimpa pola sebelumnya
        unique_suffix = uuid.uuid4().hex[:4].upper()
        pattern_key = f"{pattern_key}_{unique_suffix}"
        rule['pattern_key'] = pattern_key
        
        # Insert or replace
        try:
            cur.execute('''
                INSERT OR REPLACE INTO dynamic_rules (pattern_key, rule_json, created_at)
                VALUES (?, ?, ?)
            ''', (pattern_key, json.dumps(rule, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
            count += 1
        except Exception as e:
            logging.error(f"Gagal menyimpan rule {pattern_key}: {e}")
            
    conn.commit()
    conn.close()
    return count

def main():
    storage = Storage()
    logging.info("Mencari data pergerakan ekstrem di memori lokal...")
    contexts = get_extreme_moves(storage, limit=20) # 20 sampel sudah cukup merepresentasikan tanpa menghabiskan token
    
    if not contexts:
        logging.error("Tidak cukup data candle di database. Jalankan simulator dulu atau tunggu bot live mengumpulkan data.")
        return
        
    rules = discover_patterns(storage, contexts)
    if rules:
        msg = f"🧠 **Super AI Discovery Selesai**\n\nAI berhasil menciptakan {len(rules)} pola baru!\n\n"
        logging.info(f"AI berhasil menciptakan {len(rules)} pola baru!")
        for r in rules:
            logging.info(f"- {r.get('pattern_key')} ({r.get('direction')}): {r.get('description')}")
            msg += f"🔹 **{r.get('pattern_key')}** ({r.get('direction')})\n{r.get('description')}\n\n"
            
        saved = save_dynamic_rules(storage, rules)
        logging.info(f"✅ {saved} pola berhasil di-inject ke database dynamic_rules.")
        msg += f"✅ {saved} pola berhasil di-inject ke memori otak."
        
        try:
            from src.telegram_notifier import send_telegram_message
            send_telegram_message(msg)
        except Exception:
            pass
    else:
        logging.warning("AI tidak mengembalikan pola yang valid.")
        try:
            from src.telegram_notifier import send_telegram_message
            send_telegram_message("❌ Super AI gagal menemukan pola baru dari sampel saat ini.")
        except Exception:
            pass

if __name__ == "__main__":
    main()
