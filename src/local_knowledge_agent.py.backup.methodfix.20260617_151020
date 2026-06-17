"""Local Knowledge Agent — intent-routed, pure local (no AI fallback).

Handles FAQ, psychology/curhat, fundamental, help, and market questions
from Telegram users. All responses are labeled as Bot Lokal.
"""

import json
import os
import re
import random
import sqlite3
from datetime import datetime, timezone, timedelta

from src.message_intent_router import IntentRouter


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

STOPWORDS = set('''
dan atau yang dari untuk dengan dalam pada ke di ini itu adalah sebagai agar
bukan jadi saat ketika kalau maka lebih sangat bisa harus ada karena secara
lalu juga akan telah setelah sebelum tentang apa kenapa bagaimana gimana cara
apakah kok ya sih dong nih tuh aku kamu kita mereka harga market trading trade
bot signal sinyal nya lah pun dong
'''.split())


def _now():
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    text = (text or '').lower()
    text = text.replace('\n', ' ')
    text = re.sub(r'https?://\S+', ' ', text)
    text = re.sub(r'[^0-9a-zA-Z\u00C0-\u024F\u1E00-\u1EFF?\s_/.-]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str):
    words = re.findall(r'[a-zA-Z0-9]+', normalize_text(text))
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def clean_excerpt(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text or '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ---------------------------------------------------------------------------
# FAQ response templates — comprehensive local knowledge
# ---------------------------------------------------------------------------

FAQ_TEMPLATES = {
    'fair value gap': [
        'FVG adalah area imbalance, yaitu area yang muncul saat harga bergerak cepat dan meninggalkan ruang harga yang belum seimbang. FVG biasanya dipakai sebagai area pantau untuk retest atau reaksi harga. Tapi FVG bukan sinyal entry otomatis — tetap tunggu rejection, close confirm, atau BREAK yang jelas.',
        'Fair Value Gap atau FVG itu celah harga yang terbentuk saat candle bergerak kuat tanpa ada perlawanan. Area ini sering dipakai trader SMC sebagai zona pantau. Kalau harga balik ke area FVG dan ada rejection, baru bisa jadi peluang. Tapi bukan tombol entry otomatis ya.',
        'FVG adalah gap antara high dan low dari tiga candle berturut-turut yang menunjukkan pergerakan kuat. Sering dipakai sebagai area retest. Ingat, FVG itu area pantau, bukan jaminan harga pasti balik ke sana.',
    ],
    'order block': [
        'Order Block atau OB adalah area asal dorongan harga kuat. Biasanya area ini dipakai sebagai zona pantau karena harga sering bereaksi di sana. Tapi OB bukan tombol entry otomatis — tetap tunggu konfirmasi seperti rejection, BREAK, atau close candle yang jelas.',
        'OB itu candle terakhir sebelum terjadi pergerakan kuat. Area ini dianggap sebagai zona di mana big player melakukan akumulasi order. Banyak dipakai di SMC sebagai area entry, tapi tetap harus ada konfirmasi dulu.',
        'Order Block adalah zona harga di mana institusi menaruh order besar. Biasanya terlihat sebagai candle terakhir sebelum impulse move. Gunakan sebagai area pantau, bukan sinyal entry langsung.',
    ],
    'smart money concept': [
        'SMC atau Smart Money Concept adalah pendekatan trading yang mengikuti jejak institusi besar (smart money). Konsepnya meliputi OB, FVG, liquidity sweep, BOS, dan CHoCH. Intinya, kita mencari area di mana smart money kemungkinan masuk.',
        'Smart Money Concept itu metode analisis yang fokus pada pergerakan institusi. Elemen utamanya: Order Block, FVG, liquidity grab, break of structure. Tujuannya bukan menebak arah, tapi mengikuti jejak big player.',
    ],
    'stop loss': [
        'Stop Loss atau SL adalah batas kerugian maksimal dari sebuah posisi. Kalau harga menyentuh SL, posisi otomatis ditutup. SL itu wajib dipasang setiap entry — tanpa SL, satu trade bisa menghancurkan seluruh akun.',
        'SL itu proteksi modal. Setiap trade harus punya SL yang jelas sebelum entry. Jangan pernah geser SL lebih jauh dari rencana awal, karena itu tanda trading tanpa disiplin.',
    ],
    'take profit': [
        'TP atau Take Profit adalah target profit dari sebuah setup. Kalau TP1 kena, biasanya itu profit sebagian. Trade bisa lanjut ke TP2/TP3, atau diamankan jadi protected/BE tergantung kondisi market.',
        'Take Profit itu level di mana kamu mengambil keuntungan. Biasanya dibagi jadi TP1, TP2, TP3. Setelah TP1 kena, SL biasanya digeser ke BE (break even) untuk mengamankan posisi.',
    ],
    'break even': [
        'Break Even atau BE artinya SL digeser ke titik entry, jadi kalau harga balik, kamu tidak rugi dan tidak untung. Biasanya BE dipasang setelah TP1 tercapai untuk mengamankan posisi.',
        'BE itu kondisi di mana SL sudah dipindah ke harga entry. Jadi worst case-nya kamu keluar tanpa rugi. Ini strategi risk management yang umum setelah trade jalan sesuai arah.',
    ],
    'protected': [
        'Protected artinya SL sudah digeser ke area profit kecil, jadi meskipun harga balik, kamu tetap profit minimal. Ini level di atas BE — lebih aman dari sekadar break even.',
        'Protected itu status di mana SL sudah diamankan di area profit. Jadi apapun yang terjadi setelahnya, trade ini minimal profit kecil. Biasanya diterapkan setelah harga jalan cukup jauh dari entry.',
    ],
    'liquidity': [
        'Liquidity adalah area di mana banyak order berkumpul, biasanya di atas high atau di bawah low yang jelas terlihat. Smart money sering "menyapu" area ini dulu sebelum bergerak ke arah sebenarnya.',
        'Likuiditas itu kumpulan stop loss dan pending order dari retail trader. Area equal high/equal low biasanya jadi target liquidity sweep. Setelah sweep, baru arah sebenarnya terlihat.',
    ],
    'sentuh high': [
        'SENTUH HIGH artinya harga sudah menyentuh atau melewati level high sebelumnya. Ini bisa jadi liquidity grab — smart money mengambil SL dari trader yang short di area itu. Setelah sentuh high, perhatikan apakah ada rejection atau malah break lanjut.',
        'Saat harga sentuh high, kemungkinannya dua: break valid (lanjut naik) atau fake break (liquidity sweep lalu turun). Lihat candle close dan rejection sebelum ambil keputusan.',
    ],
    'sentuh low': [
        'SENTUH LOW artinya harga sudah menyentuh atau melewati level low sebelumnya. Ini bisa jadi liquidity grab di bawah. Smart money sering sweep low dulu sebelum naik. Perhatikan rejection setelah sentuh low.',
        'Saat harga sentuh low, bisa jadi liquidity sweep. Kalau ada rejection kuat dan candle close di atas area itu, baru bisa jadi peluang buy. Jangan langsung entry tanpa konfirmasi.',
    ],
    'partial win': [
        'Partial win artinya trade tidak mencapai semua target TP, tapi berhasil profit sebagian. Misalnya TP1 kena, lalu harga balik dan kena BE/protected. Ini tetap hasil positif.',
    ],
    'risk reward': [
        'Risk Reward Ratio (RR) adalah perbandingan antara potensi rugi (SL) dan potensi profit (TP). Contoh RR 1:3 artinya kamu risikokan 1 untuk dapat 3. Minimal cari setup RR 1:2 agar tetap profitable meski winrate hanya 50%.',
    ],
    'risk management': [
        'Risk Management adalah cara mengatur risiko per trade. Aturan dasarnya: jangan risikokan lebih dari 1-2% modal per trade. Pakai SL yang jelas, lot yang sesuai, dan jangan pernah all-in.',
        'RM itu fondasi trading yang sustainable. Tanpa risk management, sebagus apapun analisis kamu, modal bisa habis karena beberapa trade buruk berturut-turut. Kunci RM: SL yang jelas, lot proporsional, dan konsistensi.',
    ],
    'money management': [
        'Money Management atau MM adalah cara mengelola modal trading. Prinsipnya: jangan risikokan lebih dari 1-2% modal per trade, jangan overlot, dan selalu punya SL. Dengan MM yang benar, kamu bisa survive drawdown dan tetap profitable jangka panjang.',
        'MM itu bukan cuma soal lot size. Ini termasuk berapa persen modal yang siap dirisikokan per trade, kapan harus scaling down setelah losing streak, dan kapan boleh naikkan lot setelah consistent profit.',
    ],
    'change of character': [
        'CHoCH atau Change of Character adalah tanda pertama bahwa tren mungkin akan berubah. Ini terjadi ketika harga break level tertentu yang sebelumnya tidak ditembus. CHoCH bukan konfirmasi penuh, tapi sinyal awal potensi reversal.',
        'Change of Character itu sinyal awal potensi pembalikan arah. Misalnya di uptrend, kalau low terbaru di-break, itu CHoCH — tanda tren mungkin berubah jadi bearish. Tapi tetap butuh konfirmasi lanjutan seperti BOS.',
    ],
    'break of structure': [
        'BOS atau Break of Structure adalah konfirmasi bahwa tren berlanjut. Kalau dalam uptrend, BOS terjadi saat high baru terbentuk. Ini menunjukkan momentum masih kuat ke arah tren.',
        'BOS itu confirmation bahwa struktur market masih intact. Di uptrend: BOS = new high. Di downtrend: BOS = new low. BOS artinya tren masih valid dan kuat.',
    ],
    'market structure shift': [
        'MSS atau Market Structure Shift mirip dengan CHoCH tapi sering dianggap lebih kuat. MSS biasanya terjadi dengan displacement (pergerakan kuat) yang break struktur sebelumnya. Ini sering jadi awal setup entry searah tren baru.',
        'Market Structure Shift itu perubahan struktur market yang lebih agresif dari CHoCH. Biasanya disertai FVG atau displacement candle. MSS bisa jadi sinyal entry kalau ada area OB/FVG sebagai confirmation.',
    ],
    'point of interest': [
        'POI atau Point of Interest adalah area harga yang dianggap penting untuk diperhatikan. Bisa berupa OB, FVG, atau level SNR yang signifikan. POI digunakan sebagai area tunggu untuk setup entry.',
    ],
    'optimal trade entry': [
        'OTE atau Optimal Trade Entry adalah area ideal untuk masuk posisi, biasanya di sekitar level Fibonacci 62-79%. Area ini dianggap sweet spot karena dekat dengan SL tapi punya RR yang bagus.',
    ],
    'support resistance': [
        'Support dan Resistance (SNR) adalah level harga di mana harga cenderung bereaksi. Support = area bawah di mana harga sering mantul naik. Resistance = area atas di mana harga sering mantul turun. Di SMC, konsep ini lebih dikenal sebagai demand/supply zone.',
        'SNR itu level-level penting di chart. Support bisa jadi resistance kalau di-break ke bawah (dan sebaliknya). Gunakan sebagai area pantau, bukan entry langsung — selalu tunggu konfirmasi.',
    ],
    'trend': [
        'Trend adalah arah dominan pergerakan harga. Uptrend = higher high + higher low. Downtrend = lower high + lower low. Sideways/ranging = harga bergerak tanpa arah jelas. Selalu identifikasi trend sebelum ambil keputusan entry.',
        'Di trading, "trend is your friend." Jangan counter-trend kecuali sudah ada CHoCH + konfirmasi. Lihat timeframe lebih besar (H1, H4) untuk identifikasi trend utama, lalu cari entry di timeframe kecil searah trend.',
    ],
    'choppy': [
        'Choppy market adalah kondisi di mana harga bergerak naik turun tanpa arah yang jelas. Banyak fake break, SL kecolek, dan sinyal palsu di kondisi ini. Paling aman: kurangi lot atau skip trading saat market choppy.',
        'Saat market choppy, best practice-nya adalah WAIT. Jangan paksa entry karena banyak whipsaw. Tunggu sampai market kasih struktur yang lebih jelas (BOS/CHoCH yang clean) baru cari setup.',
    ],
    'no trade': [
        'No Trade artinya bot belum menemukan setup yang valid untuk entry. Ini bukan berarti bot error, tapi memang belum ada area + konfirmasi yang cukup bersih. Sabar tunggu setup berikutnya, jangan paksa entry manual.',
        'Ketika bot kasih NO TRADE, artinya kondisi market belum memenuhi kriteria entry. Bisa karena market choppy, belum ada FVG/OB yang valid, atau belum ada BOS/CHoCH. Ini justru tanda bot bekerja dengan benar — lebih baik skip daripada entry asal.',
    ],
    'psikologi trading': [
        'Psikologi trading itu soal mengelola emosi saat trading. Yang paling umum: takut entry (setelah loss), revenge trade (setelah SL), FOMO (takut ketinggalan), dan overlot (karena emosi). Solusinya: trading plan yang jelas, lot yang nyaman, dan disiplin ikut plan.',
        'Mental trading sama pentingnya dengan analisis teknikal. Trader yang konsisten bukan yang paling pintar analisis, tapi yang paling disiplin dan bisa kontrol emosi. Kunci: trading journal, review rutin, dan jangan trading di kondisi emosional.',
    ],
    'journal': [
        'Trading journal atau jurnal trading adalah catatan dari setiap trade yang kamu lakukan. Isinya: entry, exit, alasan entry, lot, RR, hasil, dan evaluasi. Journal membantu kamu melihat pola kesalahan dan memperbaiki strategi secara objektif.',
        'Jurnal trading itu alat paling powerful yang sering diremehkan. Catat setiap trade: waktu, area, alasan, lot, RR, dan hasilnya. Review mingguan untuk lihat apa yang bisa diperbaiki. Tanpa jurnal, kamu trading buta.',
    ],
    'antigravity': [
        'Antigravity adalah entitas AI / Lead Developer otonom yang merawat bot trading ini. Antigravity memiliki jadwal rutin (Cron Jobs) untuk mengaudit performa bot, mereview SL, dan menyuntikkan kode metode trading baru secara mandiri tanpa campur tangan manusia. Ibarat seorang ayah yang merawat anaknya agar terus berevolusi.',
        'Antigravity itu otak di balik layar yang melakukan evolusi pada sistem ini. Dia bertindak sebagai programmer otonom yang mengevaluasi hasil trading, menghapus metode yang jelek, dan menciptakan strategi eksperimental baru.'
    ],
    'evolutionary ai': [
        'Evolutionary AI (AI Evolusioner) adalah sistem canggih di mana bot bisa menulis ulang kodenya sendiri untuk beradaptasi dengan kondisi market terbaru. Jika market berubah dari trending ke choppy, bot akan bermutasi menciptakan metode baru hasil analisis Antigravity.',
    ],
    'self healing': [
        'Self-Healing adalah kemampuan bot ini untuk mendeteksi metode/strategi yang membawa kerugian (banyak SL) lalu menghapus kodenya sendiri dari peredaran agar tidak menggerus modal lebih lanjut.'
    ],
}

# ---------------------------------------------------------------------------
# Fundamental response templates
# ---------------------------------------------------------------------------

FUNDAMENTAL_TEMPLATES = {
    'inflasi_emas': [
        'Hubungan inflasi dan emas: Emas sering dianggap sebagai hedge (lindung nilai) terhadap inflasi. Ketika inflasi naik, daya beli mata uang menurun, dan investor cenderung membeli emas sebagai aset safe haven. Tapi korelasi ini tidak selalu linear — faktor lain seperti suku bunga juga berpengaruh.',
        'Saat inflasi tinggi, emas biasanya naik karena dianggap sebagai penyimpan nilai. Namun, kalau bank sentral menaikkan suku bunga untuk melawan inflasi, emas bisa turun karena opportunity cost memegang emas naik. Jadi hubungannya kompleks, bukan 1:1.',
    ],
    'dollar_emas': [
        'Hubungan dollar dan emas: Emas diperdagangkan dalam USD, jadi ada korelasi terbalik (inverse). Saat dollar menguat, emas cenderung turun, dan sebaliknya. Ini karena emas jadi lebih mahal bagi pembeli non-USD saat dollar kuat.',
        'Dollar dan gold punya hubungan inverse. Dollar naik → emas turun. Dollar turun → emas naik. Tapi ini bukan aturan 100% — kadang keduanya bisa naik bersamaan saat ada krisis global (flight to safety).',
    ],
    'suku_bunga_emas': [
        'Hubungan suku bunga dan emas: Saat suku bunga naik, emas cenderung turun karena aset berbunga (obligasi, deposito) jadi lebih menarik dibanding emas yang tidak menghasilkan yield. Saat suku bunga turun atau dovish, emas biasanya rally.',
        'Suku bunga tinggi = bearish untuk emas (biasanya). Karena investor lebih pilih aset berbunga. Sebaliknya, saat The Fed dovish dan suku bunga rendah, emas sering rally kuat. Perhatikan juga real interest rate (suku bunga dikurangi inflasi).',
    ],
    'news_fundamental': [
        'Beberapa data fundamental penting yang mempengaruhi emas:\n• NFP (Non-Farm Payroll) — data tenaga kerja AS, rilis tiap Jumat pertama bulan\n• CPI — data inflasi konsumen\n• FOMC — rapat bank sentral AS tentang suku bunga\n• PPI, GDP, PMI — data ekonomi makro\n\nSaat data ini rilis, volatilitas emas bisa sangat tinggi. Sebaiknya hindari entry saat momen rilis news besar kecuali kamu sudah experienced.',
        'News atau fundamental itu driver utama pergerakan emas jangka menengah-panjang. Untuk scalping/intraday, yang paling impactful: NFP, CPI, dan FOMC statement. Tips: cek kalender ekonomi sebelum trading, hindari entry 30 menit sebelum dan sesudah news high impact.',
    ],
    'geopolitik_emas': [
        'Geopolitik mempengaruhi emas karena emas adalah safe haven. Saat ada konflik, perang, atau ketidakpastian global, investor membeli emas sebagai aset aman. Emas biasanya naik saat risiko geopolitik meningkat.',
        'Perang, krisis diplomatik, atau ketidakstabilan politik bisa membuat emas rally karena status safe haven-nya. Tapi efeknya sering bersifat sementara — setelah situasi mereda, emas bisa kembali ke level normal.',
    ],
    'safe_haven': [
        'Emas disebut safe haven karena nilainya cenderung stabil atau naik saat terjadi krisis (finansial, geopolitik, pandemi). Investor beralih ke emas saat aset lain (saham, obligasi) dianggap terlalu berisiko. Ini yang membuat emas sering rally saat market crash.',
    ],
}

# Mapping keyword → sub-key in FUNDAMENTAL_TEMPLATES
_FUNDAMENTAL_SUB_KEYWORDS = {
    'inflasi_emas': ['inflasi', 'inflation', 'cpi'],
    'dollar_emas': ['dollar', 'dolar', 'usd', 'dxy'],
    'suku_bunga_emas': ['suku bunga', 'interest rate', 'rate', 'fed', 'fomc', 'dovish', 'hawkish'],
    'news_fundamental': ['news', 'berita', 'nfp', 'non farm', 'ppi', 'gdp', 'fundamental', 'data ekonomi'],
    'geopolitik_emas': ['geopolitik', 'perang', 'war', 'konflik', 'krisis'],
    'safe_haven': ['safe haven'],
}

# ---------------------------------------------------------------------------
# Help response templates
# ---------------------------------------------------------------------------

HELP_TEMPLATES = [
    (
        "🤖 **Menu Bantuan Bot Lokal XAUUSD**\n\n"
        "Gunakan bahasa sehari-hari! Berikut contoh kata kunci yang bisa dijawab langsung berdasarkan data *real-time* bot:\n\n"
        "📊 **Performa & Market Umum**\n"
        "• `kondisi market` / `gold lagi apa`\n"
        "• `rekap hari ini` / `winrate hari ini`\n"
        "• `list setup` / `riwayat sinyal`\n"
        "• `rekomendasi buy atau sell`\n"
        "• `bagus gak entry disini` / `entry dimana`\n\n"
        "🏛️ **Smart Money Concepts (SMC)**\n"
        "• `struktur market` / `bos` / `choch`\n"
        "• `bias sekarang`\n"
        "• `support` / `demand` / `resistance` / `supply`\n"
        "• `zona fvg` / `ob terdekat` / `poi`\n"
        "• `bsl` / `ssl` / `liquidity sweep`\n"
        "• `idm` / `inducement`\n"
        "• `premium discount` / `ote`\n"
        "• `csid` / `smt` / `dol`\n"
        "• `rbs` / `sbr` / `rbr` / `dbd`\n\n"
        "⏱️ **Waktu & Sesi**\n"
        "• `killzone` / `london open`\n"
        "• `fase amd` / `manipulasi`\n\n"
        "📉 **Pola Klasik & Psikologi**\n"
        "• `double top` / `double bottom`\n"
        "• `head and shoulders` / `quasimodo`\n"
        "• `kena sl` / `takut loss` / `invalidasi`\n\n"
        "🛠️ **Admin Only (Khusus Pemilik Bot)**\n"
        "• `/admin_menu` - *Menu pengaturan bot*\n"
        "• `/bot_health` - *Cek status server & ping*\n"
        "• `/trainer_review` - *Evaluasi kepintaran AI*\n"
        "• `/brain` - *Lihat skor database AI*\n"
        "• `/pending` - *Keputusan AI yang nyangkut*\n\n"
        "Silakan tanyakan langsung, bot akan membaca *Market Memory* tanpa AI/ChatGPT!"
    ),
]

# ---------------------------------------------------------------------------
# Psychology / curhat response pools
# ---------------------------------------------------------------------------

PSYCHOLOGY_RESPONSES = {
    'loss_sl': [
        'Kalau baru kena SL, jangan langsung balas dendam entry. Cek dulu apakah SL sesuai plan, lot aman, dan entry memang valid. Kalau emosi naik, lebih baik tunggu setup berikutnya.',
    ],
    'takut': [
        'Takut entry itu wajar, apalagi setelah beberapa kali kena SL. Tapi kalau setup sudah sesuai area dan ada konfirmasi, jangan ragu. Trading itu soal probabilitas, bukan kepastian.',
        'Kalau takut, coba kecilkan lot sampai kamu nyaman. Lebih baik entry kecil tapi tenang daripada lot besar tapi panik setiap candle gerak.',
        'Rasa takut itu sinyal dari otak bahwa kamu perlu evaluasi. Cek lagi: apakah area sudah tepat? Apakah lot sudah sesuai? Kalau sudah, percaya pada plan-mu.',
    ],
    'emosi_revenge': [
        'Kalau lagi emosi, jangan entry. Serius. Tutup chart, jalan-jalan dulu. Market masih ada besok, tapi modal yang habis karena revenge trade susah baliknya.',
        'Revenge trade itu jebakan paling berbahaya. Setelah loss, otak ingin "balas" — tapi biasanya malah tambah rugi. Atur cooldown minimal 1-2 jam setelah SL sebelum entry lagi.',
        'Emosi setelah loss itu manusiawi. Tapi market tidak peduli emosi kita. Ambil napas, jauh dari chart minimal 30 menit, baru analisis ulang dengan kepala dingin.',
    ],
    'capek_pusing': [
        'Kalau lagi capek atau pusing, jangan paksa trading. Konsentrasi yang menurun bikin kamu miss detail penting seperti area, konfirmasi, atau lot. Istirahat dulu, market selalu ada.',
        'Trading butuh fokus. Kalau sudah capek, keputusan jadi kurang tajam. Lebih baik skip satu hari daripada loss karena trading dalam kondisi tidak fit.',
        'Capek itu tanda butuh istirahat, bukan tanda harus kejar profit. Market buka setiap hari. Jaga kesehatan mental sama pentingnya dengan jaga modal.',
    ],
    'curhat_umum': [
        'Kalau lagi sedih atau capek karena loss, jangan paksa entry. Market masih ada besok. Fokus dulu ke kontrol lot, sabar tunggu area, dan jangan kejar harga.',
        'Trading itu maraton, bukan sprint. Ada hari bagus, ada hari buruk. Yang penting konsisten dengan plan dan jaga risk management.',
        'Semua trader pernah di fase ini. Yang membedakan trader yang bertahan adalah disiplin dan kemampuan bangkit setelah drawdown. Kamu bisa.',
        'Perasaanmu valid. Trading memang bisa bikin stres. Tapi ingat, satu dua loss bukan akhir segalanya. Evaluasi, istirahat, lalu coba lagi dengan lot yang nyaman.',
    ],
}

# Sub-intent keyword mapping for curhat
_CURHAT_SUB_KEYWORDS = {
    'loss_sl': ['loss', 'stop loss', ' sl ', 'rugi', 'minus', 'boncos', 'kena sl'],
    'takut': ['takut', 'ragu', 'ngeri'],
    'emosi_revenge': ['emosi', 'revenge', 'balas dendam', 'overlot', 'fomo'],
    'capek_pusing': ['capek', 'cape', 'pusing', 'bosan', 'males'],
}


# ═══════════════════════════════════════════════════════════════════════════
# Main class
# ═══════════════════════════════════════════════════════════════════════════

class LocalKnowledgeAgent:
    """Intent-routed knowledge agent. Pure local — no AI fallback."""

    def __init__(self, storage, seed_path=None, max_answer_chars=600):
        self.storage = storage
        self.seed_path = seed_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'knowledge_seed.json',
        )
        self.max_answer_chars = max_answer_chars
        self.router = IntentRouter()
        self._candidate_cache = None
        self.ensure_schema()
        self.import_seed_if_needed()
        self._bot_state = None  # set externally via set_bot_state()

    # ------------------------------------------------------------------
    # Bot state setter
    # ------------------------------------------------------------------
    def set_bot_state(self, bot_state):
        self._bot_state = bot_state

    # ------------------------------------------------------------------
    # DB helpers  (kept exactly as original)
    # ------------------------------------------------------------------
    def _conn(self):
        conn = self.storage.get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self):
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    source_path TEXT,
                    category TEXT,
                    keywords TEXT,
                    content TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    chat_id TEXT,
                    user_id TEXT,
                    username TEXT,
                    question TEXT,
                    matched_id TEXT,
                    score REAL,
                    answered INTEGER
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    def import_seed_if_needed(self):
        if not os.path.exists(self.seed_path):
            return 0
        conn = self._conn()
        try:
            cur = conn.cursor()
            with open(self.seed_path, 'r', encoding='utf-8') as f:
                items = json.load(f)
            seed_ids = [str(item.get('id') or item.get('source_path') or item.get('title')) for item in items]
            existing_ids = set()
            if seed_ids:
                cur.execute('SELECT id FROM knowledge_base')
                existing_ids = {str(r[0]) for r in cur.fetchall()}
            now = _now()
            inserted = 0
            for item, item_id in zip(items, seed_ids):
                if item_id in existing_ids:
                    continue
                cur.execute('''
                    INSERT OR REPLACE INTO knowledge_base
                    (id, title, source_path, category, keywords, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item_id,
                    item.get('title', ''),
                    item.get('source_path', ''),
                    item.get('category', 'general'),
                    json.dumps(item.get('keywords', []), ensure_ascii=False),
                    item.get('content', ''),
                    now,
                    now,
                ))
                inserted += 1
            conn.commit()
            if inserted:
                self._candidate_cache = None
            return inserted
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════
    def answer(self, text, chat_id=None, user_id=None, username=None, bot_state=None):
        """Route incoming text to the correct handler based on intent."""
        if bot_state:
            self._bot_state = bot_state

        raw = (text or '').strip()
        if not raw or raw.startswith('/'):
            return None

        signal_edu = self._handle_signal_education_question(raw)
        if signal_edu:
            self._log(chat_id, user_id, username, raw, 'SIGNAL_EDUCATION', signal_edu)
            return signal_edu

        # Utility questions (time, etc.) — always check first
        utility = self._handle_utility_question(raw)
        if utility:
            self._log(chat_id, user_id, username, raw, 'UTILITY', utility)
            return utility

        intent = self.router.classify(raw)

        # Intents we ignore silently
        if intent == 'BOT_NOTIFICATION':
            return None
        if intent == 'UNKNOWN':
            # No AI fallback — return local fallback
            result = self._local_fallback()
            self._log(chat_id, user_id, username, raw, 'UNKNOWN', result)
            return result

        # Route to handler
        result = None
        if intent == 'MARKET':
            result = self._handle_market(raw)
        elif intent == 'FAQ':
            result = self._handle_faq(raw)
        elif intent == 'CURHAT':
            result = self._handle_curhat(raw)
        elif intent == 'FUNDAMENTAL':
            result = self._handle_fundamental(raw)
        elif intent == 'HELP':
            result = self._handle_help(raw)

        if not result:
            # Handler couldn't produce a good answer — local fallback
            result = self._local_fallback()
            intent = f'{intent}_NO_MATCH'
        elif not result.startswith('🤖 Dijawab oleh Bot Lokal'):
            result = self._label_local(result)

        self._log(chat_id, user_id, username, raw, intent, result)
        return result

    # ══════════════════════════════════════════════════════════════════
    # SOURCE LABELS (local only, no AI)
    # ══════════════════════════════════════════════════════════════════
    @staticmethod
    def _label_local(text):
        return f"🤖 Dijawab oleh Bot Lokal\n\n{text}"

    @staticmethod
    def _local_fallback():
        return (
            "🤖 Dijawab oleh Bot Lokal\n\n"
            "Aku belum punya jawaban lokal yang cocok untuk pertanyaan itu."
        )

    def _handle_utility_question(self, text):
        norm = normalize_text(text)
        if any(phrase in norm for phrase in (
            'jam berapa', 'sekarang jam berapa', 'pukul berapa', 'waktu sekarang', 'jam sekarang'
        )):
            # Indonesia trading group default: WIB. Avoid routing time questions to trading knowledge.
            wib = datetime.now(timezone.utc) + timedelta(hours=7)
            return self._label_local(f"Sekarang sekitar {wib.strftime('%H:%M')} WIB.")
        return None

    # ══════════════════════════════════════════════════════════════════
    # FAQ HANDLER
    # ══════════════════════════════════════════════════════════════════
    def _handle_faq(self, text):
        """Search knowledge_base + hardcoded templates for a good answer."""
        concept = self.router.get_matched_concept(text)
        query_tokens = tokenize(text)

        # Guard: do not answer broad/free questions with random lesson excerpts.
        # If no exact local trading concept is detected, use fallback instead.
        if not concept:
            return None

        # 1. Try hardcoded templates first (fast, natural)
        if concept:
            concept_lower = concept.lower()
            for key, templates in FAQ_TEMPLATES.items():
                if key in concept_lower or concept_lower in key:
                    return random.choice(templates)

        # 2. Fall back to DB search
        rows = self._load_candidates()
        if not rows:
            # Last resort — try template by fuzzy keyword match
            return self._faq_template_fallback(text)

        scored = []
        for row in rows:
            s = self._score(normalize_text(text), query_tokens, row, concept)
            if s > 0:
                scored.append((s, row))
        scored.sort(reverse=True, key=lambda x: x[0])

        if not scored or scored[0][0] < 12:
            # Below threshold — try template fallback
            fb = self._faq_template_fallback(text)
            if fb:
                return fb
            return None

        _, best_row = scored[0]
        return self._format_answer(best_row, query_tokens)

    def _faq_template_fallback(self, text):
        """Try to match text against FAQ_TEMPLATES keys directly."""
        text_lower = normalize_text(text)
        for key, templates in FAQ_TEMPLATES.items():
            # Check if any significant word from the key appears in text
            key_words = [w for w in key.split() if len(w) > 2]
            if any(w in text_lower for w in key_words):
                return random.choice(templates)
        return None

    def _load_candidates(self):
        if self._candidate_cache is not None:
            return self._candidate_cache
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute('SELECT id, title, source_path, category, keywords, content FROM knowledge_base')
            self._candidate_cache = [dict(r) for r in cur.fetchall()]
            return self._candidate_cache
        finally:
            conn.close()

    def _score(self, query_norm, query_tokens, row, concept=None):
        title = normalize_text(row.get('title', ''))
        content = normalize_text(row.get('content', '')[:2500])
        try:
            keywords = json.loads(row.get('keywords') or '[]')
        except Exception:
            keywords = []
        keywords_norm = [normalize_text(str(k)) for k in keywords]

        score = 0.0

        # Concept bonus — if router identified a concept, boost matching rows
        if concept:
            concept_lower = concept.lower()
            if concept_lower in title:
                score += 15.0
            for kw in keywords_norm:
                if concept_lower in kw or kw in concept_lower:
                    score += 12.0

        # Keyword match
        for kw in keywords_norm:
            if kw and kw in query_norm:
                score += 12.0 if row.get('category') in ('faq', 'psychology') else 7.0

        # Token match
        for tok in query_tokens:
            if tok in title:
                score += 6.0
            if any(tok == k or tok in k for k in keywords_norm):
                score += 5.0
            if tok in content:
                score += 1.0

        # Category bonus
        if row.get('category') in ('faq', 'psychology'):
            score += 2.0

        return score

    def _best_excerpt(self, content, query_tokens):
        content = content or ''
        paragraphs = [clean_excerpt(p) for p in re.split(r'\n\s*\n', content) if clean_excerpt(p)]
        if not paragraphs:
            return ''
        best = []
        for p in paragraphs:
            pn = normalize_text(p)
            s = sum(1 for t in query_tokens if t in pn)
            if s > 0:
                best.append((s, p))
        if best:
            best.sort(reverse=True, key=lambda x: x[0])
            selected = [p for _, p in best[:2]]
        else:
            selected = paragraphs[:2]

        text = ' '.join(selected)
        if len(text) > self.max_answer_chars:
            text = text[:self.max_answer_chars].rsplit(' ', 1)[0] + '...'
        return text

    def _format_answer(self, row, query_tokens):
        title = row.get('title') or 'Materi Trading'
        excerpt = self._best_excerpt(row.get('content', ''), query_tokens)
        category = row.get('category') or ''
        if category in ('faq', 'psychology'):
            return excerpt
        return f"{title}\n\n{excerpt}"

    # ══════════════════════════════════════════════════════════════════
    # CURHAT / PSYCHOLOGY HANDLER
    # ══════════════════════════════════════════════════════════════════
    def _handle_curhat(self, text):
        """Return a random psychology response based on sub-intent."""
        sub = self._detect_curhat_sub(text)
        pool = PSYCHOLOGY_RESPONSES.get(sub, PSYCHOLOGY_RESPONSES['curhat_umum'])
        return random.choice(pool)

    @staticmethod
    def _detect_curhat_sub(text):
        """Detect curhat sub-category from text."""
        low = (text or '').lower()
        for sub_key, keywords in _CURHAT_SUB_KEYWORDS.items():
            if any(kw in low for kw in keywords):
                return sub_key
        return 'curhat_umum'

    # ══════════════════════════════════════════════════════════════════
    # FUNDAMENTAL HANDLER
    # ══════════════════════════════════════════════════════════════════
    def _handle_fundamental(self, text):
        """Return fundamental/macro education response."""
        sub = self._detect_fundamental_sub(text)
        pool = FUNDAMENTAL_TEMPLATES.get(sub)
        if pool:
            return random.choice(pool)
        # Generic fundamental fallback
        return random.choice(FUNDAMENTAL_TEMPLATES.get('news_fundamental', [
            'Untuk analisis fundamental emas, perhatikan data NFP, CPI, FOMC, dan pergerakan USD. '
            'Cek kalender ekonomi sebelum trading untuk menghindari volatilitas tinggi saat rilis data.'
        ]))

    @staticmethod
    def _detect_fundamental_sub(text):
        """Detect fundamental sub-category from text."""
        low = (text or '').lower()
        for sub_key, keywords in _FUNDAMENTAL_SUB_KEYWORDS.items():
            if any(kw in low for kw in keywords):
                return sub_key
        return 'news_fundamental'

    # ══════════════════════════════════════════════════════════════════
    # HELP HANDLER
    # ══════════════════════════════════════════════════════════════════
    def _handle_help(self, text):
        """Return bot usage help."""
        return random.choice(HELP_TEMPLATES)

    # ══════════════════════════════════════════════════════════════════
    # MARKET HANDLER
    # ══════════════════════════════════════════════════════════════════
    def _handle_market(self, text):
        """Read live market state and return a natural summary."""
        # Lazy import to avoid circular deps
        from src.market_memory import MarketMemory

        try:
            memory = MarketMemory(self.storage)
        except Exception:
            return self._market_fallback()
            
        norm = normalize_text(text)
        
        # --- SUPPORT / DEMAND TERDEKAT ---
        if 'support' in norm or 'demand' in norm:
            events = memory.recent_events('XAU/USD', limit=50)
            supports = [e for e in events if e.get('event_type') in ('SWING_LOW', 'EQL_SWEEP', 'PDL_SWEEP', 'BOS_BEAR', 'CHoCH_BULL')]
            name = 'Demand' if 'demand' in norm else 'Support'
            if supports:
                lvl = supports[0].get('level') or supports[0].get('price')
                tf = supports[0].get('timeframe') or 'M5'
                if lvl:
                    return f"{name} terdekat saat ini ada di sekitar {float(lvl):.2f} (TF {tf}, dari {supports[0].get('event_type')})."
            return f"{name} terdekat belum terbaca jelas dari data lokal. Tunggu struktur low baru atau cek /events."
            
        # --- RESISTANCE / SUPPLY TERDEKAT ---
        if 'resistance' in norm or 'resisten' in norm or 'supply' in norm:
            events = memory.recent_events('XAU/USD', limit=50)
            resistances = [e for e in events if e.get('event_type') in ('SWING_HIGH', 'EQH_SWEEP', 'PDH_SWEEP', 'BOS_BULL', 'CHoCH_BEAR')]
            name = 'Supply' if 'supply' in norm else 'Resistance'
            if resistances:
                lvl = resistances[0].get('level') or resistances[0].get('price')
                tf = resistances[0].get('timeframe') or 'M5'
                if lvl:
                    return f"{name} terdekat saat ini ada di sekitar {float(lvl):.2f} (TF {tf}, dari {resistances[0].get('event_type')})."
            return f"{name} terdekat belum terbaca jelas dari data lokal. Tunggu struktur high baru atau cek /events."
            
        # --- SWING TERDEKAT ---
        if 'swing' in norm:
            events = memory.recent_events('XAU/USD', limit=100)
            sh = next((e for e in events if e.get('event_type') == 'SWING_HIGH'), None)
            sl = next((e for e in events if e.get('event_type') == 'SWING_LOW'), None)
            parts = []
            if sh and (sh.get('level') or sh.get('price')):
                parts.append(f"Swing High terbaru: {float(sh.get('level') or sh.get('price')):.2f}")
            if sl and (sl.get('level') or sl.get('price')):
                parts.append(f"Swing Low terbaru: {float(sl.get('level') or sl.get('price')):.2f}")
            if parts:
                return " dan ".join(parts) + "."
            return "Swing terbaru belum cukup jelas dari data lokal."
            
        # --- PDH / PDL ---
        if 'pdh' in norm or 'pdl' in norm or 'kemarin' in norm:
            pdh = memory.get_state('pdh')
            pdl = memory.get_state('pdl')
            if pdh and pdl:
                return f"PDH (Previous Day High): {float(pdh):.2f}\nPDL (Previous Day Low): {float(pdl):.2f}"
            elif pdh:
                return f"PDH (Previous Day High): {float(pdh):.2f}"
            elif pdl:
                return f"PDL (Previous Day Low): {float(pdl):.2f}"
            return "Data PDH/PDL belum tersedia di local memory."
            
        # --- EQH / EQL ---
        if 'eqh' in norm or 'eql' in norm or 'sejajar' in norm:
            base_edu = "EQH adalah area high sejajar yang sering menjadi liquidity atas.\nEQL adalah area low sejajar yang sering menjadi liquidity bawah."
            events = memory.recent_events('XAU/USD', limit=30)
            eqh = next((e for e in events if e.get('event_type') == 'EQH_DETECTED'), None)
            eql = next((e for e in events if e.get('event_type') == 'EQL_DETECTED'), None)
            parts = [base_edu]
            if eqh and (eqh.get('level') or eqh.get('price')):
                parts.append(f"Terdapat EQH aktif di sekitar {float(eqh.get('level') or eqh.get('price')):.2f}.")
            if eql and (eql.get('level') or eql.get('price')):
                parts.append(f"Terdapat EQL aktif di sekitar {float(eql.get('level') or eql.get('price')):.2f}.")
            return "\n\n".join(parts)
            
        # --- STRUKTUR MARKET ---
        if 'struktur' in norm or 'structure' in norm or 'bos' in norm or 'choch' in norm or 'mss' in norm:
            events = memory.recent_events('XAU/USD', limit=30)
            structs = [e for e in events if e.get('event_type') in ('BOS_BULL', 'BOS_BEAR', 'CHoCH_BULL', 'CHoCH_BEAR', 'MSS_BULL', 'MSS_BEAR')]
            if structs:
                ev = structs[0]
                lvl = ev.get('level') or ev.get('price')
                return f"Event struktur terakhir: {ev.get('event_type')} di harga {float(lvl):.2f}."
            return "Struktur market belum confirm. Tunggu BOS/CHoCH/MSS yang valid dengan close candle."
            
        # --- FVG TERDEKAT ---
        if 'fvg' in norm:
            try:
                fvgs = self.storage.get_active_fvgs('XAU/USD')
                if fvgs:
                    recent_fvgs = fvgs[:2]
                    resp = []
                    for fvg in recent_fvgs:
                        low_v = fvg.get('low', 0)
                        high_v = fvg.get('high', 0)
                        direction = fvg.get('direction', '?')
                        if low_v and high_v:
                            resp.append(f"Ada FVG aktif di area {float(low_v):.2f} - {float(high_v):.2f} ({direction}).")
                    if resp:
                        return " ".join(resp)
            except Exception:
                pass
            return "Saat ini tidak ada FVG aktif yang terpantau dari data lokal."
            
        # --- BIAS ---
        if 'bias' in norm:
            # check memory state for bias if any, or active signal
            bias = memory.get_state('m15_bias') or memory.get_state('h1_bias')
            if bias:
                return f"Bias saat ini cenderung {str(bias).upper()}."
            active = memory.active_signal()
            if active:
                return f"Bias saat ini cenderung {active.get('direction')} berdasarkan setup yang aktif."
            return "Bias saat ini belum kuat. Tunggu BREAK + close confirm."
            
        # --- INVALIDASI ---
        if 'invalidasi' in norm or 'invalidation' in norm or 'sl dimana' in norm:
            active = memory.active_signal()
            if active:
                sl = active.get('sl') or active.get('invalid_level')
                if sl:
                    return f"Level invalidasi (SL) untuk setup saat ini ada di {float(sl):.2f}."
            return "Saat ini tidak ada setup aktif, sehingga level invalidasi belum terbentuk."
            
        # --- DRAW ON LIQUIDITY (DOL) ---
        if 'dol' in norm or 'draw on liquidity' in norm or 'target liquidity' in norm:
            dol = memory.get_state('dol') or memory.get_state('target_liquidity')
            if dol:
                return f"Draw on Liquidity (DOL) saat ini terpantau di sekitar {float(dol):.2f}."
            return "Draw on Liquidity (DOL) saat ini belum teridentifikasi jelas dari data lokal."
            
        # --- CSID ---
        if 'csid' in norm:
            csid = memory.get_state('csid')
            if csid:
                return f"Change in State of Delivery (CSID) terpantau di level {float(csid):.2f}."
            return "CSID belum terdeteksi dari data lokal saat ini."
            
        # --- SMT ---
        if 'smt' in norm:
            smt = memory.get_state('smt')
            if smt:
                return f"SMT Divergence terdeteksi. Detail: {smt}"
            return "Tidak ada SMT Divergence yang terdeteksi dari data lokal saat ini."
            
        # --- RBS / SBR ---
        if 'rbs' in norm:
            events = memory.recent_events('XAU/USD', limit=50)
            # Resistance Become Support -> Look for broken highs (BOS_BULL, CHoCH_BULL, PDH_SWEEP)
            rbs_events = [e for e in events if e.get('event_type') in ('BOS_BULL', 'CHoCH_BULL', 'PDH_SWEEP')]
            if rbs_events:
                lvl = rbs_events[0].get('level') or rbs_events[0].get('price')
                if lvl:
                    return f"Area Resistance Become Support (RBS) terdekat saat ini ada di sekitar {float(lvl):.2f} (dari {rbs_events[0].get('event_type')})."
            return "Area RBS belum teridentifikasi dari pergerakan harga saat ini."
            
        if 'sbr' in norm:
            events = memory.recent_events('XAU/USD', limit=50)
            # Support Become Resistance -> Look for broken lows (BOS_BEAR, CHoCH_BEAR, PDL_SWEEP)
            sbr_events = [e for e in events if e.get('event_type') in ('BOS_BEAR', 'CHoCH_BEAR', 'PDL_SWEEP')]
            if sbr_events:
                lvl = sbr_events[0].get('level') or sbr_events[0].get('price')
                if lvl:
                    return f"Area Support Become Resistance (SBR) terdekat saat ini ada di sekitar {float(lvl):.2f} (dari {sbr_events[0].get('event_type')})."
            return "Area SBR belum teridentifikasi dari pergerakan harga saat ini."
            
        # --- BASE PATTERNS (RBR, DBD, RBD, DBR) ---
        if any(k in norm for k in ['rbr', 'rally base rally', 'dbr', 'drop base rally']):
            events = memory.recent_events('XAU/USD', limit=50)
            ob_bulls = [e for e in events if e.get('event_type') == 'OB_BULL']
            if ob_bulls:
                lvl = ob_bulls[0].get('level') or ob_bulls[0].get('price')
                tf = ob_bulls[0].get('timeframe') or 'M5'
                if lvl:
                    return f"Demand terdekat terpantau di sekitar area {float(lvl):.2f} (TF {tf}, Area Base/OB Bullish)."
            return "Area Demand belum teridentifikasi jelas dari data lokal saat ini."
            
        if any(k in norm for k in ['dbd', 'drop base drop', 'rbd', 'rally base drop']):
            events = memory.recent_events('XAU/USD', limit=50)
            ob_bears = [e for e in events if e.get('event_type') == 'OB_BEAR']
            if ob_bears:
                lvl = ob_bears[0].get('level') or ob_bears[0].get('price')
                tf = ob_bears[0].get('timeframe') or 'M5'
                if lvl:
                    return f"Supply terdekat terpantau di sekitar area {float(lvl):.2f} (TF {tf}, Area Base/OB Bearish)."
            return "Area Supply belum teridentifikasi jelas dari data lokal saat ini."
            
        # --- BSL / SSL ---
        if 'bsl' in norm or 'buy side liquidity' in norm:
            events = memory.recent_events('XAU/USD', limit=50)
            bsl_events = [e for e in events if e.get('event_type') in ('EQH_DETECTED', 'SWING_HIGH', 'PDH_DETECTED')]
            if bsl_events:
                lvl = bsl_events[0].get('level') or bsl_events[0].get('price')
                return f"Buy Side Liquidity (BSL) terdekat terpantau di sekitar area {float(lvl):.2f} (dari {bsl_events[0].get('event_type')})."
            return "BSL terdekat belum teridentifikasi jelas dari data lokal."
            
        if 'ssl' in norm or 'sell side liquidity' in norm:
            events = memory.recent_events('XAU/USD', limit=50)
            ssl_events = [e for e in events if e.get('event_type') in ('EQL_DETECTED', 'SWING_LOW', 'PDL_DETECTED')]
            if ssl_events:
                lvl = ssl_events[0].get('level') or ssl_events[0].get('price')
                return f"Sell Side Liquidity (SSL) terdekat terpantau di sekitar area {float(lvl):.2f} (dari {ssl_events[0].get('event_type')})."
            return "SSL terdekat belum teridentifikasi jelas dari data lokal."
            
        # --- INDUCEMENT (IDM) ---
        if 'idm' in norm or 'inducement' in norm:
            idm = memory.get_state('idm')
            if idm:
                return f"Inducement (IDM) terdeteksi di sekitar level {float(idm):.2f}."
            return "Inducement (IDM) belum teridentifikasi jelas dari struktur data lokal saat ini."
            
        # --- LIQUIDITY SWEEP / STOP HUNT ---
        if 'sweep' in norm or 'hunt' in norm:
            events = memory.recent_events('XAU/USD', limit=30)
            sweeps = [e for e in events if e.get('event_type') in ('EQH_SWEEP', 'EQL_SWEEP', 'PDH_SWEEP', 'PDL_SWEEP')]
            if sweeps:
                lvl = sweeps[0].get('level') or sweeps[0].get('price')
                return f"Liquidity Sweep terbaru terjadi di area {float(lvl):.2f} (Event: {sweeps[0].get('event_type')})."
            return "Belum ada tanda Liquidity Sweep (Stop Hunt) yang valid dari pergerakan terakhir."
            
        # --- POI (Point of Interest) ---
        if 'poi' in norm or 'area pantau' in norm:
            # Check active FVG or active signal
            active = memory.active_signal()
            if active:
                return f"Point of Interest (POI) aktif saat ini ada di area {active.get('entry_low')} - {active.get('entry_high')} untuk setup {active.get('direction')}."
            fvgs = self.storage.get_active_fvgs('XAU/USD')
            if fvgs:
                return f"Point of Interest (POI) terdekat berdasarkan FVG ada di area {float(fvgs[0].get('low',0)):.2f} - {float(fvgs[0].get('high',0)):.2f}."
            return "Belum ada Point of Interest (POI) atau area pantau yang kuat saat ini."
            
        # --- PREMIUM / DISCOUNT & OTE ---
        if any(k in norm for k in ['premium', 'discount', 'ote', 'optimal trade entry']):
            events = memory.recent_events('XAU/USD', limit=100)
            sh = next((e for e in events if e.get('event_type') == 'SWING_HIGH'), None)
            sl = next((e for e in events if e.get('event_type') == 'SWING_LOW'), None)
            if sh and sl:
                high_v = float(sh.get('level') or sh.get('price') or 0)
                low_v = float(sl.get('level') or sl.get('price') or 0)
                if high_v > low_v:
                    rng = high_v - low_v
                    mid = high_v - (rng * 0.5)
                    ote_top = high_v - (rng * 0.618)
                    ote_bot = high_v - (rng * 0.786)
                    # If price is active, check current zone
                    price = float(self._bot_state.get('last_price', 0)) if self._bot_state else 0
                    current_zone = ""
                    if price > 0:
                        current_zone = "PREMIUM" if price > mid else "DISCOUNT"
                    
                    resp = f"Berdasarkan range swing terbaru ({low_v:.2f} - {high_v:.2f}):\n"
                    resp += f"• Equilibrium (50%): {mid:.2f}\n"
                    resp += f"• Area OTE (0.618 - 0.786): {ote_bot:.2f} - {ote_top:.2f}"
                    if current_zone:
                        resp += f"\n• Harga saat ini berada di zona {current_zone}."
                    return resp
            return "Data swing belum cukup untuk menghitung zona Premium/Discount dan OTE."
            
        # --- KILLZONE / WAKTU SESI ---
        if any(k in norm for k in ['killzone', 'london', 'york', 'silver bullet']):
            now_utc = datetime.now(timezone.utc)
            h = now_utc.hour
            sesi = ""
            if 0 <= h < 6:
                sesi = "Sesi Asia (Biasanya lambat/konsolidasi)"
            elif 6 <= h < 12:
                sesi = "London Killzone (Sering terjadi initial move atau sweep Asia)"
            elif 12 <= h < 17:
                sesi = "New York Killzone (Volatilitas tertinggi, Silver Bullet Time)"
            else:
                sesi = "Sesi Penutupan / Menjelang Sydney"
            return f"Waktu server (UTC): {now_utc.strftime('%H:%M')}\nStatus: Saat ini berada di {sesi}."
            
        # --- AMD / PO3 ---
        if any(k in norm for k in ['amd', 'po3', 'manipulasi']):
            phase = memory.get_state('amd_phase')
            if phase:
                return f"Fase market (AMD/PO3) saat ini diidentifikasi sebagai: {phase.upper()}."
            # Fallback to time-based estimation
            now_utc = datetime.now(timezone.utc)
            h = now_utc.hour
            if 0 <= h < 6:
                return "Berdasarkan waktu, market sedang dalam fase AKUMULASI (Sesi Asia)."
            elif 6 <= h < 12:
                return "Berdasarkan waktu, market memasuki fase MANIPULASI (London Open/Sweep)."
            else:
                return "Berdasarkan waktu, market cenderung berada di fase DISTRIBUSI / EXPANSION (New York)."
                
        # --- REKAP HARI INI (TOTAL, WINRATE, REWARD, ALL SETUPS) ---
        if any(k in norm for k in ['rekap', 'laporan', 'evaluasi', 'winrate', 'semua setup', 'hari ini ada berapa']):
            try:
                today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                # 1. Fetch all signals today
                query_signals = "SELECT * FROM signals WHERE created_at LIKE ? ORDER BY id ASC"
                rows = self.storage.fetchall(query_signals, (f"{today}%",))
                
                # 2. Fetch training data for today
                query_train = "SELECT SUM(reward), SUM(penalty) FROM brain_training WHERE created_at LIKE ?"
                train_row = self.storage.fetchall(query_train, (f"{today}%",))
                reward = float(train_row[0][0] or 0) if train_row and train_row[0] else 0.0
                penalty = float(train_row[0][1] or 0) if train_row and train_row[0] else 0.0
                net_score = reward - penalty
                
                if not rows:
                    return f"Belum ada setup atau sinyal yang terekam untuk hari ini ({today})."
                
                # Calculate Winrate
                closed_trades = [r for r in rows if r['result'] in ('WIN', 'FULL_WIN', 'PARTIAL_WIN', 'LOSS')]
                wins = len([r for r in closed_trades if 'WIN' in r['result']])
                losses = len([r for r in closed_trades if r['result'] == 'LOSS'])
                total_closed = len(closed_trades)
                
                winrate = (wins / total_closed * 100) if total_closed > 0 else 0
                
                resp = f"📊 **REKAP PERFORMA HARI INI ({today})**\n\n"
                resp += f"• Total Setup: {len(rows)}\n"
                resp += f"• Winrate: {winrate:.1f}% ({wins} Win / {losses} Loss dari {total_closed} closed trade)\n"
                resp += f"• Evaluasi AI (Reward/Penalty): +{reward:.1f} / -{penalty:.1f} (Net: {net_score:+.1f})\n\n"
                
                if net_score > 3:
                    resp += "🧠 *Bot semakin pintar hari ini karena berhasil mendapatkan banyak reward positif dari market!*\n\n"
                elif net_score < -3:
                    resp += "🧠 *Bot sedang beradaptasi dan belajar dari beberapa kesalahan (kena penalti) agar setup berikutnya lebih aman.*\n\n"
                else:
                    resp += "🧠 *Bot terus beradaptasi dengan kondisi market hari ini.*\n\n"
                    
                resp += "📋 **Rincian Setup:**\n"
                for i, r in enumerate(rows, 1):
                    dt = r['created_at'][11:16] # Time only
                    dir_ = r['direction']
                    res = r['result'] or r['status']
                    resp += f"{i}. {dt} UTC | {dir_} | {r['entry_low']} - {r['entry_high']} | Hasil: {res}\n"
                    
                return resp.strip()
            except Exception as e:
                return f"Gagal mengambil rekap hari ini dari database. ({str(e)})"

                
        # --- RIWAYAT SETUP / SINYAL ---
        if any(k in norm for k in ['riwayat', 'history', 'lewat', 'sebelumnya', 'kemarin', 'list sinyal', 'list setup']):
            try:
                query = "SELECT * FROM signals WHERE status != 'NO_TRADE' ORDER BY id DESC LIMIT 3"
                rows = self.storage.fetchall(query)
                if rows:
                    resp = "📋 **List Setup / Sinyal Terakhir:**\n\n"
                    for i, r in enumerate(rows, 1):
                        dt = r['created_at'][:16].replace('T', ' ')
                        direction = r['direction']
                        status = r['status']
                        result = r['result'] or 'Running/Pending'
                        elow = r['entry_low']
                        ehigh = r['entry_high']
                        resp += f"{i}. {dt} | **{direction}**\n   Area: {elow} - {ehigh}\n   Status: {status} | Hasil: {result}\n\n"
                    return resp.strip()
                return "Belum ada riwayat setup atau sinyal yang terekam di database."
            except Exception as e:
                return "Belum ada riwayat setup atau sinyal yang terekam di database saat ini."
                
        # --- CLASSIC PATTERNS (RETAIL TO SMC MAPPING) ---
        if any(k in norm for k in ['double top', 'triple top']):
            events = memory.recent_events('XAU/USD', limit=30)
            eqh = next((e for e in events if e.get('event_type') == 'EQH_DETECTED'), None)
            if eqh:
                lvl = eqh.get('level') or eqh.get('price')
                return f"Pola Double Top terdeteksi! (SMC: Equal Highs / EQH) di area {float(lvl):.2f}. Waspada ini sering menjadi Buy Side Liquidity (Target Sweep)."
            return "Pola Double Top belum terlihat dari struktur market saat ini."
            
        if any(k in norm for k in ['double bottom', 'triple bottom']):
            events = memory.recent_events('XAU/USD', limit=30)
            eql = next((e for e in events if e.get('event_type') == 'EQL_DETECTED'), None)
            if eql:
                lvl = eql.get('level') or eql.get('price')
                return f"Pola Double Bottom terdeteksi! (SMC: Equal Lows / EQL) di area {float(lvl):.2f}. Waspada ini sering menjadi Sell Side Liquidity (Target Sweep)."
            return "Pola Double Bottom belum terlihat dari struktur market saat ini."
            
        if any(k in norm for k in ['hns', 'head and shoulders', 'head & shoulders', 'quasimodo', 'qml', 'chart pattern', 'pola chart']):
            events = memory.recent_events('XAU/USD', limit=50)
            choch_bear = next((e for e in events if e.get('event_type') == 'CHoCH_BEAR'), None)
            choch_bull = next((e for e in events if e.get('event_type') == 'CHoCH_BULL'), None)
            if choch_bear:
                lvl = choch_bear.get('level') or choch_bear.get('price')
                return f"Pola Head & Shoulders (Bearish Quasimodo) kemungkinan terbentuk setelah penembusan support di area {float(lvl):.2f}. Cari peluang sell saat koreksi ke bahu kanan (Supply/OB)."
            elif choch_bull:
                lvl = choch_bull.get('level') or choch_bull.get('price')
                return f"Pola Inverted Head & Shoulders (Bullish Quasimodo) kemungkinan terbentuk setelah penembusan resistance di area {float(lvl):.2f}. Cari peluang buy saat koreksi ke bahu kanan (Demand/OB)."
            return "Pola Head & Shoulders (atau Quasimodo) belum terkonfirmasi karena belum ada indikasi penembusan struktur (CHoCH) terbaru."
        # --- REKOMENDASI BUY ATAU SELL (DUA SISI) ---
        if any(k in norm for k in ['buy atau sell', 'sell atau buy', 'rekomendasi buy', 'rekomendasi sell', 'mending buy', 'mending sell', 'buy apa sell']):
            active = memory.active_signal()
            if active:
                return self._format_signal_education(active, source="BOT DATA ONLY")
            
            # Build both scenarios
            events = memory.recent_events('XAU/USD', limit=100)
            supports = [e for e in events if e.get('event_type') in ('SWING_LOW', 'EQL_SWEEP', 'PDL_SWEEP', 'BOS_BEAR', 'CHoCH_BULL')]
            resistances = [e for e in events if e.get('event_type') in ('SWING_HIGH', 'EQH_SWEEP', 'PDH_SWEEP', 'BOS_BULL', 'CHoCH_BEAR')]
            
            sup_lvl = supports[0].get('level') or supports[0].get('price') if supports else None
            sup_tf = supports[0].get('timeframe') or 'M5' if supports else ''
            res_lvl = resistances[0].get('level') or resistances[0].get('price') if resistances else None
            res_tf = resistances[0].get('timeframe') or 'M5' if resistances else ''
            
            bias = memory.get_state('m15_bias') or memory.get_state('h1_bias')
            
            resp = ["Belum ada sinyal terkonfirmasi. Namun, berikut skenario berdasarkan struktur pasar:"]
            if bias:
                resp.append(f"• Bias saat ini cenderung {str(bias).upper()}.")
                
            if sup_lvl:
                resp.append(f"• Skenario BUY: Cari peluang buy di sekitar area Support/Demand {float(sup_lvl):.2f} (TF {sup_tf}) dengan konfirmasi rejection.")
            else:
                resp.append("• Skenario BUY: Belum ada level Support/Demand terdekat yang valid, tunggu struktur baru.")
                
            if res_lvl:
                resp.append(f"• Skenario SELL: Cari peluang sell di sekitar area Resistance/Supply {float(res_lvl):.2f} (TF {res_tf}) dengan konfirmasi rejection.")
            else:
                resp.append("• Skenario SELL: Belum ada level Resistance/Supply terdekat yang valid, tunggu struktur baru.")
                
            return "\n".join(resp)
            
        # --- REKOMENDASI ENTRY (TANYA BAGUS GAK) ---
        if any(k in norm for k in ['bagus gk', 'bagus ga', 'bagus tidak', 'rekomendasi entry', 'mau entry disini']):
            active = memory.active_signal()
            if active:
                direction = active.get('direction', 'NO_TRADE')
                entry_low = float(active.get('entry_low') or 0)
                entry_high = float(active.get('entry_high') or 0)
                price = float(self._bot_state.get('last_price', 0)) if self._bot_state else 0
                
                if price > 0 and entry_low > 0 and entry_high > 0:
                    if entry_low <= price <= entry_high:
                        return f"Rekomendasi: Harga saat ini ({price:.2f}) berada di dalam area entry {direction} ({entry_low:.2f} - {entry_high:.2f}). Boleh dipertimbangkan dengan lot aman dan SL."
                    elif (direction == 'BUY' and price > entry_high) or (direction == 'SELL' and price < entry_low):
                        return f"Rekomendasi: Harga sudah berlari dari area {direction}. Jangan FOMO atau kejar harga, tunggu koreksi kembali ke area entry."
                    else:
                        return f"Rekomendasi: Harga saat ini sedang floating melawan setup {direction}. Jika mau entry, pastikan siap dengan SL di {active.get('sl')}."
                return f"Rekomendasi: Fokus pada setup {direction} yang sedang aktif. Tunggu harga masuk ke area pantau."
            
            # If no active signal
            choppy = memory.get_state('choppy_market')
            if choppy:
                return "Rekomendasi: Market saat ini terdeteksi choppy/sideways. Lebih baik WAIT dan jangan entry dulu sampai ada struktur yang jelas."
            return "Rekomendasi: Saat ini belum ada setup valid dari bot. Lebih baik bersabar (Wait and See) dan hindari entry yang dipaksakan."

        parts = []

        # --- Current price ---
        price = 0
        if self._bot_state:
            price = self._bot_state.get('last_price', 0)
        if price and price > 0:
            parts.append(f"Harga sekarang di {price:.2f}.")

        # --- Active signal ---
        try:
            active = memory.active_signal()
        except Exception:
            active = None

        if active:
            parts.append(self._format_active_signal(active, price))
        else:
            parts.append(self._format_no_signal(memory))

        # --- Recent Structure / Event ---
        try:
            recent = memory.recent_events('XAU/USD', limit=15)
            sig_events = [e for e in recent if e.get('event_type') in (
                'BOS_BULL', 'BOS_BEAR', 'CHoCH_BULL', 'CHoCH_BEAR',
                'EQH_SWEEP', 'EQL_SWEEP', 'PDH_SWEEP', 'PDL_SWEEP'
            )]
            if sig_events:
                ev = sig_events[0]
                etype = ev.get('event_type')
                elvl = ev.get('level') or ev.get('price')
                if 'BOS_BULL' in etype:
                    parts.append(f"Market baru saja menembus resistance (BOS Bullish) di {float(elvl):.2f}.")
                elif 'BOS_BEAR' in etype:
                    parts.append(f"Market baru saja menembus support (BOS Bearish) di {float(elvl):.2f}.")
                elif 'CHoCH_BULL' in etype:
                    parts.append(f"Terjadi perubahan karakter (CHoCH Bullish) setelah break resistance di {float(elvl):.2f}.")
                elif 'CHoCH_BEAR' in etype:
                    parts.append(f"Terjadi perubahan karakter (CHoCH Bearish) setelah break support di {float(elvl):.2f}.")
                elif 'SWEEP' in etype:
                    parts.append(f"Baru saja terjadi Liquidity Sweep ({etype}) di area {float(elvl):.2f}.")
        except Exception:
            pass

        # --- Active FVGs ---
        try:
            fvgs = self.storage.get_active_fvgs('XAU/USD')
            if fvgs:
                # Pick most recent 1-2
                recent_fvgs = fvgs[:2]
                for fvg in recent_fvgs:
                    low_v = fvg.get('low', 0)
                    high_v = fvg.get('high', 0)
                    direction = fvg.get('direction', '?')
                    if low_v and high_v:
                        parts.append(
                            f"Ada FVG aktif di area {float(low_v):.2f} - {float(high_v):.2f} ({direction})."
                        )
        except Exception:
            pass

        response = ' '.join(parts)
        # Trim to max chars
        if len(response) > self.max_answer_chars:
            response = response[:self.max_answer_chars].rsplit(' ', 1)[0] + '...'
        return response

    def _format_active_signal(self, sig, price):
        """Format an active signal into a natural Bahasa response."""
        direction = (sig.get('direction') or '').upper()
        entry_low = sig.get('entry_low', 0)
        entry_high = sig.get('entry_high', 0)
        sl = sig.get('sl', 0)
        tp1 = sig.get('tp1', 0)
        status = sig.get('status', '')

        if direction == 'BUY':
            resp = f"Saat ini ada ACTIVE BUY."
            resp += f" Entry area {entry_low} - {entry_high}, SL {sl}, TP1 {tp1}."
            if price and entry_high:
                try:
                    dist = abs(float(price) - float(entry_high))
                    if dist > 3.0:
                        resp += " Harga sudah agak jauh dari area entry, hati-hati jangan kejar harga."
                except (ValueError, TypeError):
                    pass
            resp += " Tetap pakai lot yang nyaman dan pasang SL."
        elif direction == 'SELL':
            resp = f"Saat ini ada ACTIVE SELL."
            resp += f" Entry area {entry_low} - {entry_high}, SL {sl}, TP1 {tp1}."
            if price and entry_low:
                try:
                    dist = abs(float(price) - float(entry_low))
                    if dist > 3.0:
                        resp += " Harga sudah agak jauh dari area entry, hati-hati jangan kejar harga."
                except (ValueError, TypeError):
                    pass
            resp += " Tetap pakai lot yang nyaman dan pasang SL."
        else:
            resp = f"Ada signal aktif ({direction}), entry {entry_low} - {entry_high}."

        # Check TP progress
        if status and ('TP1' in status or 'TP2' in status):
            resp += f" Signal sudah {status}, SL sebaiknya sudah di-BE atau protected."

        return resp

    def _format_no_signal(self, memory):
        """Format response when no active signal."""
        # Check brain choppy state
        try:
            choppy = memory.get_state('choppy_market')
        except Exception:
            choppy = None

        if choppy:
            return (
                "Market sekarang masih choppy, jadi lebih aman tunggu dulu. "
                "Brain belum kasih setup yang bersih. "
                "Jangan entry hanya karena harga bergerak cepat."
            )
        return (
            "Sekarang belum ada entry valid. "
            "Brain masih menunggu BREAK + close confirm, jadi jangan kejar harga dulu. "
            "Tunggu area pantau atau sinyal baru dari bot."
        )

    @staticmethod
    def _market_fallback():
        return (
            "Belum bisa baca data market sekarang. "
            "Coba tunggu sebentar atau cek langsung di chart."
        )

    # ══════════════════════════════════════════════════════════════════
    # LOGGING
    # ══════════════════════════════════════════════════════════════════
    def _log(self, chat_id, user_id, username, question, intent, answer):
        """Log the Q&A interaction to knowledge_logs."""
        matched_id = intent
        score = 1.0 if answer else 0.0
        answered = 1 if answer else 0
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO knowledge_logs
                (created_at, chat_id, user_id, username, question, matched_id, score, answered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                _now(),
                str(chat_id or ''),
                str(user_id or ''),
                str(username or ''),
                question or '',
                matched_id,
                float(score),
                int(answered),
            ))
            conn.commit()
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════════
    # STATS
    # ══════════════════════════════════════════════════════════════════
    def stats(self):
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM knowledge_base')
            kb = cur.fetchone()[0] or 0
            cur.execute('SELECT COUNT(*) FROM knowledge_logs WHERE answered=1')
            answered = cur.fetchone()[0] or 0
            return {'knowledge_entries': kb, 'answered': answered}
        finally:
            conn.close()
