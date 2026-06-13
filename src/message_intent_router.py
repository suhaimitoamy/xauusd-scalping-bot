import re

ALIAS_TABLE = {
    'lose': 'loss', 'los': 'loss', 'rugi': 'loss', 'merugi': 'loss',
    'minus': 'loss', 'boncos': 'loss',
    'sl': 'stop loss', 'stoploss': 'stop loss', 'kena sl': 'stop loss hit',
    'tp': 'take profit', 'takeprofit': 'take profit',
    'ob': 'order block', 'orderblock': 'order block', 'blok order': 'order block',
    'fvg': 'fair value gap', 'imbalance': 'fair value gap',
    'smc': 'smart money concept', 'smart money concepts': 'smart money concept',
    'entry': 'entry', 'entri': 'entry', 'masuk': 'entry',
    'open posisi': 'entry', 'op': 'entry',
    'buy': 'buy', 'beli': 'buy', 'long': 'buy',
    'sell': 'sell', 'jual': 'sell', 'short': 'sell',
    'be': 'break even', 'breakeven': 'break even',
    'protected': 'protected',
    'liq': 'liquidity', 'likuiditas': 'liquidity', 'likuidity': 'liquidity',
    'poi': 'point of interest',
    'ote': 'optimal trade entry',
    'choch': 'change of character', 'bos': 'break of structure',
    'snr': 'support resistance', 'sr': 'support resistance',
    'tf': 'timeframe',
    'lot': 'lot', 'overlot': 'overlot',
    'mm': 'money management', 'rm': 'risk management',
    'rr': 'risk reward',
    'pullback': 'pullback', 'pb': 'pullback', 'retrace': 'pullback',
    'retest': 'retest',
    'rejection': 'rejection', 'rej': 'rejection',
    'confirm': 'confirmation', 'konfirmasi': 'confirmation', 'konfirm': 'confirmation',
    'bias': 'bias',
    'gold': 'xauusd', 'emas': 'xauusd', 'xau': 'xauusd',
    'skrg': 'sekarang', 'skrang': 'sekarang', 'skarang': 'sekarang',
    'gmn': 'gimana', 'gmna': 'gimana', 'gimanaa': 'gimana',
    'gk': 'tidak', 'ga': 'tidak', 'gak': 'tidak', 'nggak': 'tidak',
    'ngga': 'tidak', 'tdk': 'tidak',
    'bkn': 'bukan',
    'blm': 'belum', 'blom': 'belum',
    'udh': 'sudah', 'udah': 'sudah', 'sdh': 'sudah',
    'lg': 'lagi', 'lgi': 'lagi',
    'krn': 'karena', 'soalnya': 'karena',
    'yg': 'yang',
    'msh': 'masih',
    'bgt': 'banget', 'bngt': 'banget',
    'dlm': 'dalam',
    'aja': 'saja',
    'gw': 'aku', 'gue': 'aku', 'saya': 'aku', 'w': 'aku',
}

# Sort multi-word aliases first (longest first) so they match before single words
_MULTI_WORD_ALIASES = sorted(
    [(k, v) for k, v in ALIAS_TABLE.items() if ' ' in k],
    key=lambda x: len(x[0]), reverse=True
)
_SINGLE_WORD_ALIASES = {k: v for k, v in ALIAS_TABLE.items() if ' ' not in k}

_RE_EMOJI = re.compile(
    '['
    '\U0001F600-\U0001F64F'
    '\U0001F300-\U0001F5FF'
    '\U0001F680-\U0001F6FF'
    '\U00002600-\U000026FF'
    '\U00002700-\U000027BF'
    '\U0001F900-\U0001F9FF'
    '\U0001FA00-\U0001FA6F'
    '\U0001FA70-\U0001FAFF'
    '\U00002702-\U000027B0'
    '\U0000FE00-\U0000FE0F'
    '\U0000200D'
    '\U000020E3'
    '\U0000203C-\U00003299'
    ']+', re.UNICODE
)
_RE_URL = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)
_RE_PUNCT = re.compile(r'[^\w\s]', re.UNICODE)
_RE_WHITESPACE = re.compile(r'\s+')

BOT_MARKERS = [
    'xauusd buy', 'xauusd sell', 'adaptive brain', 'source: adaptive brain',
    'source: rule engine', 'tp1 hit', 'tp2 hit', 'tp3 hit', 'sl hit',
    'fvg detected', 'ob detected', 'poi map', 'gold smart money signals',
    'brain draft', 'ai trainer result', 'recent events:', 'brain status',
    'source: local db', 'xauusd adaptive brain', 'learning:', 'confidence:',
    'signal #', 'protected hit', 'be hit', 'partial win', 'full win',
]

NOISE_WORDS = frozenset({
    'ok', 'oke', 'sip', 'siap', 'mantap', 'mantab', 'wkwk', 'wkwkwk',
    'haha', 'hahaha', 'lol', 'nice', 'gg', 'gas', 'amin', 'aminn', 'aminnn',
    'ya', 'yaa', 'yoi', 'iya', 'ngga', 'bener', 'setuju', 'betul',
    'thanks', 'makasih', 'thx', 'noted', 'oot', 'min',
})

