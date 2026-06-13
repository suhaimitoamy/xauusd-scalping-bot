import threading
import time
import logging
from src.telegram_notifier import send_telegram_message, telegram_is_configured
from src.ai_advisor import get_ai_response
from src.bot_views import format_scalping_plan, build_context, _fmt

logger = logging.getLogger("AutomatedTasks")


class AutomatedTasks:
    def __init__(self, storage, symbol, config, bot_state):
        self.storage = storage
        self.symbol = symbol
        self.config = config
        self.bot_state = bot_state
        self.running = False
        self.last_poi_text = None

    def start(self):
        self.running = True
        threading.Thread(target=self._run_poi_summary_loop, daemon=True).start()
        threading.Thread(target=self._run_hourly_review_loop, daemon=True).start()
        threading.Thread(target=self._run_daily_recap_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def send_poi_summary(self, manual=False, use_ai=False):
        msg = format_scalping_plan(self.storage, self.symbol, self.bot_state)
        if not manual and self.last_poi_text == msg:
            msg += "\n\nCatatan:\nArea belum berubah."
        self.last_poi_text = msg
        if use_ai:
            messages = [
                {"role": "system", "content": "Kamu AI Challenger XAUUSD. Tambahkan AI Note 1 kalimat pendek. Jangan ubah angka. Jangan artikel."},
                {"role": "user", "content": msg}
            ]
            ai_note, used = get_ai_response(messages, fallback_text="", max_tokens=80)
            if used and ai_note:
                msg += f"\n\nAI Note:\n{ai_note}"
        if telegram_is_configured():
            send_telegram_message(msg)
        return msg

    def send_hourly_review(self, manual=False, send_telegram=True):
        ctx = build_context(self.storage, self.symbol, self.bot_state)
        h1 = ctx.get('h1', [])
        if not h1:
            return "Data belum cukup untuk 1H Review"
        last = h1[-1]
        s = ctx.get('structure', {})
        price_open = last.get('open')
        price_close = last.get('close')
        event_parts = []
        if s.get('sweep_type'):
            event_parts.append('Sweep')
        if s.get('reclaim_valid'):
            event_parts.append('Reclaim')
        if s.get('break_type'):
            event_parts.append(s.get('break_type'))
        if s.get('retest_mode') and s.get('retest_mode') != 'NONE':
            event_parts.append('Retest mode')
        events = ', '.join(event_parts) if event_parts else 'Belum ada event valid'
        plan = 'WATCH SELL' if str(s.get('m15_bias')).lower() == 'bearish' else ('WATCH BUY' if str(s.get('m15_bias')).lower() == 'bullish' else 'WAIT')
        area = self._area_from_ctx(ctx)
        msg = (
            f"🧠 XAUUSD 1H Review {ctx['time']}\n\n"
            f"Ringkasan 1 jam:\n"
            f"Harga bergerak dari {_fmt(price_open)} ke {_fmt(price_close)}.\n"
            f"Event: {events}.\n\n"
            f"Kondisi sekarang:\n"
            f"Bias scalping: {s.get('m15_bias', 'N/A')}\n"
            f"Phase: {s.get('trend', 'N/A')}\n\n"
            f"Area pantau:\n{area}\n\n"
            f"Plan:\n{plan}. Tunggu konfirmasi M5, jangan kejar harga.\n\n"
            f"Kesimpulan:\nWAIT kalau belum ada retest/reclaim yang bersih."
        )
        messages = [
            {"role": "system", "content": "Kamu AI Challenger XAUUSD. Beri AI Note 1 kalimat pendek. Jangan ubah angka. Jangan artikel."},
            {"role": "user", "content": msg}
        ]
        ai_note, used = get_ai_response(messages, fallback_text="", max_tokens=80)
        if used and ai_note:
            msg += f"\n\nAI Note:\n{ai_note}"
        if send_telegram and telegram_is_configured():
            send_telegram_message(msg)
        return msg

    def _area_from_ctx(self, ctx):
        from src.bot_views import _area
        return _area(ctx)

    def _run_poi_summary_loop(self):
        while self.running:
            time.sleep(900)
            if self.running and self.config.get('poi_summary', {}).get('enabled', True):
                try:
                    self.send_poi_summary(manual=False, use_ai=False)
                except Exception as e:
                    logger.error(f"Error sending POI Summary: {e}")

    def _run_hourly_review_loop(self):
        while self.running:
            time.sleep(3600)
            if self.running and self.config.get('ai_hourly_review', {}).get('enabled', True):
                try:
                    self.send_hourly_review(manual=False)
                except Exception as e:
                    logger.error(f"Error sending Hourly Review: {e}")

    def send_daily_recap(self):
        from src.local_knowledge_agent import LocalKnowledgeAgent
        try:
            agent = LocalKnowledgeAgent(self.storage)
            recap_msg = agent._handle_market("rekap hari ini")
            if telegram_is_configured():
                send_telegram_message(recap_msg)
        except Exception as e:
            logger.error(f"Error sending Daily Recap: {e}")

    def _run_daily_recap_loop(self):
        from datetime import datetime, timezone
        last_sent_day = None
        while self.running:
            now = datetime.now(timezone.utc)
            # Target 14:00 UTC (which is 21:00 WIB)
            if now.hour == 14 and now.minute == 0:
                day_str = now.strftime('%Y-%m-%d')
                if last_sent_day != day_str:
                    try:
                        self.send_daily_recap()
                        last_sent_day = day_str
                    except Exception as e:
                        logger.error(f"Error in daily recap loop: {e}")
            time.sleep(30) # check every 30 seconds

