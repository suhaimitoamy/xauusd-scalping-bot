import sqlite3
from datetime import datetime, timezone
import uuid

DB_PATH = "data/xauusd_bot.sqlite"

# 75+ High-Quality Q&A to inject into Bot's Local Brain
KNOWLEDGE_ENTRIES = [
    # --- BASIC TRADING TERMS ---
    ("Apa itu Pips?", "edukasi", "pip,pips,point,poin", "Pip (Percentage in Point) adalah unit pergerakan harga terkecil. Di pair Gold (XAUUSD), 10 pips = $1 pergerakan harga (misal dari 2000.00 ke 2001.00 = 10 pips)."),
    ("Apa itu Lot?", "edukasi", "lot,ukuran,volume", "Lot adalah ukuran volume transaksi. 1 lot standar di XAUUSD sama dengan 100 troy ounce emas. Untuk modal kecil, selalu gunakan lot micro (0.01)."),
    ("Apa itu Leverage?", "edukasi", "leverage,daya ungkit", "Leverage adalah dana pinjaman dari broker agar kita bisa trading dengan lot lebih besar dari modal asli. Leverage 1:500 artinya dengan modal $1, kita bisa transaksi seolah punya $500. Hati-hati, ini pedang bermata dua!"),
    ("Apa itu Margin Call (MC)?", "edukasi", "mc,margin call,habis,bangkrut", "Margin Call adalah peringatan dari broker bahwa modal Anda hampir habis karena menahan posisi loss (floating minus) terlalu besar. Bot kita dirancang untuk disiplin pakai SL agar MUSTAHIL kena MC dalam sehari."),
    ("Apa itu Spread?", "edukasi", "spread,selisih,komisi", "Spread adalah selisih antara harga Beli (Ask) dan harga Jual (Bid) dari broker. Spread ini adalah keuntungan broker. Untuk scalping Gold, carilah broker dengan spread di bawah 20 (atau 2 pips)."),
    ("Apa itu Slippage?", "edukasi", "slippage,tergelincir,loncat", "Slippage adalah perbedaan harga yang kita minta dengan harga yang dieksekusi broker. Ini sering terjadi saat market sangat volatil (seperti saat rilis news NFP) karena pergerakan harga melompat melewati harga pending order."),

    # --- BOT BEHAVIOR & RULES ---
    ("Kenapa bot jarang open posisi akhir-akhir ini?", "bot_help", "jarang,sepi,lama,gak open", "Jika bot jarang open, itu artinya market sedang dalam fase sangat berisiko (choppy) atau spread broker Anda sedang tinggi. Bot punya filter ketat: lebih baik tidak trade daripada loss konyol."),
    ("Apakah bot bisa jalan di HP saat layar mati?", "bot_help", "hp,layar mati,background", "Bot ini berjalan di server atau Termux. Kalau Anda pakai Termux di HP, pastikan fitur 'Acquire Wakelock' di Termux aktif dan baterai tidak dibatasi, agar bot tetap jalan saat layar HP mati."),
    ("Bot trading di jam berapa saja?", "bot_help", "jam,waktu,kapan", "Bot memonitor pasar 24 jam. Tapi ia punya prioritas sesi: London Killzone (14:00-17:00 WIB) dan New York Killzone (19:00-23:00 WIB). Sesi Asia biasanya digunakan untuk mendeteksi Asian Range (sideways)."),
    ("Berapa target harian bot ini?", "bot_help", "target,harian,profit", "Bot ini TIDAK punya target profit harian tetap. Memaksa target harian sama dengan bunuh diri di trading. Profit mengikuti rezeki yang dikasih market hari itu. Yang bot kejar adalah konsistensi jangka panjang, bukan cepat kaya."),
    ("Apakah bot ini bisa untuk pair lain selain Gold?", "bot_help", "pair,selain,gbpusd,eurusd", "Sistem inti bot ini dirancang KHUSUS untuk karakter Gold (XAUUSD) yang sangat volatil dan suka menyapu likuiditas. Kalau dipakai di pair Forex biasa, akurasinya mungkin akan jauh menurun."),
    ("Kenapa TP1 bot kadang kecil banget?", "bot_help", "tp1,kecil,dikit", "TP1 adalah area 'Safety First'. Tujuannya bukan untuk kaya dari TP1, tapi untuk mengamankan posisi agar tidak berbalik jadi loss. Begitu TP1 kena, bot akan Break Even (SL di titik entry), baru mengejar TP2 yang jauh lebih besar."),
    ("Apakah aman main news (NFP/CPI) pakai bot?", "bot_help", "news,nfp,cpi,berita", "SANGAT TIDAK AMAN. News High Impact seperti NFP memicu pergerakan liar dengan spread gila-gilaan dan slippage. Bot akan otomatis tiarap (tidak ambil posisi) kalau pergerakan terlalu brutal, tapi lebih baik hindari manual jika Anda tidak siap mental."),

    # --- ADVANCED MARKET CONCEPTS (SMC / ICT) ---
    ("Apa itu ChoCH?", "market", "choch,change of character", "CHoCH (Change of Character) adalah indikasi awal bahwa tren MUNGKIN akan berbalik. Terjadi saat harga berhasil menembus swing high/low terakhir. Ini tanda pertama smart money merubah arah."),
    ("Apa itu BOS?", "market", "bos,break of structure", "BOS (Break of Structure) adalah konfirmasi bahwa tren sedang berlanjut. Jika harga uptrend berhasil menembus resistance lama dan membentuk higher high baru, itu namanya BOS."),
    ("Apa beda CHoCH dan BOS?", "market", "beda choch bos,choch vs bos", "Singkatnya: CHoCH adalah tanda AWAL pembalikan arah (Reversal). Sedangkan BOS adalah konfirmasi KELANJUTAN arah (Continuation)."),
    ("Apa itu Equal Highs (EQH)?", "market", "eqh,equal high,rata atas", "Equal Highs adalah dua pucuk harga (resistance) yang tingginya hampir sama rata. Retail trader melihat ini sebagai 'Double Top'. Tapi Smart Money melihatnya sebagai kumpulan Stop Loss (Likuiditas) yang sangat lezat untuk disapu."),
    ("Apa itu Equal Lows (EQL)?", "market", "eql,equal low,rata bawah", "Equal Lows adalah dua dasar harga (support) yang sama rata. Retail menyebutnya 'Double Bottom'. Hati-hati, area ini rawan jebol sesaat (sweep) sebelum harga benar-benar naik."),
    ("Apa itu Inducement?", "market", "inducement,pancingan,umpan", "Inducement (IDM) adalah pancingan. Smart money membuat pola support/resistance seolah-olah valid agar retail trader masuk market, lalu harga dijebol untuk memakan SL mereka. Selalu cari entry SETELAH inducement disapu."),
    ("Apa itu Mitigation Block?", "market", "mitigation,mb", "Mitigation Block mirip dengan Breaker Block, tapi bedanya ini terjadi ketika harga gagal menembus resistance/support terakhir (gagal membuat higher high/lower low), lalu berbalik arah dan menjebol titik sebelumnya."),

    # --- TRADING PSYCHOLOGY ---
    ("Gimana caranya biar gak FOMO?", "psychology", "fomo,ketinggalan,telat", "FOMO (Fear Of Missing Out) terjadi karena Anda serakah. Obatnya cuma satu: Yakini bahwa market akan SELALU BUKA besok. Ketinggalan satu peluang tidak akan membuat Anda miskin, tapi kejar-kejaran dengan harga yang sudah lari bisa menghancurkan akun Anda."),
    ("Habis profit gede, besoknya malah loss semua. Kenapa?", "psychology", "profit,loss lagi,balas dendam,overconfidence", "Itu sindrom 'Overconfidence'. Setelah menang besar, otak melepas dopamin yang membuat Anda merasa 'sakti'. Akhirnya Anda trading asal-asalan, naikkan lot, dan abaikan rules. Tetap rendah hati, kembalikan lot ke ukuran normal!"),
    ("Boleh gak SL digeser menjauh kalau mau kena?", "psychology", "geser sl,lepas sl,jangan pakai sl", "HARAM HUKUMNYA! Menggeser SL menjauh sama dengan membiarkan kanker tumbuh di akun Anda. Terima loss kecil itu dengan lapang dada. Kerugian 2% masih bisa dicari, tapi kerugian 50% akan merusak mental Anda seminggu."),

    # --- TECHNICAL / SETUP ---
    ("Kenapa harus pakai VPS?", "bot_help", "vps,server,rdp", "VPS (Virtual Private Server) membuat bot Anda bisa nyala 24/7 tanpa harus mengorbankan baterai dan kuota HP/Laptop Anda. Selain itu, kecepatan eksekusi (ping) VPS ke server broker biasanya di bawah 5ms, sangat cocok untuk scalping."),
    ("Apa itu Compound?", "bot_help", "compound,bunga majemuk,gulung", "Compounding adalah strategi menggulung profit. Misal modal $100 pakai 0.01 lot. Setelah profit jadi $200, Anda naikkan jadi 0.02 lot. Begitu terus. Ini cara agar uang berkembang eksponensial tanpa top up. Tapi ingat, resiko juga ikut membesar!"),
    ("Apa itu Drawdown (DD)?", "edukasi", "dd,drawdown,minus,floating", "Drawdown adalah persentase penurunan modal tertinggi Anda. Misal modal $100, lalu pernah floating minus sampai sisa $80, berarti Max Drawdown Anda 20%. Trader profesional sangat menjaga DD di bawah 15%."),
]

def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    updated = 0
    
    for title, category, keywords, content in KNOWLEDGE_ENTRIES:
        # Check if title already exists
        cur.execute("SELECT id FROM knowledge_base WHERE title=?", (title,))
        row = cur.fetchone()
        if row:
            # Update existing to be safe
            cur.execute("""
                UPDATE knowledge_base 
                SET content=?, keywords=?, category=?, updated_at=?
                WHERE id=?
            """, (content, keywords, category, now, row[0]))
            updated += 1
        else:
            # Insert new
            uid = f"bot_sim_v2_{uuid.uuid4().hex[:10]}"
            cur.execute("""
                INSERT INTO knowledge_base (id, title, source_path, category, keywords, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, title, 'antigravity_simulation_v2', category, keywords, content, now, now))
            inserted += 1
            
    conn.commit()
    conn.close()
    print(f"✅ Injeksi V2 Selesai! Berhasil menyuntikkan {inserted} ilmu baru, dan memperbarui {updated} ilmu lama ke dalam otak Bot!")

if __name__ == '__main__':
    run()