# ---------------------------------------------------------------------------
# Generic / supporting question words — score LOW, never trigger by themselves
# ---------------------------------------------------------------------------
GENERIC_QUESTION_WORDS = frozenset({
    'apa', 'apakah', 'gimana', 'bagaimana', 'kenapa', 'mengapa',
    'dimana', 'sekarang', 'kapan', 'siapa', 'mana',
})

# --- MARKET ---
MARKET_PHRASES = [
    'buy atau sell', 'sell atau buy', 'buy apa sell', 'sell apa buy',
    'sekarang buy', 'sekarang sell', 'sekarang entry',
    'entry di mana', 'entry dimana', 'area entry',
    'market gimana', 'market sekarang', 'kondisi market',
    'masih valid buy', 'masih valid sell', 'masih valid',
    'setup sekarang', 'bias sekarang', 'bias hari ini',
    'area pantau', 'area pantau mana', 'area pantau sekarang',
    'harga sekarang boleh entry', 'boleh entry', 'aman entry',
    'sinyal masih valid', 'signal masih valid',
    'tunggu apa sekarang', 'tunggu apa',
    'enaknya buy', 'enaknya sell', 'enaknya entry',
    'harga sudah jauh', 'harga jauh',
    'ikut sinyal', 'ikut signal',
    'kapan entry', 'mau entry',
]

_MARKET_REGEXES = [
    re.compile(r'(sekarang|skrg).*?(buy|sell|entry|setup|market|bias|area|pantau)'),
    re.compile(r'(buy|sell|entry).*?(mana|dimana|sekarang|valid|aman|kapan)'),
    re.compile(r'(xauusd|gold|emas).*?(buy|sell|gimana|sekarang)'),
    re.compile(r'(masih|msh).*?(valid|aman|hold|lanjut)'),
    re.compile(r'(area|zona|level).*?(pantau|entry|buy|sell)'),
    re.compile(r'(sinyal|signal|setup).*?(masih|valid|aman|sekarang|hari ini)'),
    re.compile(r'(tunggu|wait).*?(apa|mana|setup|entry|sinyal)'),
    re.compile(r'(harga|price).*?(sekarang|entry|boleh|aman|sudah|jauh)'),
    re.compile(r'(kapan|mau|boleh|bisa).*?(entry|buy|sell|masuk|open)'),
    re.compile(r'(choppy|sideways|ranging)'),
]

MARKET_KEYWORDS = frozenset({
    'buy', 'sell', 'entry', 'xauusd', 'market', 'setup', 'bias',
    'pantau', 'sinyal', 'signal', 'valid', 'hold', 'lanjut',
    'choppy', 'sideways', 'ranging',
})

# --- FAQ ---
FAQ_PHRASES = [
    'apa itu', 'itu apa', 'artinya apa', 'arti apa', 'maksud apa', 'maksudnya apa',
    'gunanya apa', 'fungsinya apa', 'buat apa', 'dipakai buat apa',
    'jelaskan', 'jelasin', 'pengertian', 'definisi',
    'beda apa', 'perbedaan', 'bedanya apa', 'sama gak', 'sama tidak',
    'valid kalau gimana', 'cara pakai', 'cara menggunakan',
]

FAQ_CONCEPT_KEYWORDS = frozenset({
    'fair value gap', 'order block', 'smart money concept', 'stop loss',
    'take profit', 'break even', 'protected', 'partial win', 'full win',
    'liquidity', 'point of interest', 'optimal trade entry',
    'change of character', 'break of structure', 'support resistance',
    'pullback', 'retest', 'rejection', 'confirmation', 'bias',
    'risk reward', 'risk management', 'money management', 'lot', 'timeframe',
    'swing', 'trend', 'reversal', 'continuation', 'candle', 'candlestick',
    'bearish', 'bullish', 'demand', 'supply', 'premium', 'discount',
    'antigravity', 'evolutionary ai', 'self healing',
})

FAQ_QUESTION_WORDS = frozenset({
    'apa', 'apakah', 'gimana', 'bagaimana', 'kenapa', 'mengapa',
    'maksud', 'arti', 'artinya', 'jelaskan', 'jelasin', 'cara',
    'pengertian', 'definisi', 'beda', 'perbedaan', 'bedanya',
    'gunanya', 'fungsinya',
})

_FAQ_REGEXES = [
    re.compile(r'(apa|apakah)\s+(itu\s+)?\w+'),
    re.compile(r'\w+\s+(itu|nya|tuh)\s+(apa|apaan)'),
    re.compile(r'(maksud|arti|artinya|pengertian|definisi|jelaskan|jelasin)\s+\w+'),
    re.compile(r'\w+\s+(gunanya|fungsinya|buat apa|dipakai)'),
    re.compile(r'\w+\s+(sama|dan|dengan)\s+\w+\s+(beda|perbedaan|bedanya)'),
    re.compile(r'(cara|gimana|bagaimana)\s+(pakai|menggunakan|baca|lihat)\s+\w+'),
]

