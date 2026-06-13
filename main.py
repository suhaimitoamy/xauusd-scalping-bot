import sys
import time
import traceback
import logging
import os

from src.utils import load_environment, load_config
from src.formatter import setup_logger
from src.storage import Storage
from src.ws_client import WSClient
from src.candle_builder import CandleBuilder
from src.telegram_notifier import test_telegram, telegram_is_configured, send_telegram_message, get_telegram_status
from src.history_bootstrap import bootstrap_history
from src.ai_advisor import configure_ai, get_ai_response
from src.market_memory import MarketMemory
import importlib

_last_brain_mtime = 0

def get_brain_engine_class():
    global _last_brain_mtime
    brain_path = os.path.join(os.path.dirname(__file__), "src", "market_brain.py")
    try:
        current_mtime = os.path.getmtime(brain_path)
    except OSError:
        current_mtime = 0

    import src.market_brain
    if _last_brain_mtime != 0 and current_mtime > _last_brain_mtime:
        importlib.reload(src.market_brain)
        logger.info("[HOT-RELOAD] src.market_brain has been reloaded!")
    _last_brain_mtime = current_mtime
    
    return src.market_brain.BrainEngine
from src.signal_gate import SignalGate
from src.signal_tracker import track_signals
from src.adaptive_formatter import format_adaptive_signal, format_recent_events, format_brain_status
from src.ai_context_builder import build_compact_ai_context
from src.ai_trainer import AdaptiveTrainer
from src.rule_manager import RuleManager
from src.telegram_interactive import TelegramBotPolling
from src.local_knowledge_agent import LocalKnowledgeAgent
from src.market_alert_engine import MarketAlertEngine

logger = setup_logger("Main")


def get_candles(storage, symbol, signal_tf="M5"):
    signal_tf = str(signal_tf or "M5").upper()
    trigger_limit = 90 if signal_tf == "M1" else 80
    return (
        storage.get_recent_candles(symbol, signal_tf, trigger_limit),
        storage.get_recent_candles(symbol, "M15", 64),
        storage.get_recent_candles(symbol, "H1", 96),
    )


def _config_for_signal_tf(config, signal_tf):
    import copy
    cfg = copy.deepcopy(config or {})
    adaptive = cfg.setdefault('adaptive_brain', {})
    adaptive['signal_timeframe'] = str(signal_tf or 'M5').upper()
    adaptive['v6_lookbacks'] = adaptive.get('v6_lookbacks') or [6, 8, 12]
    return cfg


def build_signal(storage, symbol, bot_state, config, signal_tf="M5"):
    trigger_candles, m15, h1 = get_candles(storage, symbol, signal_tf)
    price = float(bot_state.get('last_price') or (trigger_candles[-1]['close'] if trigger_candles else 0) or 0)
    min_need = 14 if str(signal_tf).upper() == 'M1' else 14
    data_health = {'is_healthy': len(trigger_candles) >= min_need and len(m15) >= 5 and len(h1) >= 5}
    BrainEngineCls = get_brain_engine_class()
    brain = BrainEngineCls(storage, symbol=symbol, config=_config_for_signal_tf(config, signal_tf))
    return brain.analyze(price, trigger_candles, m15, h1, data_health)


def compact_ai_review(storage, symbol, bot_state, signal=None):
    price = float(bot_state.get('last_price') or 0)
    compact = build_compact_ai_context(storage, symbol, price, signal)
    prompt = (
        "Beri review singkat untuk Telegram berdasarkan compact DB context ini.\n"
        "Jangan buat level baru. Jangan kirim artikel. Maksimal 6 baris.\n"
        "Gunakan istilah SENTUH, BREAK, close confirm.\n\n"
        f"{compact}"
    )
    messages = [
        {"role": "system", "content": "You are a compact XAUUSD adaptive bot reviewer. Short Telegram output only."},
        {"role": "user", "content": prompt},
    ]
    fallback = "AI review offline. Gunakan /brain dan /events untuk membaca memori lokal."
    text, used = get_ai_response(messages, fallback, max_tokens=220)
    text = (text or '').strip()
    if not text:
        text = fallback
        used = False
    title = "🧠 AI TRAINER REVIEW" if used else "🧠 LOCAL REVIEW"
    return f"{title}\n{text}"


def approve_or_reject(storage, answer):
    rm = RuleManager(storage)
    if answer == 'yes':
        ok, msg = rm.approve_pending()
    else:
        ok, msg = rm.reject_pending()
    return msg


