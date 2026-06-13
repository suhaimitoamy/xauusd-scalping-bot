import sqlite3
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.telegram_notifier import send_telegram_message

DB_PATH = "data/xauusd_bot.sqlite"

def get_db_data():
    if not os.path.exists(DB_PATH):
        return {}
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    data = {}
    
    # 1. Current Price (from candles table)
    cur.execute("SELECT close FROM candles ORDER BY open_time DESC LIMIT 1")
    row = cur.fetchone()
    data['current_price'] = row['close'] if row else 0.0
    cp = data['current_price']
    
    # 2. Bias — compute from recent candles (SMA20 vs SMA50 shortcut)
    cur.execute("SELECT close FROM candles WHERE timeframe='M5' ORDER BY open_time DESC LIMIT 50")
    closes = [r['close'] for r in cur.fetchall()]
    if len(closes) >= 50:
        sma20 = sum(closes[:20]) / 20
        sma50 = sum(closes[:50]) / 50
        if sma20 > sma50 + 1.0:
            data['bias'] = 'Bullish'
        elif sma20 < sma50 - 1.0:
            data['bias'] = 'Bearish'
        else:
            data['bias'] = 'Ranging'
    else:
        data['bias'] = 'Ranging'
    
    # 3. Supply & Demand
    cur.execute("SELECT * FROM supply_demand_zones WHERE status = 'VALID' AND zone_type LIKE '%SUPPLY%' ORDER BY created_at DESC LIMIT 1")
    data['supply'] = cur.fetchone()
    
    cur.execute("SELECT * FROM supply_demand_zones WHERE status = 'VALID' AND zone_type LIKE '%DEMAND%' ORDER BY created_at DESC LIMIT 1")
    data['demand'] = cur.fetchone()
    
    # 4. FVG — direction is 'Bullish'/'Bearish' (capitalized), status UNFILLED = fresh
    cur.execute("SELECT * FROM active_fvgs WHERE direction = 'Bullish' AND status != 'INVALID' ORDER BY created_at DESC LIMIT 1")
    data['bullish_fvg'] = cur.fetchone()
    
    cur.execute("SELECT * FROM active_fvgs WHERE direction = 'Bearish' AND status != 'INVALID' ORDER BY created_at DESC LIMIT 1")
    data['bearish_fvg'] = cur.fetchone()
    
    # 5. Order Blocks — direction is NULL! Use `type` column instead ('Bullish'/'Bearish')
    cur.execute("SELECT * FROM active_order_blocks WHERE type = 'Bullish' AND status = 'VALID' ORDER BY created_at DESC LIMIT 1")
    data['bullish_ob'] = cur.fetchone()
    
    cur.execute("SELECT * FROM active_order_blocks WHERE type = 'Bearish' AND status = 'VALID' ORDER BY created_at DESC LIMIT 1")
    data['bearish_ob'] = cur.fetchone()
    
    # 6. Liquidity — pool_type is 'EQH'/'EQL', map to BSL/SSL
    cur.execute("SELECT pool_type, level FROM liquidity_pools WHERE status = 'ACTIVE' ORDER BY created_at DESC")
    liquidity = cur.fetchall()
    lq = {}
    for row in liquidity:
        pt = row['pool_type'].upper()
        if pt == 'EQH' and 'EQH' not in lq:
            lq['EQH'] = row['level']
        elif pt == 'EQL' and 'EQL' not in lq:
            lq['EQL'] = row['level']
    # Map EQH/EQL to BSL/SSL for display
    lq['BSL'] = lq.get('EQH')
    lq['SSL'] = lq.get('EQL')
    data['liquidity'] = lq
    
    # 7. POI Utama — construct from nearest OB/FVG/SD zone to current price
    poi_candidates = []
    if data.get('supply'):
        z = data['supply']
        poi_candidates.append(('Supply', z['low'], z['high'], abs(cp - z['low'])))
    if data.get('demand'):
        z = data['demand']
        poi_candidates.append(('Demand', z['low'], z['high'], abs(cp - z['high'])))
    if data.get('bullish_fvg'):
        f = data['bullish_fvg']
        poi_candidates.append(('FVG Bullish', f['low'], f['high'], abs(cp - f['high'])))
    if data.get('bearish_fvg'):
        f = data['bearish_fvg']
        poi_candidates.append(('FVG Bearish', f['low'], f['high'], abs(cp - f['low'])))
    if data.get('bullish_ob'):
        o = data['bullish_ob']
        poi_candidates.append(('OB Bullish', o['low'], o['high'], abs(cp - o['high'])))
    if data.get('bearish_ob'):
        o = data['bearish_ob']
        poi_candidates.append(('OB Bearish', o['low'], o['high'], abs(cp - o['low'])))
    
    if poi_candidates:
        poi_candidates.sort(key=lambda x: x[3])
        nearest = poi_candidates[0]
        data['main_poi'] = {'type': nearest[0], 'low': nearest[1], 'high': nearest[2], 'dist': nearest[3]}
    
    # 8. BOS / CHoCH
    cur.execute("SELECT * FROM structure_events WHERE event_type LIKE '%BOS%' OR event_type LIKE '%CHOCH%' ORDER BY created_at DESC LIMIT 4")
    data['structure'] = cur.fetchall()
    
    # 9. Compute BOS/CHoCH from recent candle swings if structure_events is empty
    if not data['structure'] and len(closes) >= 20:
        # Simple swing detection for BOS/CHoCH
        recent_highs = []
        recent_lows = []
        cur.execute("SELECT high, low FROM candles WHERE timeframe='M5' ORDER BY open_time DESC LIMIT 20")
        for r in cur.fetchall():
            recent_highs.append(r['high'])
            recent_lows.append(r['low'])
        if recent_highs and recent_lows:
            data['computed_bos'] = {
                'bull_bos': max(recent_highs),
                'bear_bos': min(recent_lows),
            }
    
    conn.close()
    return data