# --- CURHAT ---
CURHAT_PHRASES = [
    'aku sedih', 'aku capek', 'aku down', 'aku frustasi', 'aku frustrasi',
    'aku mau curhat', 'curhat dong', 'mau curhat',
    'aku takut entry', 'takut salah', 'takut loss', 'takut rugi',
    'aku emosi', 'aku panik', 'aku bingung',
    'aku revenge', 'revenge trade', 'revenge entry',
    'aku overlot', 'overlot',
    'capek trading', 'pusing trading', 'bosan trading',
    'kok loss', 'kok rugi', 'sinyalnya loss', 'sinyalnya rugi',
    'ikut malah rugi', 'ikut malah loss',
    'stop loss hit terus', 'kena stop loss terus', 'loss terus',
    'lose terus', 'rugi terus', 'minus terus', 'boncos terus',
]

_CURHAT_REGEXES = [
    re.compile(r'(aku|gw|gue|saya|w)\s+(sedih|capek|cape|down|frustasi|frustrasi|takut|emosi|panik|bingung|stress|stres|galau|nyesel|menyesal|kecewa)'),
    re.compile(r'(kena|loss|lose|rugi|minus|boncos|stop loss)\s*(terus|mulu|melulu|berkali|lagi|lg)'),
    re.compile(r'(capek|cape|pusing|bosan|muak|males|malas)\s*(trading|trade|market)'),
    re.compile(r'(kok|kenapa|mengapa)\s*(loss|rugi|kena|stop loss|sl)'),
    re.compile(r'(revenge|balas dendam|overlot|fomo|over trade|overtrade)'),
    re.compile(r'(mau|pengen|ingin)\s*(curhat|cerita|curcol)'),
]

CURHAT_EMOTION_KEYWORDS = frozenset({
    'sedih', 'capek', 'cape', 'down', 'frustasi', 'frustrasi', 'takut',
    'emosi', 'panik', 'bingung', 'stress', 'stres', 'galau', 'nyesel',
    'menyesal', 'kecewa', 'revenge', 'fomo', 'overlot', 'curhat',
})

# --- FUNDAMENTAL ---
# NOTE: "emas"/"gold" are aliased to "xauusd" during normalization,
# so we include both raw and normalized forms for phrase matching.
FUNDAMENTAL_PHRASES = [
    # Raw forms (matched before normalization in some paths)
    'inflasi dan emas', 'inflasi dan gold', 'hubungan inflasi emas',
    'hubungan inflasi dan emas', 'pengaruh inflasi terhadap emas',
    'dollar dan gold', 'dollar dan emas', 'hubungan dollar emas',
    'hubungan dollar dan gold', 'pengaruh dollar terhadap emas',
    'dolar dan emas', 'dolar dan gold', 'hubungan dolar emas',
    'suku bunga dan gold', 'suku bunga dan emas', 'hubungan suku bunga emas',
    'pengaruh suku bunga terhadap emas', 'interest rate dan gold',
    'the fed dan emas', 'the fed dan gold', 'fomc dan emas', 'fomc dan gold',
    'nfp dan emas', 'nfp dan gold', 'non farm payroll',
    'cpi dan emas', 'cpi dan gold',
    'fundamental emas', 'fundamental gold', 'fundamental xauusd',
    'berita emas', 'berita gold', 'news gold', 'news emas',
    'kenapa emas naik', 'kenapa gold naik', 'kenapa emas turun', 'kenapa gold turun',
    'geopolitik dan emas', 'perang dan emas', 'resesi dan emas',
    'safe haven', 'safe haven emas',
    # Normalized forms (after alias: emas/gold → xauusd)
    'inflasi dan xauusd', 'hubungan inflasi xauusd',
    'hubungan inflasi dan xauusd', 'pengaruh inflasi terhadap xauusd',
    'dollar dan xauusd', 'hubungan dollar xauusd',
    'hubungan dollar dan xauusd', 'pengaruh dollar terhadap xauusd',
    'dolar dan xauusd', 'hubungan dolar xauusd',
    'suku bunga dan xauusd', 'hubungan suku bunga xauusd',
    'pengaruh suku bunga terhadap xauusd', 'interest rate dan xauusd',
    'the fed dan xauusd', 'fomc dan xauusd',
    'nfp dan xauusd', 'cpi dan xauusd',
    'berita xauusd', 'news xauusd',
    'kenapa xauusd naik', 'kenapa xauusd turun',
    'geopolitik dan xauusd', 'perang dan xauusd', 'resesi dan xauusd',
    'safe haven xauusd',
]