def command_response(storage, bot_state, symbol, config, command, args_text="", is_admin=True):
    command = (command or "").lower().strip()
    memory = MarketMemory(storage)

    if command in ('/yes', 'yes'):
        return approve_or_reject(storage, 'yes')
    if command in ('/no', 'no'):
        return approve_or_reject(storage, 'no')

    if command in ('/help', '/start'):
        return """🧠 XAUUSD Adaptive Brain Bot V7

Commands:
/signal - cek signal adaptive M5
/m1_signal - cek signal M1 agresif
/m5_signal - cek signal M5 rekomendasi
/daily_recap - rangkuman performa hari ini
/alerts - daftar 21 market alert V6
/brain - status otak + memory
/events - recent events
/ai_review - review compact AI
/trainer_review - latih dari trade terakhir
/pending - cek approval brain/rule
/methods - list 36 method aktif
/market_context - bias intraday + supply/demand
/supply_demand - level supply demand angka pasti
/ask [pertanyaan] - AI fallback berdasarkan data bot
/bot_health - cek status bot + Telegram
/chat_id - cek chat/user ID Telegram
/yes atau YES - approve pending
/no atau NO - reject pending
/price, /stats, /telegram_status, /test_telegram"""

    if command in ('/methods', '/method'):
        return """V7 METHODS ACTIVE
Total technical methods: 36
News filter: OFF

9 high-WR core methods:
- M1/M5 sweep 6/8/12
- M1/M5 break 6/8/12
- Bias filter tetap M15 + H1

6 user methods:
- METHOD_CRT_H4_SWEEP_BUY/SELL
- METHOD_CRT_D1_SWEEP_BUY/SELL
- METHOD_H1_BREAK_BUY/SELL

Killzone & Session methods:
- METHOD_NY_KILLZONE_REVERSAL_BUY/SELL
- METHOD_LONDON_KILLZONE_REVERSAL_BUY/SELL
- METHOD_ASIAN_TRAP_BUY/SELL

ICT methods:
- METHOD_ICT_TURTLE_SOUP_BUY/SELL
- METHOD_ICT_UNICORN_BUY/SELL
- METHOD_ICT_AMD_BUY/SELL
- METHOD_MOMENTUM_RIDE_BUY/SELL
- METHOD_PATTERN_SHOOTING_STAR
- METHOD_HIGH_WR_M15_SWEEP_SCALP_BUY/SELL
"""

    if command == '/alerts':
        return """V7 MARKET ALERTS: 21
1 FVG detected
2 FVG break/jebol
3 Impulsive move
4 OB touched
5 Support/Resistance touched
6 Break level
7 Sweep level
8 M15 pinbar/engulfing
9 Double top
10 Double bottom
11 Head and shoulder
12 SSL touched
13 BSL touched
14 BOS
15 CHoCH
16 Retest
17 Rejection
18 Displacement candle
19 Session high/low
20 Judas swing
21 Premium/discount + OTE

Entry features: M1 signal, M5 signal, BUY LIMIT, SELL LIMIT, averaging.
Total fitur utama: 26. Methods: 15. News filter: OFF."""
    if command == '/price':
        return f"Latest Price: {bot_state.get('last_price', 'Unknown')}"

    if command in ('/market_context', '/context', '/bias', '/intraday_bias'):
        from src.market_context_ai import format_market_context
        return format_market_context(storage, symbol, bot_state)

    if command in ('/supply_demand', '/sd', '/supply', '/demand'):
        from src.market_context_ai import format_supply_demand
        return format_supply_demand(storage, symbol, bot_state)

    if command == '/ask':
        if not args_text.strip():
            return 'Kirim: /ask pertanyaan kamu'
        from src.market_context_ai import TelegramMarketAI
        return TelegramMarketAI(storage, symbol=symbol, bot_state=bot_state).answer(
            args_text.strip(), chat_id='cli', user_id='cli', username='cli'
        )

    if command == '/m1_signal':
        sig = build_signal(storage, symbol, bot_state, config, signal_tf='M1')
        return format_adaptive_signal(sig, bot_state.get('last_price', 0))

    if command in ('/signal', '/m5_signal', '/premium_signal'):
        sig = build_signal(storage, symbol, bot_state, config, signal_tf='M5')
        return format_adaptive_signal(sig, bot_state.get('last_price', 0))

    if command == '/market_plan':
        from src.bot_views import format_scalping_plan
        return format_scalping_plan(storage, symbol, bot_state)

    if command in ('/brain', '/brain_status'):
        return format_brain_status(memory, symbol)

    if command in ('/events', '/recent_events'):
        price = float(bot_state.get('last_price') or 0)
        events = memory.recent_events(
            symbol, 20,
            current_price=price if price > 0 else None,
            max_age_minutes=180,
            max_distance_points=25.0,
        )
        return format_recent_events(events)

    if command in ('/ai_review', '/hourly_review', '/admin_review'):
        sig = build_signal(storage, symbol, bot_state, config, signal_tf='M5')
        return compact_ai_review(storage, symbol, bot_state, sig)

    if command == '/trainer_review':
        return AdaptiveTrainer(storage, symbol, config).review_latest_closed(bot_state.get('last_price', 0))

    if command == '/pending':
        pending = storage.get_pending_action()
        if not pending:
            return "Tidak ada aksi yang menunggu persetujuan."
        return (
            f"Pending Action #{pending.get('id')}\n"
            f"Type: {pending.get('action_type')}\n"
            f"Message:\n{pending.get('message')}\n\n"
            "Ketik YES untuk approve atau NO untuk reject."
        )

    if command in ('/super_ai', '/pattern_discovery'):
        if not is_admin:
            return "Maaf, command ini hanya untuk Admin."
        import subprocess
        import os
        script_path = os.path.join(os.path.dirname(__file__), 'src', 'pattern_discovery.py')
        subprocess.Popen([sys.executable, script_path])
        return "🧠 Super AI Pattern Discovery sedang dijalankan di background...\nProses ini memakan waktu 30-60 detik. Bot akan memberikan notifikasi otomatis setelah AI selesai merumuskan pola baru."

    if command == '/stats':
        today = storage.get_stats_today()
        return (
            f"Today: {today['total']} signals | Wins: {today['wins']} | Losses: {today['losses']}\n"
            f"Partial wins: {today.get('partial_wins', 0)} | Active: {today.get('active', 0)} | Protected: {today.get('protected', 0)} | Closed: {today.get('closed', 0)}"
        )

    if command in ('/daily_recap', '/recap', '/hari_ini'):
        from src.bot_views import daily_recap
        return daily_recap(storage)

    if command in ('/market_plan', '/poi'):
        from src.bot_views import format_scalping_plan
        return format_scalping_plan(storage, symbol, bot_state)

    if command in ('/fvg', '/fvg_map'):
        from src.bot_views import answer_area
        return answer_area(storage, symbol, bot_state, 'fvg')

    if command in ('/ob', '/order_block'):
        from src.bot_views import answer_area
        return answer_area(storage, symbol, bot_state, 'ob')

    if command in ('/liquidity', '/liq'):
        from src.bot_views import answer_area
        return answer_area(storage, symbol, bot_state, 'liquidity')

    if command == '/ote':
        from src.bot_views import answer_area
        return answer_area(storage, symbol, bot_state, 'ote')

    if command in ('/debug_fvg', '/debug_ob', '/debug_ote', '/debug_poi'):
        from src import bot_views
        fn = {
            '/debug_fvg': bot_views.debug_fvg,
            '/debug_ob': bot_views.debug_ob,
            '/debug_ote': bot_views.debug_ote,
            '/debug_poi': bot_views.debug_poi,
        }[command]
        return fn(storage, symbol, bot_state)

    if command == '/bot_health':
        tg = 'OK' if telegram_is_configured() else 'NOT_CONFIGURED'
        price = bot_state.get('last_price', 'Unknown')
        active = memory.active_signal()
        if active:
            return f"BOT HEALTH\nTelegram: {tg}\nPrice: {price}\nHigh-WR Mode: {config.get('adaptive_brain', {}).get('high_wr_only', True)}\nPending Orders: {config.get('adaptive_brain', {}).get('pending_orders', {}).get('enabled', True)}\nSignal Streams: M1 + M5 | Alerts: 21 | Features: 26 | Methods: 15\nBlocking active signal: #{active.get('id')} {active.get('direction')}"
        return f"BOT HEALTH\nTelegram: {tg}\nPrice: {price}\nHigh-WR Mode: {config.get('adaptive_brain', {}).get('high_wr_only', True)}\nPending Orders: {config.get('adaptive_brain', {}).get('pending_orders', {}).get('enabled', True)}\nSignal Streams: M1 + M5 | Alerts: 21 | Features: 26 | Methods: 15\nBlocking active signal: none"

    if command == '/current_rule':
        rule = storage.get_active_rule_version()
        if not rule:
            return "Belum ada active/trial rule version."
        return f"CURRENT RULE\n#{rule.get('id')} {rule.get('version_name')} | {rule.get('status')}\nCreated: {rule.get('created_at')}"

    if command == '/rule_review':
        try:
            from src.weekly_report import generate_rule_review
            return generate_rule_review(storage)
        except Exception as e:
            return f"Rule review error: {e}"

    if command == '/risk_review':
        try:
            m5, _, _ = get_candles(storage, symbol, 'M5')
            from src.risk_review import check_risk_review
            return check_risk_review(storage, m5, config)
        except Exception as e:
            return f"Risk review error: {e}"

    if command == '/trial_status':
        try:
            rows = storage.fetchall("SELECT status, COUNT(*) AS n FROM signals GROUP BY status")
            body = "\n".join([f"- {r.get('status')}: {r.get('n')}" for r in rows]) or "Belum ada signal."
            return f"TRIAL STATUS\n{body}"
        except Exception as e:
            return f"Trial status error: {e}"

    if command == '/rollback_rule':
        return "Rollback rule harus dilakukan manual dengan YES/NO approval. Tidak ada rollback otomatis dari command ini."

    if command == '/kb_stats':
        try:
            stats = LocalKnowledgeAgent(storage).stats()
            return f"Knowledge Base: {stats['knowledge_entries']} entries | Local answers: {stats['answered']}"
        except Exception as e:
            return f"Knowledge Base error: {e}"

    if command == '/telegram_status':
        return get_telegram_status()

    if command == '/test_telegram':
        return "Test message sent successfully." if test_telegram() else "Failed to send test message."

    if command == '/bootstrap_history':
        ok = bootstrap_history(storage, config)
        return "REST Bootstrap berhasil." if ok else "REST Bootstrap gagal/dilewati."

    if command == '/brain_versions':
        conn = storage.get_connection(); conn.row_factory = __import__('sqlite3').Row; cur = conn.cursor()
        cur.execute("SELECT * FROM brain_code_versions ORDER BY id DESC LIMIT 8")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        if not rows:
            return "Belum ada brain version."
        lines = ["BRAIN VERSIONS:"]
        for r in rows:
            lines.append(f"#{r.get('id')} {r.get('version_name')} | {r.get('status')} | syntax={r.get('syntax_ok')} | {r.get('created_at')}")
        return "\n".join(lines)

    return "Perintah tidak dikenali. Ketik /help."


