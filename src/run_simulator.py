import os
import argparse
import glob
import logging
import sqlite3
import shutil
import time
import sys
from datetime import datetime as original_datetime, timezone, timedelta

class MockDatetime(original_datetime):
    @classmethod
    def now(cls, tz=None):
        import run_simulator
        if hasattr(run_simulator, 'GLOBAL_SIM_TS') and run_simulator.GLOBAL_SIM_TS:
            dt = original_datetime.fromtimestamp(run_simulator.GLOBAL_SIM_TS, timezone.utc)
            if tz:
                return dt.astimezone(tz)
            return dt
        return original_datetime.now(tz)

import datetime
datetime.datetime = MockDatetime
sys.modules['datetime'] = datetime

import sys
import csv
from datetime import datetime, timezone

# Add project root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Disable Telegram
os.environ["TELEGRAM_API_KEY"] = ""

from src.storage import Storage
from src.candle_builder import CandleBuilder
from src.market_brain import BrainEngine
from src.signal_gate import SignalGate
from src.signal_tracker import track_signals
from src.fvg_engine import update_all_fvg_status
from src.pnl_accounting import calculate_virtual_balance_report
from src import ai_trainer

def dummy_no_trade(*args, **kwargs):
    pass
ai_trainer.AdaptiveTrainer.evaluate_no_trade = dummy_no_trade

# Disable LLM network requests for the massive simulator run!
original_init = ai_trainer.AdaptiveTrainer.__init__
def patched_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.auto_ai_review = False
    self.auto_brain_draft = False
ai_trainer.AdaptiveTrainer.__init__ = patched_init

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("Simulator")

def load_config():
    import yaml
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

def get_db_stats(storage):
    conn = storage.get_connection()
    cur = conn.cursor()
    stats = {}
    
    # Get brain training stats
    cur.execute("SELECT pattern_key, wins, losses, score FROM brain_patterns")
    brain_stats = {row[0]: {'wins': row[1], 'losses': row[2], 'score': row[3]} for row in cur.fetchall()}
    stats['brain'] = brain_stats
    
    conn.close()
    return stats

import sqlite3

class DummyConn:
    def __init__(self, real_conn):
        self.real_conn = real_conn
    def close(self):
        pass # Prevent closing
    def commit(self):
        pass # Prevent frequent commits, we batch them
    def __getattr__(self, name):
        return getattr(self.real_conn, name)
    def __setattr__(self, name, value):
        if name == 'real_conn':
            super().__setattr__(name, value)
        else:
            setattr(self.real_conn, name, value)

def extract_month(path):
    import re
    m = re.search(r'(\d{6})', path)
    if m: return m.group(1)
    return 'UNKNOWN'