_FUNDAMENTAL_REGEXES = [
    re.compile(r'(inflasi|inflation).*?(emas|gold|xau|xauusd|naik|turun|pengaruh|hubungan)'),
    re.compile(r'(emas|gold|xau|xauusd).*?(inflasi|inflation|dollar|dolar|suku bunga|interest rate|fed|fomc|nfp|cpi|fundamental|berita|news)'),
    re.compile(r'(dollar|dolar|usd).*?(emas|gold|xau|xauusd|naik|turun|pengaruh|hubungan|kuat|lemah)'),
    re.compile(r'(suku bunga|interest rate|rate).*?(emas|gold|xau|xauusd|naik|turun|pengaruh|hubungan)'),
    re.compile(r'(fed|fomc|nfp|cpi|ppi|gdp|non farm).*?(emas|gold|xau|xauusd|pengaruh|hubungan|dampak|efek|gimana|bagaimana)'),
    re.compile(r'(berita|news|fundamental).*?(emas|gold|xau|xauusd|market|hari ini)'),
    re.compile(r'(kenapa|mengapa).*?(emas|gold|xau|xauusd).*(naik|turun|jatuh|rally|terbang|anjlok)'),
    re.compile(r'(geopolitik|perang|war|resesi|recession|safe haven).*?(emas|gold|xau|xauusd)'),
    re.compile(r'(emas|gold|xau|xauusd).*?(geopolitik|perang|war|resesi|recession|safe haven)'),
    # Catch "hubungan X dan xauusd" pattern after normalization
    re.compile(r'hubungan.+?(inflasi|dollar|dolar|suku bunga|interest|fed|fomc|nfp|cpi)'),
    re.compile(r'(inflasi|dollar|dolar|suku bunga|interest|fed|fomc|nfp|cpi).+?xauusd'),
]

FUNDAMENTAL_KEYWORDS = frozenset({
    'inflasi', 'inflation', 'dollar', 'dolar', 'usd',
    'suku', 'bunga', 'interest', 'rate', 'fed', 'fomc', 'nfp', 'cpi', 'ppi', 'gdp',
    'fundamental', 'berita', 'news', 'geopolitik', 'perang', 'resesi',
    'safe', 'haven', 'recession', 'war',
})

# --- HELP (cara pakai bot) ---
HELP_PHRASES = [
    'cara pakai bot', 'cara menggunakan bot', 'cara kerja bot',
    'gimana cara pakai', 'gimana cara pake', 'bagaimana cara pakai',
    'bot ini bisa apa', 'fitur bot', 'command bot', 'perintah bot',
    'cara baca signal', 'cara baca sinyal', 'cara pakai sinyal',
    'cara pakai signal', 'cara ikut sinyal', 'cara ikut signal',
    'command apa saja', 'perintah apa saja', 'menu bot',
    'help bot', 'bantuan bot', 'tolong jelaskan bot',
    'cara join', 'cara gabung', 'cara mulai',
    'bot ini apa', 'ini bot apa',
]

_HELP_REGEXES = [
    re.compile(r'(cara|gimana|bagaimana)\s+(pakai|pake|menggunakan|kerja|baca|ikut)\s+(bot|sinyal|signal)'),
    re.compile(r'(bot|command|perintah|fitur|menu)\s+(ini|apa|nya|saja|aja)'),
    re.compile(r'(apa|apakah)\s+(saja|aja)?\s*(command|perintah|fitur|menu|tombol)'),
    re.compile(r'(cara|gimana|bagaimana)\s+(join|gabung|mulai|start)'),
]

HELP_KEYWORDS = frozenset({
    'bot', 'command', 'perintah', 'fitur', 'menu', 'tombol',
    'bantuan', 'help', 'panduan', 'tutorial',
})


