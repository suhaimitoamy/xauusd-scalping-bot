import os
import time
import requests
import logging
from threading import Thread

logger = logging.getLogger("TelegramInteractive")


def normalize_telegram_command(text: str) -> str:
    if not text:
        return ""

    parts = text.strip().split(maxsplit=1)
    command = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    if command.startswith("/") and "@" in command:
        command = command.split("@", 1)[0]

    return f"{command} {rest}".strip()


class TelegramBotPolling:
    def __init__(self, command_handler, knowledge_agent=None, bot_state=None, storage=None):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.discussion_chat_id = os.getenv("TELEGRAM_DISCUSSION_CHAT_ID")
        self.admin_ids = [x.strip() for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip()]
        self.allowed_chat_ids = {str(x).strip() for x in (self.chat_id, self.discussion_chat_id) if str(x or '').strip()}
        self.command_handler = command_handler
        self.knowledge_agent = knowledge_agent
        self.bot_state = bot_state or {}
        self.storage = storage
        self.ai_fallback = None
        ai_fallback_enabled = os.getenv("TELEGRAM_AI_FALLBACK_ENABLED", "false").lower() in ("true", "1", "yes", "on")
        if storage is not None and ai_fallback_enabled:
            try:
                from src.market_context_ai import TelegramMarketAI
                self.ai_fallback = TelegramMarketAI(storage, bot_state=self.bot_state)
            except Exception as e:
                logger.warning(f"Telegram AI fallback init failed: {e}")
        self.offset = 0
        self.running = False
        self.user_state = {}

    def start(self):
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not found, interactive mode disabled.")
            return
        self._delete_webhook_if_any()
        self.running = True
        Thread(target=self._poll_loop, daemon=True).start()
        logger.info("Telegram interactive polling started.")

    def _delete_webhook_if_any(self):
        try:
            url = f"https://api.telegram.org/bot{self.token}/deleteWebhook"
            resp = requests.post(url, json={"drop_pending_updates": False}, timeout=10)
            if not resp.ok:
                logger.warning(f"deleteWebhook failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"deleteWebhook error: {e}")

    def stop(self):
        self.running = False

    def is_admin(self, user_id, user=None):
        user = user or {}
        if user.get("username") == "GroupAnonymousBot":
            return True
        if not self.admin_ids:
            return True
        return str(user_id) in self.admin_ids

    def _chat_allowed(self, chat_id, is_admin):
        if is_admin:
            return True
        if not self.allowed_chat_ids:
            return True
        return str(chat_id) in self.allowed_chat_ids

    def _poll_loop(self):
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        while self.running:
            try:
                resp = requests.get(url, params={"offset": self.offset, "timeout": 30}, timeout=35)
                resp.raise_for_status()
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        self._handle_update(update)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                now = time.time()
                if not hasattr(self, '_last_net_err') or now - self._last_net_err > 120:
                    logger.warning("Telegram polling timeout, retrying..." if isinstance(e, requests.exceptions.Timeout) else f"Telegram network error: {e}, retrying...")
                    self._last_net_err = now
                time.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error in polling: {e}")
                time.sleep(5)
            time.sleep(1)

    def _cooldown_ok(self, user_id, command, is_admin):
        if is_admin or command == '/help':
            return True, ""
        now = time.time()
        st = self.user_state.setdefault(user_id, {"count": 0, "window_start": now, "last_light": 0, "last_ai": 0, "blocked_until": 0})
        if now < st.get("blocked_until", 0):
            mins = int((st['blocked_until'] - now) / 60) + 1
            return False, f"Cooldown aktif. Coba lagi sekitar {mins} menit lagi."
        if now - st.get("window_start", now) > 300:
            st.update({"count": 0, "window_start": now})
        ai_commands = {'/ask','/market_plan','/admin_review','/hourly_review','/send_poi_ai','/rule_review','/risk_review','/ai_review','/trainer_review'}
        if command in ai_commands:
            if now - st.get("last_ai", 0) < 30:
                return False, "Cooldown AI 30 detik aktif."
            st['last_ai'] = now
        else:
            if now - st.get("last_light", 0) < 5:
                return False, "Cooldown 5 detik aktif."
            st['last_light'] = now
        st['count'] += 1
        if st['count'] > 7:
            st['blocked_until'] = now + 300
            st['count'] = 0
            return False, "Cooldown aktif. Coba lagi sekitar 5 menit lagi."
        return True, ""

    def _get_reply_markup(self, is_admin):
        keyboard = [
            [{"text": "⚠️ M1 Signal"}, {"text": "✅ M5 Signal"}],
            [{"text": "🟢 Signal"}, {"text": "📣 Alerts"}],
            [{"text": "💰 Price"}, {"text": "🧠 Brain"}],
            [{"text": "📌 Methods"}, {"text": "📊 Context"}],
            [{"text": "📍 Supply Demand"}, {"text": "🧾 Events"}],
            [{"text": "📊 Stats"}, {"text": "📋 Recap"}],
            [{"text": "🧠 AI Review"}, {"text": "🩺 Health"}],
            [{"text": "⚖️ Pending"}, {"text": "❓ Help"}],
            [{"text": "🆔 Chat ID"}]
        ]
        
        show_admin = True
        if self.admin_ids and not is_admin:
            show_admin = False
            
        if show_admin:
            keyboard.append([{"text": "⚙️ Admin"}, {"text": "🧪 Debug"}])
            
        return {
            "keyboard": keyboard,
            "resize_keyboard": True,
            "is_persistent": True
        }


    @staticmethod
    def _split_free_text(text):
        """Split multi-question Telegram messages into clean user lines."""
        raw = (text or '').strip()
        if not raw:
            return []
        lines = [ln.strip(' -•\t') for ln in raw.splitlines()]
        lines = [ln for ln in lines if ln]
        if not lines:
            return [raw]
        # Keep normal paragraph as one question; split only clear multi-line questions.
        return lines[:8]

    @staticmethod
    def _shortcut_command_for_text(text):
        """Route natural Telegram questions to local bot commands when intent is clearly market-data based."""
        low = (text or '').lower().strip()
        if not low or low.startswith('/'):
            return None
        # Concept explanation must stay in local knowledge, not area command.
        explanation_markers = ('apa itu', 'itu apa', 'artinya', 'maksud', 'jelaskan', 'jelasin', 'pengertian', 'definisi', 'gimana cara', 'bagaimana cara', 'maksudnya')
        if any(m in low for m in explanation_markers):
            return None
            
        where_markers = (
            'dimana', 'di mana', 'mana', 'area', 'zona', 'level', 'titik', 'posisi',
            'dekat', 'terdekat', 'aktif', 'terbaru', 'berapa', 'harga berapa', 'di harga'
        )
        
        # 1. MARKET AREAS (/fvg, /ob, /liquidity, etc)
        if any(m in low for m in where_markers):
            if any(k in low for k in ('liquidity', 'likuiditas', 'likuidity', 'liq', 'bsl', 'ssl', 'sweep', 'sapuan')):
                return '/liquidity'
            if any(k in low for k in ('fvg', 'fair value gap', 'imbalance', 'imb', 'gap kosong')):
                return '/fvg'
            if any(k in low for k in ('order block', 'orderblock')) or low == 'ob' or low.startswith('ob ') or ' ob ' in low:
                return '/ob'
            if any(k in low for k in ('ote', 'fibo', 'fibonacci', 'discount', 'premium', 'golden ratio', 'retracement')):
                return '/ote'
            if any(k in low for k in ('poi', 'point of interest', 'area pantau', 'zona pantau', 'fokus utama')):
                return '/poi'
            if any(k in low for k in ('supply', 'demand', 'sd zone', 's d', 'support', 'resistance', 'snr', 'sr', 's&r', 'snd', 's&d', 'atap', 'lantai', 'resisten', 'supot')):
                return '/supply_demand'
                
        # 2. MARKET CONTEXT (/market_context)
        if any(k in low for k in ('bias intraday', 'konteks market', 'market context', 'context market', 'arah trend', 'trend hari ini', 'struktur market', 'market structure', 'choch', 'bos', 'trend sekarang')):
            return '/market_context'
            
        # 3. DAILY RECAP (/daily_recap)
        if any(k in low for k in ('rekap hari ini', 'recap hari ini', 'performa hari ini', 'hasil hari ini', 'profit hari ini', 'loss hari ini', 'winrate hari ini', 'rangkuman', 'hari ini gimana', 'cek performa', 'hasil trade')):
            return '/daily_recap'
            
        # 4. MARKET PLAN / MAPPING (/market_plan)
        if any(k in low for k in ('mappingan', 'mapingan', 'mapping hari ini', 'maping hari ini', 'mapping gold', 'maping gold', 'mapping xau', 'trading plan', 'skenario hari ini', 'plan hari ini', 'rencana trading', 'plan gold')):
            return '/market_plan'
            
        # 5. SIGNALS (/signal)
        if any(k in low for k in ('minta sinyal', 'cek sinyal', 'sinyal sekarang', 'sinyal dong', 'setup sekarang')):
            return '/signal'
            
        # 5. CURRENT PRICE (/price)
        if any(k in low for k in ('harga sekarang', 'price sekarang', 'harga gold', 'harga xau', 'gold di berapa', 'xau di berapa', 'running price')):
            return '/price'
            
        # 6. STATS & REVIEW (/stats, /bot_health, /methods, /events)
        if any(k in low for k in ('statistik', 'total trade', 'winrate bot', 'akurasi bot', 'persentase win')):
            return '/stats'
        if any(k in low for k in ('metode apa', 'strategi apa', 'pakai strategi apa', 'rule apa', 'list metode')):
            return '/methods'
        if any(k in low for k in ('status bot', 'bot jalan gak', 'bot sehat', 'cek bot', 'koneksi bot', 'bot nyala')):
            return '/bot_health'
        if any(k in low for k in ('berita terbaru', 'event hari ini', 'kejadian market', 'recent events', 'ada apa di market')):
            return '/events'
            
        return None

    @staticmethod
    def _trim_for_telegram(text, limit=3900):
        text = str(text or '').strip()
        if len(text) <= limit:
            return text
        return text[:limit].rsplit('\n', 1)[0].rsplit(' ', 1)[0] + '...'

    def _answer_free_text(self, text, chat_id, user_id, username, is_admin):
        """Answer normal Telegram messages accurately, one line at a time, with correct source labels."""
        if not self.knowledge_agent:
            return None
        answers = []
        for line in self._split_free_text(text):
            command = self._shortcut_command_for_text(line)
            if command:
                try:
                    resp = self.command_handler(chat_id, user_id, username, command, "", is_admin)
                    if resp:
                        answers.append(f"🤖 Dijawab oleh Bot Lokal\n\n{resp}")
                    continue
                except Exception as e:
                    logger.exception(f"Natural command shortcut failed for {command}: {e}")
            ans = self.knowledge_agent.answer(
                line,
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                bot_state=self.bot_state
            ) if self.knowledge_agent else None
            local_miss = (not ans) or ('Aku belum punya jawaban lokal yang cocok' in str(ans))
            if local_miss and self.ai_fallback:
                try:
                    ai_ans = self.ai_fallback.answer(line, chat_id=chat_id, user_id=user_id, username=username)
                    if ai_ans:
                        answers.append(ai_ans)
                        continue
                except Exception as e:
                    logger.exception(f"Telegram AI fallback error: {e}")
            if ans:
                # Ensure no AI label leaks through for local knowledge only
                ans = ans.replace('🧠 Dijawab oleh Bot Lokal', '🤖 Dijawab oleh Bot Lokal')
                answers.append(ans)
        if not answers:
            return None
        if len(answers) == 1:
            return answers[0]
        combined = []
        for idx, ans in enumerate(answers, 1):
            combined.append(f"[{idx}] {ans}")
        return self._trim_for_telegram("\n\n".join(combined))

    def _handle_update(self, update):
        message = update.get("message")
        if not message:
            return
        # IMPORTANT: Only read the user's fresh message text.
        # Do NOT use reply_to_message text as the primary question.
        text = normalize_telegram_command(message.get("text", ""))
        if not text:
            return
        
        button_mapping = {
            "⚠️ M1 Signal": "/m1_signal",
            "✅ M5 Signal": "/m5_signal",
            "📣 Alerts": "/alerts",
            "🟢 Signal": "/signal",
            "🧠 Brain": "/brain",
            "🧾 Events": "/events",
            "🧠 AI Review": "/ai_review",
            "⚖️ Pending": "/pending",
            "📊 Market Plan": "/market_plan",
            "📊 Context": "/market_context",
            "📍 Supply Demand": "/supply_demand",
            "📍 POI Map": "/poi",
            "🧩 FVG / OB": "/fvg_ob_menu",
            "💧 Liquidity": "/liquidity",
            "📐 OTE": "/ote",
            "⚙️ Admin": "/admin_menu",
            "🧪 Debug": "/debug_menu",
            "💰 Price": "/price",
            "📌 Methods": "/methods",
            "📊 Stats": "/stats",
            "📋 Recap": "/daily_recap",
            "🩺 Health": "/bot_health",
            "🆔 Chat ID": "/chat_id",
            "❓ Help": "/help"
        }
        
        if text in button_mapping:
            text = button_mapping[text]

        if text.upper() in ("YES", "NO"):
            text = "/" + text.lower()

        chat = message.get("chat", {})
        chat_id = str(chat.get("id"))
        user = message.get("from", {})
        user_id = str(user.get("id"))
        username = user.get("username") or user.get("first_name", "Unknown")
        is_admin = self.is_admin(user_id, user)
        message_thread_id = message.get("message_thread_id")

        # Filter: abaikan pesan dari bot lain, KECUALI anonymous admin
        if user.get("is_bot") and user.get("username") != "GroupAnonymousBot":
            return
        # Filter: abaikan forward dari channel (termasuk automatic forward channel post)
        if message.get("is_automatic_forward") or message.get("forward_from_chat"):
            return

        if text.lower() in ("/id", "/chat_id", "/my_id"):
            self.send_message(
                chat_id,
                f"TELEGRAM ID\nChat ID: {chat_id}\nUser ID: {user_id}\nUsername: {username}",
                reply_to_message_id=message.get("message_id"),
                message_thread_id=message_thread_id,
            )
            return

        if not self._chat_allowed(chat_id, is_admin):
            return

        if not text.startswith("/"):
            if self.knowledge_agent:
                try:
                    answer = self._answer_free_text(text, chat_id, user_id, username, is_admin)
                    if answer:
                        self.send_message(
                            chat_id,
                            answer,
                            reply_to_message_id=message.get("message_id"),
                            message_thread_id=message_thread_id,
                        )
                except Exception as e:
                    logger.exception(f"Local knowledge agent error: {e}")
                    self.send_message(
                        chat_id,
                        "⚠️ Bot lokal gagal membaca pertanyaan terbaru. Coba ulangi dengan kalimat lebih jelas.",
                        reply_to_message_id=message.get("message_id"),
                        message_thread_id=message_thread_id,
                    )
            return
        text = normalize_telegram_command(text)
        parts = text.split(" ", 1)
        command = parts[0].lower()
        args_text = parts[1] if len(parts) > 1 else ""
        
        reply_markup = None
        if command in ('/start', '/help', '/menu'):
            reply_markup = self._get_reply_markup(is_admin)

        if command == '/fvg_ob_menu':
            try:
                fvg_resp = self.command_handler(chat_id, user_id, username, '/fvg', "", is_admin)
                ob_resp = self.command_handler(chat_id, user_id, username, '/ob', "", is_admin)
                response = f"{fvg_resp}\n\n{ob_resp}"
            except Exception as e:
                response = "Error retrieving FVG/OB."
            self.send_message(chat_id, response, reply_to_message_id=message.get("message_id"), message_thread_id=message_thread_id)
            return
            
        if command == '/admin_menu':
            if self.admin_ids and not is_admin:
                return
            response = "⚙️ **Admin Menu**\n\nCommand yang tersedia:\n/admin_review\n/rule_review\n/risk_review\n/current_rule\n/trial_status\n/rollback_rule\n/pending\n/bot_health\n/telegram_status\n/test_telegram\n\nUntuk eksekusi, ketik command secara manual."
            self.send_message(chat_id, response, reply_to_message_id=message.get("message_id"), message_thread_id=message_thread_id)
            return
            
        if command == '/debug_menu':
            if self.admin_ids and not is_admin:
                return
            response = "🧪 **Debug Menu**\n\nPilih command debug:\n/debug_fvg\n/debug_ob\n/debug_ote\n/debug_poi"
            self.send_message(chat_id, response, reply_to_message_id=message.get("message_id"), message_thread_id=message_thread_id)
            return

        if command in ('/start', '/menu'):
            response = "🤖 XAUUSD Bot aktif.\nGunakan menu di bawah."
            self.send_message(chat_id, response, reply_to_message_id=message.get("message_id"), reply_markup=reply_markup, message_thread_id=message_thread_id)
            return

        ok, msg = self._cooldown_ok(user_id, command, is_admin)
        if not ok:
            self.send_message(chat_id, msg, reply_to_message_id=message.get("message_id"), message_thread_id=message_thread_id)
            return
        try:
            response = self.command_handler(chat_id, user_id, username, command, args_text, is_admin)
            if response:
                self.send_message(chat_id, response, reply_to_message_id=message.get("message_id"), reply_markup=reply_markup, message_thread_id=message_thread_id)
        except Exception as e:
            logger.exception(f"Error handling command {command}: {e}")
            self.send_message(chat_id, "⚠️ Data belum lengkap.\n\nPrioritas: WAIT\nAction: tunggu setup valid dari rule engine.\n\nSource: RULE ENGINE FALLBACK", reply_to_message_id=message.get("message_id"), reply_markup=reply_markup)

    def send_message(self, chat_id, text, reply_to_message_id=None, reply_markup=None, message_thread_id=None):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": chat_id, "text": self._trim_for_telegram(text)}
        if message_thread_id:
            payload["message_thread_id"] = message_thread_id
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if not resp.ok:
                logger.error(f"Telegram sendMessage failed: {resp.status_code} {resp.text[:300]}")
        except Exception as e:
            logger.error(f"Error sending reply: {e}")
