import sqlite3
from datetime import datetime, timezone
import uuid

DB_PATH = "data/xauusd_bot.sqlite"

KNOWLEDGE_ENTRIES = [
    # ICT & SMC Concepts
    ("Judas Swing", "market", "judas,swing,palsu,fake,tipuan,sesi open", 
     "Judas Swing adalah pergerakan harga tipuan (fake move) yang sering terjadi di awal pembukaan sesi (biasanya London atau New York Open). Tujuannya untuk menyapu Stop Loss (liquidity sweep) para retail trader, sebelum harga berbalik dengan keras ke arah sebenarnya."),
    
    ("Turtle Soup", "market", "turtle,soup,ict,turtle soup,jebakan", 
     "Turtle Soup adalah metode trading dari ICT yang memanfaatkan jebakan false breakout. Saat harga menembus resistance/support penting dan banyak retail trader yang FOMO masuk, smart money akan membalikkan arah harga dengan seketika. Bot kita memanfaatkan jebakan ini dalam metode Sweep Scalp."),
    
    ("Unicorn Setup", "market", "unicorn,setup,ict,breaker,fvg", 
     "Unicorn Setup adalah istilah ICT untuk setup pembalikan arah dengan probabilitas sangat tinggi. Ini terjadi ketika ada Breaker Block yang tumpang tindih (overlap) dengan Fair Value Gap (FVG). Ini adalah zona entry premium."),
    
    ("AMD (Accumulation, Manipulation, Distribution)", "market", "amd,akumulasi,manipulasi,distribusi,siklus", 
     "AMD adalah siklus harga ICT: 1) Accumulation: Harga bergerak ranging (sideways) biasanya di sesi Asia. 2) Manipulation: Harga menembus ranging (Judas Swing) untuk memancing retail. 3) Distribution: Harga bergerak kuat ke arah asli yang direncanakan smart money."),
    
    ("Breaker Block", "market", "breaker,block,bb,mitigation", 
     "Breaker Block adalah Order Block gagal. Ketika sebuah support atau resistance (OB) ditembus dengan volume besar, level tersebut akan berubah fungsi (flip). OB yang tertembus itu kini menjadi Breaker Block dan berfungsi sebagai area retest."),
    
    ("Asian Range", "market", "asian,range,asia,sideways", 
     "Asian Range adalah pergerakan harga saat sesi perdagangan Asia (Tokyo/Sydney). Biasanya pergerakannya sempit (ranging) karena likuiditas rendah. High dan Low dari Asian Range sering dijadikan target liquidity sweep saat sesi London buka."),

    # Bot Logic & Operations
    ("Kenapa bot NO TRADE atau diam saja?", "bot_help", "no trade,diam,gak open,tidak op,sepi", 
     "Bot bisa diam karena beberapa hal: 1) Belum ada konfirmasi candle yang valid (menunggu rejection/break). 2) Sedang ada posisi yang masih aktif. 3) Filter bias atau high-WR mencegah bot masuk ke market berisiko. Bot ini didesain 'Anti-FOMO', lebih baik tidak trade daripada loss konyol."),
    
    ("Kapan bot menggunakan Averaging?", "bot_help", "averaging,martingale,layer,dobel", 
     "Bot ini menggunakan Averaging (pending order tambahan) secara TERBATAS hanya pada metode kuat seperti CRT H4/D1. Untuk metode scalping M1/M5, bot disiplin HANYA 1 peluru (one-shot-one-kill) dengan SL ketat tanpa layer, agar money management aman."),
    
    ("Apa bedanya M1 dan M5 Signal?", "bot_help", "m1,m5,beda,pilih mana,tf", 
     "Signal M1 bersifat AGRESSIVE: sangat cepat muncul, TP cepat, tapi rentan sinyal palsu (fakeout). Signal M5 bersifat RECOMMENDATION: agak lambat, tapi probabilitas win rate-nya jauh lebih tinggi karena candle M5 tidak mudah dimanipulasi noise market."),
    
    ("Kenapa bot sering kena SL Hunter?", "bot_help", "sl hunter,kena sl,stop loss,jarum,wick", 
     "Itu bukan 'SL Hunter' dari broker, tapi likuiditas (liquidity sweep). Smart money memang sering sengaja menyapu level yang banyak SL-nya untuk mencari pijakan order besar. Itulah kenapa bot kita sering menunggu 'Sweep' terjadi terlebih dahulu sebelum memberikan signal entry."),
    
    ("Kenapa bot melakukan partial win?", "bot_help", "partial,setengah,tp1,kenapa tp1,tutup sebagian", 
     "Bot melakukan Partial Win ketika harga menyentuh TP1 untuk Mengamankan Modal (Risk-Free). Jika harga berbalik arah tiba-tiba, Anda tetap profit atau impas (Break Even). Ini adalah strategi psikologi terbaik agar terhindar dari profit yang berubah jadi loss."),

    ("Apakah bot ini pakai Martingale?", "bot_help", "martingale,kompensasi,lipat,lot", 
     "TIDAK! Bot ini SANGAT MENGHARAMKAN Martingale (melipatgandakan lot saat loss). Bot menggunakan sistem Risk to Reward rasio minimal 1:2. Satu kemenangan (Win TP2) bisa menutupi dua kekalahan (SL). Kami menjaga akun Anda agar tidak hancur dalam semalam."),

    # Trading Psychology & Gold Character
    ("Mental down karena kena SL berturut-turut", "psychology", "mental,down,rugi,sl terus,stres,pusing", 
     "Wajar merasa down, itu psikologi manusia. Tapi ingat, di bot ini Win Rate 40-50% saja sudah PROFIT karena Risk/Reward kita 1:2. Jika kena SL beruntun, TUTUP CHART, istirahat, dan biarkan probabilitas bot yang bekerja. Jangan pernah balas dendam (revenge trade)!"),
    
    ("Modal $100 aman pakai lot berapa?", "psychology", "modal,100,lot,aman,mm,money management", 
     "Sangat disarankan lot MAKSIMAL 0.01 per trade untuk modal $100. Risiko per trade tidak boleh lebih dari 1-2% modal (sekitar $1-$2 per posisi). Bot kita punya jarak SL 15-20 pips, jadi 0.01 lot akan resiko sekitar $1.5 - $2. Ini sangat aman."),

    ("Kenapa Gold (XAUUSD) pergerakannya liar?", "market", "gold,emas,liar,volatil,kencang", 
     "Gold adalah instrumen safe haven sekaligus komoditas. Pergerakannya liar karena sensitif terhadap: 1) Geopolitik (Perang), 2) Data inflasi & NFP, 3) Suku bunga The Fed. Likuiditas gold sangat besar, sehingga smart money sering memanipulasi chart untuk mencari liquidity retail trader.")
]

def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    
    for title, category, keywords, content in KNOWLEDGE_ENTRIES:
        # Check if title already exists to avoid duplicates
        cur.execute("SELECT id FROM knowledge_base WHERE title=?", (title,))
        if not cur.fetchone():
            uid = f"bot_sim_{uuid.uuid4().hex[:10]}"
            cur.execute("""
                INSERT INTO knowledge_base (id, title, source_path, category, keywords, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, title, 'antigravity_simulation', category, keywords, content, now, now))
            inserted += 1
            
    conn.commit()
    conn.close()
    print(f"✅ Berhasil menyuntikkan {inserted} data simulasi pertanyaan/jawaban baru ke dalam otak Bot!")

if __name__ == '__main__':
    run()