def fmt(val):
    """Format a float price or return N/A"""
    if val is None:
        return 'N/A'
    return f"{float(val):.2f}"

def build_message(d):
    cp = d.get('current_price', 0.0)
    
    msg = f"📊 **MARKET SUMMARY GOLD - 30 MIN**\n"
    msg += f"Harga Sekarang: {cp:.2f}\n"
    msg += f"Bias: {d.get('bias', 'Netral')}\n\n"
    
    # Supply
    msg += "🔴 **Supply:**\n"
    if d.get('supply'):
        s = d['supply']
        dist = abs(cp - s['low'])
        msg += f"- {s['timeframe']}: {s['low']:.2f} - {s['high']:.2f}\n"
        msg += f"- Jarak: {dist:.1f} point\n\n"
    else:
        msg += "- Belum tersedia\n\n"
        
    # Demand
    msg += "🟢 **Demand:**\n"
    if d.get('demand'):
        s = d['demand']
        dist = abs(cp - s['high'])
        msg += f"- {s['timeframe']}: {s['low']:.2f} - {s['high']:.2f}\n"
        msg += f"- Jarak: {dist:.1f} point\n\n"
    else:
        msg += "- Belum tersedia\n\n"
        
    # FVG
    msg += "⚡ **FVG / Imbalance:**\n"
    if d.get('bullish_fvg'):
        f = d['bullish_fvg']
        status = f['status'].lower().replace('unfilled', 'fresh')
        msg += f"- Bullish FVG ({f['timeframe']}): {f['low']:.2f} - {f['high']:.2f} [{status}]\n"
    else:
        msg += "- Bullish FVG: Belum ada\n"
        
    if d.get('bearish_fvg'):
        f = d['bearish_fvg']
        status = f['status'].lower().replace('unfilled', 'fresh')
        msg += f"- Bearish FVG ({f['timeframe']}): {f['low']:.2f} - {f['high']:.2f} [{status}]\n\n"
    else:
        msg += "- Bearish FVG: Belum ada\n\n"
        
    # Order Block
    msg += "🧱 **Order Block:**\n"
    if d.get('bullish_ob'):
        o = d['bullish_ob']
        msg += f"- Bullish OB ({o['timeframe']}): {o['low']:.2f} - {o['high']:.2f} [{o['status'].lower()}]\n"
    else:
        msg += "- Bullish OB: Belum ada\n"
        
    if d.get('bearish_ob'):
        o = d['bearish_ob']
        msg += f"- Bearish OB ({o['timeframe']}): {o['low']:.2f} - {o['high']:.2f} [{o['status'].lower()}]\n\n"
    else:
        msg += "- Bearish OB: Belum ada\n\n"
        
    # Inducement & Liquidity (combined because EQH/EQL = BSL/SSL)
    lq = d.get('liquidity', {})
    msg += "🎯 **Inducement:**\n"
    msg += f"- Buy-side (EQH): {fmt(lq.get('EQH'))}\n"
    msg += f"- Sell-side (EQL): {fmt(lq.get('EQL'))}\n\n"
    
    msg += "💧 **Liquidity:**\n"
    msg += f"- BSL (Equal Highs): {fmt(lq.get('BSL'))}\n"
    msg += f"- SSL (Equal Lows): {fmt(lq.get('SSL'))}\n\n"
    
    # POI Utama
    msg += "📌 **POI Utama:**\n"
    if d.get('main_poi'):
        p = d['main_poi']
        scenario = "wait confirmation"
        bias = d.get('bias', 'Ranging')
        if 'Demand' in p['type'] and bias == 'Bullish':
            scenario = "potensi reversal bullish"
        elif 'Supply' in p['type'] and bias == 'Bearish':
            scenario = "potensi reversal bearish"
        elif 'FVG' in p['type']:
            scenario = "potensi retest FVG"
        msg += f"- Jenis: {p['type']}\n"
        msg += f"- Area: {p['low']:.2f} - {p['high']:.2f}\n"
        msg += f"- Jarak: {p['dist']:.1f} point\n"
        msg += f"- Skenario: {scenario}\n\n"
    else:
        msg += "- Belum ada POI valid terdekat\n\n"
        
    # Market Structure
    msg += "📈 **Market Structure:**\n"
    msg += f"- Struktur Saat Ini: {d.get('bias', 'Ranging')}\n"
    
    bull_bos = "N/A"
    bear_bos = "N/A"
    bull_choch = "N/A"
    bear_choch = "N/A"
    struct_status = "Belum break"
    
    if d.get('structure'):
        for s in d['structure']:
            et = s['event_type'].upper() if s['event_type'] else ''
            if 'BULLISH' in et and 'BOS' in et: bull_bos = f"{s['level']:.2f}"
            elif 'BEARISH' in et and 'BOS' in et: bear_bos = f"{s['level']:.2f}"
            elif 'BULLISH' in et and 'CHOCH' in et: bull_choch = f"{s['level']:.2f}"
            elif 'BEARISH' in et and 'CHOCH' in et: bear_choch = f"{s['level']:.2f}"
        latest_event = d['structure'][0]
        if latest_event['price'] and latest_event['level']:
            struct_status = f"{latest_event['event_type']} valid"
    elif d.get('computed_bos'):
        cb = d['computed_bos']
        bull_bos = f"{cb['bull_bos']:.2f}"
        bear_bos = f"{cb['bear_bos']:.2f}"
        struct_status = "Computed from recent swings"
            
    msg += f"- Bullish BOS: break & close di atas {bull_bos}\n"
    msg += f"- Bearish BOS: break & close di bawah {bear_bos}\n"
    msg += f"- Bullish CHoCH: break & close di atas {bull_choch}\n"
    msg += f"- Bearish CHoCH: break & close di bawah {bear_choch}\n"
    msg += f"- Status Break: {struct_status}\n\n"
    
    # Kesimpulan
    kesimpulan = "wait confirmation"
    bias = d.get('bias', 'Ranging')
    has_fvg = d.get('bullish_fvg') or d.get('bearish_fvg')
    has_ob = d.get('bullish_ob') or d.get('bearish_ob')
    if bias == 'Bullish' and (d.get('bullish_fvg') or d.get('bullish_ob')):
        kesimpulan = "layak entry BUY (Bullish trend + confluence)"
    elif bias == 'Bearish' and (d.get('bearish_fvg') or d.get('bearish_ob')):
        kesimpulan = "layak entry SELL (Bearish trend + confluence)"
    elif has_fvg or has_ob:
        kesimpulan = "ada confluence tapi tren belum jelas, pantau area POI"
        
    msg += f"**Kesimpulan:** {kesimpulan}\n"
    return msg

def main():
    import os
    is_simulator = os.environ.get('DRY_RUN', '').lower() == 'true'
    try:
        data = get_db_data()
        msg = build_message(data)
        if not is_simulator:
            print("Mengirim pesan ke Telegram:\n" + "="*40 + "\n" + msg + "\n" + "="*40)
            send_telegram_message(msg)
        else:
            print("[SIMULATOR] Muting Market Summary to prevent Telegram spam.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