def _extend_router_vocabulary():
    """Expand Bahasa Indonesia Telegram trigger coverage without changing routing structure."""
    global ALIAS_TABLE, _MULTI_WORD_ALIASES, _SINGLE_WORD_ALIASES
    global MARKET_KEYWORDS, FAQ_CONCEPT_KEYWORDS, CURHAT_EMOTION_KEYWORDS

    ALIAS_TABLE.update({
        'bisa buy': 'buy', 'bisa sell': 'sell', 'buyy': 'buy', 'sel': 'sell', 'selll': 'sell',
        'sinyall': 'sinyal', 'signall': 'signal', 'sinyal nya': 'sinyal', 'setup nya': 'setup',
        'valid gak': 'valid tidak', 'valid ga': 'valid tidak', 'aman gak': 'aman tidak',
        'aman ga': 'aman tidak', 'boleh gak': 'boleh tidak', 'boleh ga': 'boleh tidak',
        'di mana': 'dimana', 'd mana': 'dimana', 'dmna': 'dimana', 'dimna': 'dimana',
        'sekrang': 'sekarang', 'skrang': 'sekarang', 'skrg': 'sekarang', 'skg': 'sekarang',
        'klo': 'kalau', 'kalo': 'kalau', 'klau': 'kalau', 'klu': 'kalau',
        'ap': 'apa', 'apa kah': 'apakah', 'knp': 'kenapa', 'napa': 'kenapa', 'ngapain': 'kenapa',
        'gimana ya': 'gimana', 'gmn ya': 'gimana', 'gmn nih': 'gimana', 'gimana nih': 'gimana',
        'plis': 'tolong', 'please': 'tolong', 'tolong cek': 'cek', 'cek dong': 'cek',
        'xau/usd': 'xauusd', 'xau usd': 'xauusd', 'goldnya': 'xauusd', 'emasnya': 'xauusd',
        'tp 1': 'take profit 1', 'tp 2': 'take profit 2', 'tp1': 'take profit 1', 'tp2': 'take profit 2',
        'sl nya': 'stop loss', 'tpsl': 'take profit stop loss', 'kena tp': 'take profit hit',
        'kena tp1': 'take profit 1 hit', 'kena tp2': 'take profit 2 hit',
        'balik be': 'break even', 'balik ke be': 'break even', 'profit sedikit': 'partial win',
        'fomo': 'fear of missing out', 'over trade': 'overtrade', 'over trading': 'overtrade',
        'mss': 'market structure shift', 'bms': 'break in market structure',
        'bsl': 'buy side liquidity', 'ssl': 'sell side liquidity',
        'eqh': 'equal high', 'eql': 'equal low', 'sweep': 'sentuh', 'grab': 'sentuh',
        'breaker': 'breaker block', 'mitigasi': 'mitigation', 'mitigate': 'mitigation',
        'reclaim': 'reclaim', 'displacement': 'displacement', 'disp': 'displacement',
        'inducement': 'inducement', 'idm': 'inducement', 'chochnya': 'change of character',
        'bosnya': 'break of structure', 'obnya': 'order block', 'fvgnya': 'fair value gap',
        'liquidnya': 'liquidity', 'liquiditynya': 'liquidity', 'liqudity': 'liquidity',
        'jurnal': 'journal', 'journal': 'journal', 'evaluasi': 'evaluation', 'review': 'review',
    })

    MARKET_PHRASES.extend([
        'cek market', 'cek xau', 'cek gold', 'cek emas', 'update xau', 'update gold', 'update emas',
        'gold gimana', 'emas gimana', 'xau gimana', 'xauusd gimana', 'gold sekarang', 'emas sekarang',
        'xau sekarang', 'xauusd sekarang', 'gold hari ini', 'emas hari ini', 'xau hari ini',
        'arah gold', 'arah emas', 'arah xau', 'arah market', 'market arah mana', 'harga mau kemana',
        'gold mau kemana', 'emas mau kemana', 'xau mau kemana', 'market mau kemana',
        'setup buy', 'setup sell', 'setup aman', 'setup valid', 'setup masih jalan', 'setup batal',
        'buy valid', 'sell valid', 'entry valid', 'entry aman', 'entry sekarang aman', 'boleh buy', 'boleh sell',
        'bisa buy', 'bisa sell', 'cari buy', 'cari sell', 'prioritas buy', 'prioritas sell', 'prioritas wait',
        'wait atau entry', 'masuk sekarang', 'open posisi sekarang', 'ikut sekarang', 'ikut entry',
        'harga dekat area', 'harga sudah sentuh', 'sudah sentuh area', 'retest belum', 'sudah retest',
        'break sudah valid', 'close confirm belum', 'candle confirm belum', 'm5 confirm', 'm15 bias',
        'kenapa no trade', 'no trade kenapa', 'market choppy', 'lagi choppy', 'sideways ya', 'range ya',
        'signal terbaru', 'sinyal terbaru', 'ada sinyal', 'ada signal', 'signal mana', 'sinyal mana',
        'validasi signal', 'validasi sinyal', 'sinyal masih aman', 'signal masih aman',
        'tp1 sudah kena', 'tp2 sudah kena', 'sl sudah kena', 'masih hold', 'hold atau close',
        'close dulu', 'ambil profit', 'protect dulu', 'be dulu', 'pindah be', 'pasang be',
        
        'market lagi apa', 'market sekarang apa', 'kondisi market apa', 'gold lagi apa', 'xau lagi apa', 'market sedang apa', 'gold sedang apa',
        'support terdekat', 'support dimana', 'area support', 'support sekarang', 'support gold', 'support xau',
        'demand terdekat', 'demand dimana', 'area demand', 'demand sekarang', 'demand gold', 'demand xau',
        'resistance terdekat', 'resistance dimana', 'area resistance', 'resistance sekarang', 'resistance gold', 'resistance xau',
        'supply terdekat', 'supply dimana', 'area supply', 'supply sekarang', 'supply gold', 'supply xau',
        'swing terdekat', 'swing high terdekat', 'swing low terdekat', 'swing terbaru', 'high low terdekat', 'struktur swing',
        'invalidasi dimana', 'level invalidasi', 'invalidasi sekarang', 'sl dimana', 'invalidation level',
        'draw on liquidity', 'dol dimana', 'dol sekarang', 'target liquidity',
        'csid', 'csid dimana', 'csid sekarang',
        'smt', 'smt dimana', 'smt divergen', 'smt sekarang',
        'rbs', 'rbs dimana', 'rbs sekarang', 'resistance become support',
        'sbr', 'sbr dimana', 'sbr sekarang', 'support become resistance',
        'rbr', 'rally base rally', 'dbd', 'drop base drop', 'rbd', 'rally base drop', 'dbr', 'drop base rally',
        'bsl', 'bsl dimana', 'buy side liquidity',
        'ssl', 'ssl dimana', 'sell side liquidity',
        'idm', 'idm dimana', 'inducement',
        'sweep', 'liquidity sweep', 'stop hunt',
        'poi', 'point of interest', 'area pantau',
        'premium', 'discount', 'harga premium', 'harga discount',
        'ote', 'optimal trade entry', 'area ote',
        'killzone', 'london open', 'new york open', 'silver bullet',
        'amd', 'po3', 'fase amd', 'manipulasi', 'akumulasi', 'distribusi',
        'double top', 'double bottom', 'triple top', 'triple bottom', 
        'hns', 'head and shoulders', 'head & shoulders', 'quasimodo', 'qml', 'chart pattern', 'pola chart',
        'riwayat sinyal', 'riwayat setup', 'list sinyal', 'list setup', 'setup yang sudah lewat', 'history sinyal', 'history setup',
        'rekap hari ini', 'laporan hari ini', 'hari ini ada berapa sinyal', 'evaluasi hari ini', 'winrate hari ini', 'semua setup hari ini',
        'bagus gk entry', 'bagus ga entry', 'bagus tidak entry', 'mau entry disini', 'boleh entry disini', 'rekomendasi entry',
        'rekomendasi buy', 'rekomendasi sell', 'mending buy atau sell', 'mending sell atau buy', 'buy atau sell', 'sell atau buy',
        'pdh', 'previous day high', 'high kemarin', 'daily high kemarin',
        'pdl', 'previous day low', 'low kemarin', 'daily low kemarin',
        'eqh', 'equal high', 'liquidity atas sejajar', 'high sejajar',
        'eql', 'equal low', 'liquidity bawah sejajar', 'low sejajar',
        'bias sekarang', 'bias saat ini', 'bias market', 'bias gold', 'bias xau', 'arah bias',
        'struktur market saat ini', 'struktur market sekarang', 'struktur gold', 'struktur xau', 'market structure', 'struktur bullish atau bearish', 'bos atau choch', 'mss sekarang',
        'zona fvg dinama', 'fvg dinama', 'fvg dimana', 'zona fvg dimana', 'fvg terdekat', 'area fvg',
        'enaknya entry apa', 'entry apa', 'ada entry', 'posisi entry', 'buy dimana', 'sell dimana',
        'enaknya buy atau sell', 'cari buy atau sell', 'gold buy atau sell', 'xau buy atau sell'
    ])

    _MARKET_REGEXES.extend([
        re.compile(r'(cek|update|lihat|pantau).*?(xauusd|xau|gold|emas|market|harga|setup|sinyal|signal)'),
        re.compile(r'(gold|emas|xauusd|xau|market|harga).*?(gimana|bagaimana|arah|kemana|naik|turun|buy|sell|entry|valid|aman|wait)'),
        re.compile(r'(boleh|bisa|aman|valid).*?(buy|sell|entry|masuk|open posisi|op)'),
        re.compile(r'(tp1|take profit 1|tp2|take profit 2|stop loss|break even|protected|protect).*?(kena|hit|sudah|belum|balik|close|hold)'),
        re.compile(r'(m5|m15|h1|tf).*?(confirm|close|break|bias|retest|reject|rejection)'),
        re.compile(r'(sinyal|signal).*?(baru|terbaru|valid|aman|batal|lanjut|hold|close)'),
    ])

    MARKET_KEYWORDS = MARKET_KEYWORDS | frozenset({
        'cek', 'update', 'lihat', 'harga', 'price', 'arah', 'naik', 'turun', 'wait', 'no', 'trade',
        'xau', 'gold', 'emas', 'xauusd', 'm5', 'm15', 'h1', 'confirm', 'close', 'break', 'sentuh',
        'retest', 'reject', 'rejection', 'tp1', 'tp2', 'protect', 'protected', 'break', 'even',
        'liquidity', 'demand', 'supply', 'fvg', 'ob', 'ote', 'poi', 'area', 'zona', 'level',
        'support', 'resistance', 'swing', 'pdh', 'pdl', 'eqh', 'eql', 'bias', 'struktur', 'structure',
        'invalidasi', 'invalidation', 'dol', 'draw', 'csid', 'smt', 'rbs', 'sbr', 'rbr', 'dbd', 'rbd', 'dbr',
        'bsl', 'ssl', 'idm', 'inducement', 'sweep', 'hunt', 'premium', 'discount', 'killzone', 'london', 'york', 'amd', 'po3', 'manipulasi',
        'double', 'triple', 'top', 'bottom', 'hns', 'head', 'shoulders', 'quasimodo', 'qml', 'chart', 'pattern', 'pola',
        'riwayat', 'history', 'lewat', 'list', 'rekap', 'laporan', 'evaluasi', 'winrate', 'semua'
    })

    FAQ_PHRASES.extend([
        'maksudnya gimana', 'maksudnya bagaimana', 'jelasin dong', 'jelaskan dong', 'tolong jelaskan',
        'contohnya apa', 'contoh nya apa', 'contoh gimana', 'cara bacanya', 'cara lihatnya',
        'cara nentuin', 'cara menentukan', 'cara entry', 'cara pasang', 'cara hitung',
        'kenapa harus', 'kenapa tidak boleh', 'kenapa jangan', 'apakah boleh', 'apakah aman',
        'fungsi dari', 'arti dari', 'apa maksud dari', 'apa bedanya', 'bedanya dimana',
    ])

    FAQ_CONCEPT_KEYWORDS = FAQ_CONCEPT_KEYWORDS | frozenset({
        'market structure shift', 'mss', 'bms', 'buy side liquidity', 'sell side liquidity',
        'equal high', 'equal low', 'displacement', 'breaker block', 'mitigation', 'inducement',
        'reclaim', 'sentuh high', 'sentuh low', 'sweep', 'liquidity sweep', 'liquidity grab',
        'daily bias', 'session', 'london session', 'new york session', 'asian session',
        'atr', 'spread', 'commission', 'drawdown', 'winrate', 'risk per trade', 'position sizing',
        'journal', 'jurnal', 'trading plan', 'entry model', 'price action', 'reversal', 'continuation',
        'range', 'choppy', 'sideways', 'impulsive', 'pullback', 'premium discount', 'equilibrium',
        'buy side', 'sell side', 'target liquidity', 'invalidasi', 'invalidation', 'confirmation candle',
        'no trade', 'psikologi', 'psikologi trading', 'mental trading',
    })

    _FAQ_REGEXES.extend([
        re.compile(r'(apa|apakah|maksud|arti|jelasin|jelaskan|contoh|cara|kenapa).*?(fvg|ob|order block|liquidity|bos|choch|mss|bsl|ssl|ote|poi|sl|tp|be|risk|lot|rr|jurnal|journal|sentuh|sweep)'),
        re.compile(r'(fvg|ob|order block|liquidity|bos|choch|mss|bsl|ssl|ote|poi|sl|tp|be|risk|lot|rr|jurnal|journal|sentuh|sweep).*?(apa|gimana|bagaimana|maksud|arti|cara|fungsi|gunanya|contoh|beda)'),
        re.compile(r'(kenapa|mengapa).*?(loss|sl|rugi|market|choppy|sideways|fomo|overlot|entry|sinyal|signal)'),
    ])

    CURHAT_PHRASES.extend([
        'aku kena sl lagi', 'kena sl lagi', 'sl mulu', 'loss mulu', 'rugi mulu', 'boncos mulu',
        'akun turun', 'modal turun', 'mental kena', 'mental down', 'takut open posisi', 'takut op',
        'takut salah entry', 'bingung entry', 'bingung market', 'galau trading', 'kecewa trading',
        'cape loss', 'capek loss', 'pusing loss', 'emosi habis loss', 'habis loss', 'baru loss',
        'mau balas loss', 'pengen balas', 'mau revenge', 'gatal entry', 'pengen entry terus',
        'susah sabar', 'tidak sabar', 'ga sabar', 'gak sabar', 'selalu fomo', 'sering fomo',
        'aku tadi kena sl', 'kena sl', 'habis sl', 'sl terus', 'entry kena sl', 'loss lagi', 'kalah lagi'
    ])

    _CURHAT_REGEXES.extend([
        re.compile(r'(aku|gw|gue|saya|w)?.*?(kena sl|loss|rugi|boncos|minus).*?(lagi|mulu|terus|melulu)'),
        re.compile(r'(takut|ragu|ngeri|cemas|khawatir).*?(entry|op|open posisi|buy|sell|loss|sl)'),
        re.compile(r'(mental|psikologi).*?(down|kena|hancur|capek|cape|lelah|drop)'),
        re.compile(r'(gatal|pengen|mau|ingin).*?(entry terus|balas|revenge|overtrade|fomo)'),
    ])

    CURHAT_EMOTION_KEYWORDS = CURHAT_EMOTION_KEYWORDS | frozenset({
        'cemas', 'khawatir', 'lelah', 'drop', 'hancur', 'mental', 'psikologi', 'trauma', 'kapok',
        'marah', 'kesal', 'gatal', 'sabar', 'overtrade', 'overtrading', 'balas', 'revenge',
    })

    _MULTI_WORD_ALIASES = sorted(
        [(k, v) for k, v in ALIAS_TABLE.items() if ' ' in k],
        key=lambda x: len(x[0]), reverse=True
    )
    _SINGLE_WORD_ALIASES = {k: v for k, v in ALIAS_TABLE.items() if ' ' not in k}