def run_simulation(csv_paths, limit=None):
    logger.info("Initializing Simulator Training Camp (GHOST MODE)...")
    config = load_config()
    symbol = config.get('symbol', 'XAU/USD')
    db_path = config.get('db_path', 'data/xauusd_bot.sqlite')
    ghost_db_path = db_path.replace('.sqlite', '_ghost.sqlite')
    
    # Setup modes
    import run_simulator
    append_mode = getattr(run_simulator, 'APPEND_GHOST', False)
    replace_mode = getattr(run_simulator, 'REPLACE_MONTH', False)
    test_run_mode = getattr(run_simulator, 'NEW_TEST_RUN', False)
    fast_mode = getattr(run_simulator, 'FAST_MODE', False)
    quiet_mode = getattr(run_simulator, 'QUIET_MODE', False)
    progress_every = max(1, int(getattr(run_simulator, 'PROGRESS_EVERY', 1000) or 1000))
    log_file = getattr(run_simulator, 'SIM_LOG_FILE', None)

    file_handler = None
    if log_file:
        os.makedirs(os.path.dirname(log_file) or '.', exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))
        logging.getLogger().addHandler(file_handler)

    if fast_mode or quiet_mode:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO if file_handler else logging.WARNING)
        for handler in root_logger.handlers:
            if handler is not file_handler and isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.WARNING)
        logger.setLevel(logging.INFO if file_handler else logging.WARNING)
    
    dataset_keys = list(set([extract_month(p) for p in csv_paths]))
    sim_type = 'TEST_RUN' if test_run_mode else 'MAIN'
    sim_id = "sim_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    
    setattr(run_simulator, 'CURRENT_SIM_ID', sim_id)
    setattr(run_simulator, 'CURRENT_SIM_TYPE', sim_type)
    
    # 1. Create Ghost DB to avoid locking the live bot
    import shutil
    
    if not append_mode:
        if os.path.exists(ghost_db_path):
            os.remove(ghost_db_path)
        shutil.copy2(db_path, ghost_db_path)
    else:
        if not os.path.exists(ghost_db_path):
            shutil.copy2(db_path, ghost_db_path)
            
        # Always wipe live state when starting simulator to prevent stale trades blocking execution
        global_conn = sqlite3.connect(ghost_db_path)
        tables_to_wipe = ['signals', 'signal_events', 'active_fvgs', 'active_order_blocks', 'active_ote_zones', 'active_breakers', 'pending_actions', 'brain_state', 'brain_decisions', 'candles', 'ticks', 'structure_events', 'brain_events']
        for table in tables_to_wipe:
            try:
                global_conn.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError:
                pass
        global_conn.commit()
        global_conn.close()
    
    # Gunakan In-Memory DB untuk performa SUPER NGEBUT
    disk_conn = sqlite3.connect(ghost_db_path)
    global_conn = sqlite3.connect(":memory:")
    disk_conn.backup(global_conn)
    disk_conn.close()
    
    global_conn.execute("PRAGMA synchronous = OFF")
    global_conn.execute("PRAGMA journal_mode = MEMORY")
    global_conn.execute("PRAGMA temp_store = MEMORY")
    
    # Duplicate Protection
    if not test_run_mode and os.path.exists(ghost_db_path):
        cur = global_conn.cursor()
        for dkey in dataset_keys:
            try:
                month_where = """
                    (json_extract(raw_context_json, '$.dataset_key') = ?
                     OR json_extract(json_extract(raw_context_json, '$.raw_context_json'), '$.dataset_key') = ?)
                    AND COALESCE(
                        json_extract(raw_context_json, '$.sim_type'),
                        json_extract(json_extract(raw_context_json, '$.raw_context_json'), '$.sim_type'),
                        'MAIN'
                    ) = 'MAIN'
                """
                cur.execute(f"SELECT count(*) FROM signals WHERE {month_where}", (dkey, dkey))
                count = cur.fetchone()[0]
                if count > 0:
                    if replace_mode:
                        logger.info(f"Replacing dataset {dkey} in Ghost DB...")
                        global_conn.execute(
                            f"DELETE FROM signal_events WHERE signal_id IN (SELECT id FROM signals WHERE {month_where})",
                            (dkey, dkey),
                        )
                        global_conn.execute(f"DELETE FROM signals WHERE {month_where}", (dkey, dkey))
                        global_conn.commit()
                    elif append_mode:
                        logger.error(f"Month {dkey} already exists in ghost research dataset. Use --replace-month or --new-test-run.")
                        sys.exit(1)
            except sqlite3.OperationalError:
                pass # JSON functions might not be supported or table empty

        if replace_mode:
            state_tables_to_wipe = [
                'active_fvgs', 'active_order_blocks', 'active_ote_zones',
                'active_breakers', 'pending_actions', 'brain_state',
                'brain_decisions', 'candles', 'ticks', 'structure_events',
                'brain_events'
            ]
            for table in state_tables_to_wipe:
                try:
                    global_conn.execute(f"DELETE FROM {table}")
                except sqlite3.OperationalError:
                    pass
            global_conn.commit()
    
    # Sandbox Brain Injection
    sandbox_brain = getattr(run_simulator, 'SANDBOX_BRAIN', None)
    if sandbox_brain and os.path.exists(sandbox_brain):
        logger.info(f"Injecting sandbox brain: {sandbox_brain}")
        try:
            with open(sandbox_brain, 'r') as f:
                sandbox_data = __import__('json').load(f)
            
            import run_simulator
            run_simulator.SANDBOX_RULES = sandbox_data
            
            cur = global_conn.cursor()
            for m in sandbox_data.get('methods', []):
                cur.execute(
                    """
                    INSERT OR IGNORE INTO brain_patterns
                    (pattern_key, direction, score, wins, losses, partials, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m['name'],
                        m.get('direction', 'BUY'),
                        0,
                        0,
                        0,
                        0,
                        'sandbox candidate',
                        datetime.now(timezone.utc).isoformat(),
                    )
                )
            global_conn.commit()
            logger.info("Sandbox brain loaded successfully!")
        except Exception as e:
            logger.error(f"Failed to load sandbox brain: {e}")
            sys.exit(1)
            
    # Wipe live state dari Ghost DB
    if not append_mode and not replace_mode and not test_run_mode:
        tables_to_wipe = ['signals', 'signal_events', 'active_fvgs', 'active_order_blocks', 'active_ote_zones', 'active_breakers', 'pending_actions', 'brain_state', 'brain_decisions', 'candles', 'ticks', 'structure_events', 'brain_events']
        for table in tables_to_wipe:
            try:
                global_conn.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError:
                pass
        global_conn.commit()
    
    class DummyCursor:
        def __init__(self, cursor):
            self.cursor = cursor
        def execute(self, query, params=None):
            import run_simulator
            if hasattr(run_simulator, 'GLOBAL_SIM_TS') and run_simulator.GLOBAL_SIM_TS:
                from datetime import datetime as orig_dt, timezone
                sim_time = orig_dt.fromtimestamp(run_simulator.GLOBAL_SIM_TS, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                query = query.replace("datetime('now'", f"datetime('{sim_time}'")
                query = query.replace("CURRENT_TIMESTAMP", f"'{sim_time}'")
            if params is None:
                return self.cursor.execute(query)
            return self.cursor.execute(query, params)
        def fetchone(self): return self.cursor.fetchone()
        def fetchall(self): return self.cursor.fetchall()
        def fetchmany(self, size=None): return self.cursor.fetchmany(size)
        def __iter__(self): return iter(self.cursor)
        @property
        def lastrowid(self): return self.cursor.lastrowid
        @property
        def rowcount(self): return self.cursor.rowcount
        def close(self): self.cursor.close()

    class DummyConn:
        def __init__(self, conn):
            self.conn = conn
            
        @property
        def row_factory(self):
            return self.conn.row_factory
            
        @row_factory.setter
        def row_factory(self, value):
            self.conn.row_factory = value
            
        def cursor(self):
            return DummyCursor(self.conn.cursor())
            
        def execute(self, query, params=None):
            import run_simulator
            if hasattr(run_simulator, 'GLOBAL_SIM_TS') and run_simulator.GLOBAL_SIM_TS:
                from datetime import datetime as orig_dt, timezone
                sim_time = orig_dt.fromtimestamp(run_simulator.GLOBAL_SIM_TS, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                query = query.replace("datetime('now'", f"datetime('{sim_time}'")
                query = query.replace("CURRENT_TIMESTAMP", f"'{sim_time}'")
            if params is None:
                return self.conn.execute(query)
            return self.conn.execute(query, params)
            
        def commit(self):
            pass
            
        def close(self):
            pass
            
    def fast_get_connection(self):
        return DummyConn(global_conn)
        
    Storage.get_connection = fast_get_connection
    storage = Storage()
    bot_state = {}

    stats_before = get_db_stats(storage)
    
    original_save_signal = storage.save_signal
    def patched_save_signal(sig):
        import run_simulator
        import json
        sim_id = getattr(run_simulator, 'CURRENT_SIM_ID', 'UNKNOWN')
        sim_type = getattr(run_simulator, 'CURRENT_SIM_TYPE', 'MAIN')
        dkey = getattr(run_simulator, 'CURRENT_DATASET_KEY', 'UNKNOWN')
        
        raw = sig.get('raw_context_json', '{}')
        try:
            raw_dict = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            raw_dict = {}
            
        raw_dict['simulation_id'] = sim_id
        raw_dict['dataset_key'] = dkey
        raw_dict['sim_type'] = sim_type

        sig['simulation_id'] = sim_id
        sig['dataset_key'] = dkey
        sig['sim_type'] = sim_type
        
        sig['raw_context_json'] = json.dumps(raw_dict)
        return original_save_signal(sig)
    storage.save_signal = patched_save_signal

    # Track signals created during this run
    signals_created = {'WIN': 0, 'LOSS': 0, 'PARTIAL_WIN': 0, 'PROTECTED': 0, 'ACTIVE': 0, 'TOTAL': 0}

    brain = BrainEngine(storage, symbol=symbol, config=config)

    def build_signal(storage, symbol, bot_state, config):
        m5 = storage.get_recent_candles(symbol, "M5", 60)
        m15 = storage.get_recent_candles(symbol, "M15", 32)
        h1 = storage.get_recent_candles(symbol, "H1", 12)
        price = float(bot_state.get('last_price') or (m5[-1]['close'] if m5 else 0) or 0)
        data_health = {'is_healthy': len(m5) >= 8}
        return brain.analyze(price, m5, m15, h1, data_health)

    def handle_m5_closed(candle):
        try:
            sig = build_signal(storage, symbol, bot_state, config)
            if sig and sig.get('direction') != 'NO_TRADE':
                allowed, gate_msg = SignalGate(storage).check(sig)
                if not allowed:
                    return
                storage.save_signal(sig)
                signals_created['TOTAL'] += 1
                signals_created['ACTIVE'] += 1
        except Exception as e:
            logger.error(f"Brain error on M5 close: {e}")

    candle_builder = CandleBuilder(storage=storage, on_m5_closed=handle_m5_closed)

    def process_pseudo_tick(price, timestamp):
        bot_state['last_price'] = price
        candle_builder.process_tick(symbol, price, timestamp, None)
        try:
            track_signals(storage, price, timestamp)
        except Exception:
            pass
        try:
            update_all_fvg_status(storage, price, symbol)
        except Exception:
            pass

    total_candles = 0
    start_sim_time = time.time()

    for path in csv_paths:
        if fast_mode or quiet_mode:
            print(f"Processing {path}...")
        else:
            logger.info(f"Processing {path}...")
        import run_simulator
        setattr(run_simulator, 'CURRENT_DATASET_KEY', extract_month(path))
        try:
            with open(path, 'r') as f:
                reader = csv.reader(f)
                header_skipped = False
                for row in reader:
                    if limit and total_candles >= limit:
                        break
                        
                    if len(row) < 6: continue
                    date_str, time_str, o_str, h_str, l_str, c_str = row[0], row[1], row[2], row[3], row[4], row[5]
                    
                    try:
                        dt = datetime.strptime(f"{date_str} {time_str}", "%Y.%m.%d %H:%M")
                        dt = dt.replace(tzinfo=timezone.utc)
                        ts = int(dt.timestamp())
                        
                        import run_simulator
                        run_simulator.GLOBAL_SIM_TS = ts
                        
                        o = float(o_str)
                        h = float(h_str)
                        l = float(l_str)
                        c = float(c_str)
                    except ValueError as ve:
                        if not header_skipped:
                            header_skipped = True
                            continue
                        logger.error(f"Format CSV tidak dikenali pada baris: {row}")
                        logger.error(f"Diharapkan format: YYYY.MM.DD HH:MM,Open,High,Low,Close. Detail: {ve}")
                        sys.exit(1)
                    
                    # Generate 4 pseudo-ticks to simulate intra-candle movement
                    process_pseudo_tick(o, ts)
                    if c > o:
                        process_pseudo_tick(l, ts + 15)
                        process_pseudo_tick(h, ts + 30)
                    else:
                        process_pseudo_tick(h, ts + 15)
                        process_pseudo_tick(l, ts + 30)
                    process_pseudo_tick(c, ts + 45)
                    
                    total_candles += 1
                    if total_candles % progress_every == 0:
                        global_conn.commit()
                        if fast_mode or quiet_mode:
                            print(f"Progress: Simulated {total_candles} candles...")
                        else:
                            logger.info(f"Progress: Simulated {total_candles} candles...")
                        
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            
        if limit and total_candles >= limit:
            logger.info(f"Limit of {limit} candles reached. Stopping simulation.")
            break

    global_conn.commit()
    elapsed = time.time() - start_sim_time
    stats_after = get_db_stats(storage)
    
    # 2. Merge Brain Patterns back to Live DB safely.
    # Sandbox/test simulations must not mutate the live brain.
    sandbox_mode = bool(getattr(run_simulator, 'SANDBOX_BRAIN', None))
    if sandbox_mode or test_run_mode:
        logger.info("Sandbox/test run: skipped merge back into LIVE database.")
    else:
        try:
            live_conn = sqlite3.connect(db_path, timeout=10.0)
            live_conn.execute("ATTACH DATABASE ? AS ghost", (ghost_db_path,))
            live_conn.execute("""
                INSERT OR REPLACE INTO brain_patterns
                SELECT * FROM ghost.brain_patterns
            """)
            live_conn.commit()
            live_conn.close()
            logger.info("Successfully merged training data into LIVE database!")
        except Exception as e:
            logger.error(f"Failed to merge ghost db into live db: {e}")
        
    # Cleanup ghost db
    import run_simulator
    if not getattr(run_simulator, 'KEEP_GHOST', False):
        if os.path.exists(ghost_db_path):
            try: os.remove(ghost_db_path)
            except: pass
    
    print("\n" + "="*50)
    print("📊 HASIL SIMULASI (TRAINING CAMP)")
    print("="*50)
    print(f"Durasi Proses   : {elapsed:.2f} detik")
    print(f"Candle Diproses : {total_candles}")
    print(f"Total Signal    : {signals_created['TOTAL']}")
    
    print("\n🧠 PATTERN YANG BERUBAH DI BRAIN:")
    changes = 0
    for pattern, after_stats in stats_after['brain'].items():
        before_stats = stats_before['brain'].get(pattern, {'wins': 0, 'losses': 0, 'score': 0.0})
        w_diff = after_stats['wins'] - before_stats['wins']
        l_diff = after_stats['losses'] - before_stats['losses']
        s_diff = after_stats['score'] - before_stats['score']
        
        if w_diff != 0 or l_diff != 0 or s_diff != 0:
            print(f"- {pattern}: Wins +{w_diff}, Losses +{l_diff}, Score {s_diff:+.1f}")
            changes += 1
            
    if changes == 0:
        if signals_created['TOTAL'] == 0:
            print("- No trade generated. (Tidak ada sinyal yang memenuhi syarat di data ini)")
        else:
            print("- (Tidak ada pola yang mendapatkan win/loss tertutup selama simulasi ini)")
    
    print("="*50)
    
    # Virtual Balance Tracker
    init_bal = getattr(run_simulator, 'INITIAL_BALANCE', 0)
    if init_bal > 0:
        risk_percent = getattr(run_simulator, 'RISK_PERCENT', 1.0)
        report = calculate_virtual_balance_report(
            global_conn,
            initial_balance=init_bal,
            risk_percent=risk_percent,
            sim_id=sim_id,
            dataset_keys=dataset_keys,
            sim_type=sim_type,
        )
        
        print("\n" + "="*50)
        print("💰 VIRTUAL BALANCE REPORT")
        print("="*50)
        print(f"Initial Balance  : ${report['initial_balance']:.2f}")
        print(f"Ending Balance   : ${report['ending_balance']:.2f}")
        print(f"Net P/L          : ${report['net_pl']:.2f} ({report['net_pl_pct']:+.2f}%)")
        print(f"Max Drawdown     : ${report['max_drawdown']:.2f} ({report['max_dd_pct']:.2f}%)")
        print(f"Winrate          : {report['winrate']:.2f}%")
        print(f"Total Trades     : {report['total_trades']}")
        print(f"Wins             : {report['wins']} (TP2 {report['tp2_wins']}, TP3 {report['full_wins']}, Partial {report['partial_wins']})")
        print(f"Losses           : {report['losses']}")
        print(f"Profit Factor    : {report['profit_factor']:.2f}")
        print(f"Average Win      : ${report['average_win']:.2f}")
        print(f"Average Loss     : ${report['average_loss']:.2f}")
        print(f"Largest W Streak : {report['largest_win_streak']}")
        print(f"Largest L Streak : {report['largest_loss_streak']}")
        if report['ending_balance'] < report['initial_balance']:
            loss_amount = report['initial_balance'] - report['ending_balance']
            loss_percent = (loss_amount / report['initial_balance']) * 100 if report['initial_balance'] else 0
            print(f"Net Loss         : ${loss_amount:.2f}")
            print(f"Loss Percent     : {loss_percent:.2f}%")
        print("="*50)
        
        import json
        with open(f"data/virtual_sim_report.json", "w") as f:
            json.dump(report, f, indent=2)

    # FLUSH IN-MEMORY DB BACK TO DISK
    print("\nMenyimpan hasil simulasi ke disk (Ghost DB)...")
    disk_conn = sqlite3.connect(ghost_db_path)
    global_conn.backup(disk_conn)
    disk_conn.close()
    print("Selesai menyimpan!")

def find_csv_files():
    files = glob.glob("/storage/emulated/0/Download/*candle*.csv") + \
            glob.glob("/storage/emulated/0/Download/*xauusd*.csv") + \
            glob.glob("/storage/emulated/0/Download/DAT_MT_XAUUSD_M1*.csv") + \
            glob.glob("/storage/emulated/0/Download/ADM/DAT_MT_XAUUSD_M1*.csv")
    csv_paths = list(set([f for f in files if os.path.isfile(f)]))
    csv_paths.sort()
    return csv_paths

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XAUUSD Bot Simulator Backtest")
    parser.add_argument('--file', type=str, help='Spesifik path file CSV yang ingin disimulasikan')
    parser.add_argument('--month', type=str, help='Filter file CSV berdasarkan bulan (misal: 202601)')
    parser.add_argument('--from', dest='from_month', type=str, help='Filter mulai dari bulan (misal: 202501)')
    parser.add_argument('--to', dest='to_month', type=str, help='Filter sampai bulan (misal: 202612)')
    parser.add_argument('--limit', type=int, help='Batasi jumlah candle yang diproses (untuk test cepat)')
    parser.add_argument('--all', action='store_true', help='Paksa jalankan semua file CSV yang ditemukan')
    parser.add_argument('--keep-ghost', action='store_true', help='Jangan hapus ghost db setelah simulasi selesai')
    parser.add_argument('--append-ghost', action='store_true', help='Lanjutkan data simulasi ke ghost db sebelumnya')
    parser.add_argument('--replace-month', action='store_true', help='Hapus data lama bulan ini dan jalankan ulang')
    parser.add_argument('--new-test-run', action='store_true', help='Jalankan simulasi sebagai eksperimen (tidak masuk riset AI utama)')
    parser.add_argument('--strict-rr', action='store_true', help='Gunakan Strict RR 1:2 (Tanpa TP1/BE)')
    parser.add_argument('--initial-balance', type=float, default=0, help='Modal awal virtual (misal 3000)')
    parser.add_argument('--risk-percent', type=float, default=1.0, help='Persentase resiko SL per trade (default 1.0)')
    parser.add_argument('--sandbox-brain', type=str, help='Path ke file JSON sandbox brain')
    parser.add_argument('--fast', action='store_true', help='Mode simulasi foreground cepat: output terminal diringkas')
    parser.add_argument('--quiet', action='store_true', help='Kurangi output terminal tanpa mengubah logic entry')
    parser.add_argument('--progress-every', type=int, default=1000, help='Interval progress candle (default 1000, contoh 10000)')
    parser.add_argument('--log-file', type=str, help='Simpan detail log ke file, contoh logs/sim_202605.log')
    
    args = parser.parse_args()
    
    available_csvs = find_csv_files()
    
    if args.keep_ghost:
        import run_simulator
        run_simulator.KEEP_GHOST = True
        
    if args.append_ghost:
        import run_simulator
        run_simulator.APPEND_GHOST = True
        
    if args.replace_month:
        import run_simulator
        run_simulator.REPLACE_MONTH = True
        run_simulator.APPEND_GHOST = True # implicitly append to ghost db
        run_simulator.KEEP_GHOST = True
        
    if args.new_test_run:
        import run_simulator
        run_simulator.NEW_TEST_RUN = True
        run_simulator.APPEND_GHOST = True
        run_simulator.KEEP_GHOST = True
        
    if args.strict_rr:
        import run_simulator
        run_simulator.STRICT_RR = True
    
    if args.sandbox_brain:
        import run_simulator
        run_simulator.SANDBOX_BRAIN = args.sandbox_brain

    if args.fast:
        import run_simulator
        run_simulator.FAST_MODE = True

    if args.quiet:
        import run_simulator
        run_simulator.QUIET_MODE = True

    if args.progress_every:
        import run_simulator
        run_simulator.PROGRESS_EVERY = args.progress_every

    if args.log_file:
        import run_simulator
        run_simulator.SIM_LOG_FILE = args.log_file
        
    if args.initial_balance > 0:
        import run_simulator
        run_simulator.INITIAL_BALANCE = args.initial_balance
        
    if args.risk_percent:
        import run_simulator
        run_simulator.RISK_PERCENT = args.risk_percent
        
    if args.file:
        if not os.path.exists(args.file):
            logger.error(f"File {args.file} tidak ditemukan!")
            sys.exit(1)
        csv_paths = [args.file]
    elif args.from_month and args.to_month:
        import re
        csv_paths = []
        for f in available_csvs:
            m = re.search(r'(\d{6})', f)
            if m:
                month_str = m.group(1)
                if args.from_month <= month_str <= args.to_month:
                    csv_paths.append(f)
        if not csv_paths:
            logger.error(f"Tidak ada file CSV untuk periode {args.from_month} - {args.to_month}")
            sys.exit(1)
    elif args.month:
        csv_paths = [f for f in available_csvs if args.month in f]
        if not csv_paths:
            logger.error(f"Tidak ada file CSV yang mengandung teks '{args.month}'")
            sys.exit(1)
    elif args.all:
        csv_paths = available_csvs
    else:
        print("💡 PENGGUNAAN SIMULATOR:")
        print("Silakan tentukan target simulasi Anda dengan menambahkan flag. Contoh:")
        print("  python3 src/run_simulator.py --file /sdcard/Download/ADM/DAT_MT_XAUUSD_M1_202601.csv")
        print("  python3 src/run_simulator.py --month 202601")
        print("  python3 src/run_simulator.py --from 202501 --to 202612 --keep-ghost --append-ghost")
        print("  python3 src/run_simulator.py --all")
        print("  python3 src/run_simulator.py --month 202601 --limit 5000\n")
        
        print("📂 FILE CSV XAUUSD YANG DITEMUKAN DI HP ANDA:")
        if available_csvs:
            for f in available_csvs:
                print(f"  - {f}")
        else:
            print("  (Tidak ada file CSV yang ditemukan di folder Download)")
        sys.exit(0)
        
    run_simulation(csv_paths, limit=args.limit)