def run_cli(storage, bot_state, symbol, config, tg_polling=None):
    print("==================================================")
    print("XAUUSD Adaptive Brain Bot V7")
    print("Commands: /signal, /m1_signal, /m5_signal, /alerts, /brain")
    print("          /pending, YES, NO, /price, /stats, /exit")
    print("==================================================\n")

    while True:
        try:
            cmd = input("Bot> ").strip()
            if not cmd:
                continue
            low = cmd.lower()
            if low == '/exit':
                if tg_polling:
                    tg_polling.stop()
                print("Exiting...")
                sys.exit(0)
            parts = cmd.split(" ", 1)
            command = parts[0]
            args_text = parts[1] if len(parts) > 1 else ""
            print(command_response(storage, bot_state, symbol, config, command, args_text, True))
        except (KeyboardInterrupt, EOFError):
            if tg_polling:
                tg_polling.stop()
            print("\nExiting...")
            sys.exit(0)
        except Exception as e:
            traceback.print_exc()
            print(f"CLI Error: {e}")


def main():
    logger.info("Initializing XAUUSD Adaptive Brain Bot...")
    load_environment()
    config = load_config("config.yaml")
    configure_ai(config)

    db_path = config.get("storage", {}).get("sqlite_path", "data/xauusd_bot.sqlite")
    storage = Storage(db_path)
    MarketMemory(storage).ensure_schema()
    knowledge_agent = LocalKnowledgeAgent(storage)
    symbol = config.get("symbol", "XAU/USD")

    rest_config = config.get("rest_bootstrap", {})
    if rest_config.get("run_on_startup", True):
        bootstrap_history(storage, config)

    bot_state = {'last_price': 0}
    alert_engine = MarketAlertEngine(storage, symbol=symbol, config=config)

    if telegram_is_configured():
        send_telegram_message("🧠 XAUUSD Adaptive Brain Bot V7 ONLINE\nM1 + M5 signals independent\nMarket alerts: 21 | Total fitur: 26 | Methods: 15\nNews filter: OFF\nSource: LOCAL BRAIN + AI TRAINER")

    def _send_signal_if_allowed(sig):
        if sig and sig.get('direction') != 'NO_TRADE':
            allowed, gate_msg = SignalGate(storage).check(sig)
            if not allowed:
                logger.info(f"Signal blocked: {gate_msg}")
                return
            storage.save_signal(sig)
            msg = format_adaptive_signal(sig, bot_state.get('last_price', 0))
            print(f"\n{msg}\nBot> ", end="")
            if telegram_is_configured():
                send_telegram_message(msg)
        else:
            reason = sig.get('reason') if sig else 'NO_TRADE'
            logger.info(reason)

    def handle_candle_closed(candle):
        logger.info(f"{candle.timeframe} Candle Closed: {candle.open_time} | Close: {candle.close}")
        try:
            if candle.timeframe != 'M1':
                alert_engine.process_closed_candle(candle)
        except Exception as e:
            logger.exception(f"V6 market alert error on {candle.timeframe} close: {e}")

        if candle.timeframe != 'M5':
            return
        try:
            sig = build_signal(storage, symbol, bot_state, config, signal_tf=candle.timeframe)
            _send_signal_if_allowed(sig)
        except Exception as e:
            logger.exception(f"Adaptive brain error on {candle.timeframe} close: {e}")

    candle_builder = CandleBuilder(storage=storage, on_candle_closed=handle_candle_closed)

    def handle_tick(tick_symbol, price, timestamp, raw_data):
        import time
        bot_state['last_price'] = price
        try:
            alert_engine.process_tick(tick_symbol, price, timestamp)
        except Exception as e:
            logger.error(f"V6 tick market alert error: {e}")
        
        # --- Impulsive Move Detection ---
        # DISABLED PER USER REQUEST
        # now_ts = time.time()
        # history = bot_state.setdefault('price_history', [])
        # history.append((now_ts, price))
        
        # Prune older than 60s
        # cutoff = now_ts - 60
        # while history and history[0][0] < cutoff:
        #     history.pop(0)
            
        # if len(history) > 1:
        #     oldest_price = history[0][1]
        #     diff = price - oldest_price
        #     if abs(diff) >= 3.0:
        #         last_warn = bot_state.setdefault('last_impulse_warning', 0)
        #         if now_ts - last_warn >= 300: # 5 minutes cooldown
        #             bot_state['last_impulse_warning'] = now_ts
        #             dir_str = "MELONJAK NAIK 🚀" if diff > 0 else "ANJLOK TURUN 🩸"
        #             msg = (
        #                 f"🚨 **WARNING: IMPULSIVE MOVE DETECTED!** 🚨\n\n"
        #                 f"XAU/USD {dir_str} tajam!\n"
        #                 f"Pergerakan: {abs(diff):.2f} poin dalam {int(now_ts - history[0][0])} detik\n"
        #                 f"Harga saat ini: {price:.2f}"
        #             )
        #             chat_id = os.getenv("TELEGRAM_DISCUSSION_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        #             if chat_id:
        #                 send_telegram_message(chat_id, msg)
        
        # --- Standard Tick Processing ---
        candle_builder.process_tick(tick_symbol, price, timestamp, raw_data)
        try:
            track_signals(storage, price, timestamp)
        except Exception as e:
            logger.error(f"Signal tracker error: {e}")
            
        try:
            from src.fvg_engine import update_all_fvg_status
            update_all_fvg_status(storage, price, symbol)
        except Exception as e:
            logger.error(f"FVG update error: {e}")

    ws_client = WSClient(config_path="config.yaml", on_tick_callback=handle_tick)
    ws_client.start()

    tg_polling = None
    if telegram_is_configured():
        def telegram_command_handler(chat_id, user_id, username, command, args_text, is_admin):
            return command_response(storage, bot_state, symbol, config, command, args_text, is_admin)

        tg_polling = TelegramBotPolling(
            command_handler=telegram_command_handler, 
            knowledge_agent=knowledge_agent,
            bot_state=bot_state,
            storage=storage
        )
        tg_polling.start()

    time.sleep(1)
    run_cli(storage, bot_state, symbol, config, tg_polling)


if __name__ == "__main__":
    main()