_extend_router_vocabulary()


def normalize(text: str) -> str:
    t = text.lower()
    t = _RE_URL.sub('', t)
    t = _RE_EMOJI.sub('', t)
    t = _RE_PUNCT.sub(' ', t)
    t = _RE_WHITESPACE.sub(' ', t).strip()
    # Multi-word alias replacement first
    for src, dst in _MULTI_WORD_ALIASES:
        t = t.replace(src, dst)
    # Single-word alias replacement
    words = t.split()
    words = [_SINGLE_WORD_ALIASES.get(w, w) for w in words]
    return ' '.join(words)


def _is_bot_notification(raw_lower: str) -> bool:
    for marker in BOT_MARKERS:
        if marker in raw_lower:
            return True
    return False


def _is_noise(normalized: str) -> bool:
    if not normalized or len(normalized) < 3:
        return True
    if normalized in NOISE_WORDS:
        return True
    return False


def _score_phrases(text: str, phrases: list) -> int:
    count = 0
    for p in phrases:
        if p in text:
            count += 1
    return count


def _score_regexes(text: str, regexes: list) -> int:
    count = 0
    for r in regexes:
        if r.search(text):
            count += 1
    return count


def _score_keywords(text_words: set, keywords: frozenset) -> int:
    return len(text_words & keywords)


def _score_generic_only(text_words: set) -> int:
    """Count how many words in the text are ONLY generic question words.
    Used to penalize messages that have no domain-specific content."""
    return len(text_words & GENERIC_QUESTION_WORDS)


def _count_domain_words(text_words: set) -> int:
    """Count words that are NOT generic question words — i.e. domain-specific."""
    return len(text_words - GENERIC_QUESTION_WORDS - NOISE_WORDS - frozenset({
        'dan', 'atau', 'yang', 'dari', 'untuk', 'dengan', 'dalam', 'pada',
        'ke', 'di', 'ini', 'itu', 'adalah', 'aku', 'kamu', 'nya',
        'dong', 'sih', 'nih', 'tuh', 'lah', 'ya', 'tidak', 'bukan',
        'belum', 'sudah', 'masih', 'lagi', 'karena', 'juga', 'kalau',
        'tapi', 'jadi', 'jangan', 'bisa', 'harus', 'boleh', 'mau',
        'tolong', 'coba', 'saja', 'banget',
    }))


def _find_concept(text: str) -> str | None:
    for concept in sorted(FAQ_CONCEPT_KEYWORDS, key=len, reverse=True):
        if concept in text:
            return concept
    return None


class IntentRouter:
    __slots__ = ('_last_concept',)

    def __init__(self):
        self._last_concept: str | None = None

    def classify(self, raw_text: str) -> str:
        self._last_concept = None

        if not raw_text or not raw_text.strip():
            return 'UNKNOWN'

        raw_lower = raw_text.lower()

        # Step 1: Bot notification check on raw text
        if _is_bot_notification(raw_lower):
            return 'BOT_NOTIFICATION'

        # Step 2: Normalize
        norm = normalize(raw_text)

        # Step 3: Noise check
        if _is_noise(norm):
            return 'UNKNOWN'

        words = set(norm.split())
        domain_count = _count_domain_words(words)

        # Step 4: Score MARKET
        m_phrase = _score_phrases(norm, MARKET_PHRASES)
        m_regex = _score_regexes(norm, _MARKET_REGEXES)
        m_kw = _score_keywords(words, MARKET_KEYWORDS)
        market_score = m_phrase * 10 + m_regex * 7 + m_kw * 3

        # Step 5: Score FAQ
        f_phrase = _score_phrases(norm, FAQ_PHRASES)
        f_regex = _score_regexes(norm, _FAQ_REGEXES)
        concept = _find_concept(norm)
        has_question = bool(words & FAQ_QUESTION_WORDS)
        f_concept = 1 if (concept and has_question) else 0
        faq_score = f_phrase * 10 + f_regex * 7 + f_concept * 5

        # Step 6: Score CURHAT
        c_phrase = _score_phrases(norm, CURHAT_PHRASES)
        c_regex = _score_regexes(norm, _CURHAT_REGEXES)
        c_emo = _score_keywords(words, CURHAT_EMOTION_KEYWORDS)
        curhat_score = c_phrase * 10 + c_regex * 7 + c_emo * 4

        # Step 7: Score FUNDAMENTAL — boosted weights because fundamental
        # phrases are highly specific but "emas"/"gold" alias to "xauusd"
        # which inflates MARKET keyword score incorrectly.
        fund_phrase = _score_phrases(norm, FUNDAMENTAL_PHRASES)
        fund_regex = _score_regexes(norm, _FUNDAMENTAL_REGEXES)
        fund_kw = _score_keywords(words, FUNDAMENTAL_KEYWORDS)
        fundamental_score = fund_phrase * 15 + fund_regex * 10 + fund_kw * 3

        # Step 8: Score HELP
        help_phrase = _score_phrases(norm, HELP_PHRASES)
        help_regex = _score_regexes(norm, _HELP_REGEXES)
        help_kw = _score_keywords(words, HELP_KEYWORDS)
        help_score = help_phrase * 12 + help_regex * 8 + help_kw * 3

        # Step 9: Guard — if no domain-specific words at all, don't match
        # This prevents "sekarang gimana" or "apa itu" (alone) from triggering
        if domain_count == 0:
            return 'UNKNOWN'

        # Step 10: Tie-break — if FUNDAMENTAL has regex hits AND fundamental
        # domain keywords, prefer it over MARKET. This prevents generic
        # "xauusd gimana" MARKET phrase from overriding specific questions
        # like "suku bunga naik emas gimana" or "inflasi dan gold gimana".
        if (fund_phrase > 0 or fund_regex > 0) and fund_kw >= 2:
            # FUNDAMENTAL has strong domain signal — suppress MARKET
            market_score = min(market_score, fundamental_score - 1)
        elif fund_phrase > 0 or fund_regex > 0:
            if m_phrase == 0 and m_regex == 0:
                # MARKET has no specific phrases — FUNDAMENTAL wins
                market_score = 0

        # Step 11: Pick highest
        scores = {
            'MARKET': market_score,
            'FAQ': faq_score,
            'CURHAT': curhat_score,
            'FUNDAMENTAL': fundamental_score,
            'HELP': help_score,
        }
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        if best_score < 5:
            return 'UNKNOWN'

        # Set concept for FAQ
        if best_intent == 'FAQ':
            self._last_concept = concept

        return best_intent

    def get_matched_concept(self, raw_text: str) -> str | None:
        self.classify(raw_text)
        return self._last_concept
