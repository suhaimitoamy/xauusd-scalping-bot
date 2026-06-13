import os
import time
from typing import Optional, List

import requests
from src.formatter import setup_logger

logger = setup_logger("TelegramNotifier")


def _get_token() -> str:
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def _default_chat_id() -> str:
    return (
        os.getenv("TELEGRAM_DISCUSSION_CHAT_ID")
        or os.getenv("TELEGRAM_CHAT_ID")
        or ""
    ).strip()


def _looks_like_chat_id(value) -> bool:
    value = str(value or "").strip()
    if not value:
        return False
    if value.startswith("-"):
        value = value[1:]
    return value.isdigit()


def _split_message(text: str, limit: int = 3900) -> List[str]:
    text = str(text or "").strip()
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < 500:
            cut = remaining.rfind(" ", 0, limit)
        if cut < 500:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def telegram_is_configured(require_chat: bool = True) -> bool:
    token = _get_token()
    if not token:
        return False
    if require_chat and not _default_chat_id():
        return False
    return True


def send_telegram_message(text, chat_id: Optional[str] = None, parse_mode: Optional[str] = None,
                          disable_web_page_preview: bool = True, message_thread_id: Optional[int] = None) -> bool:
    """Send Telegram message.

    Supports both:
    - send_telegram_message("message")
    - send_telegram_message(chat_id, "message")  # old accidental style
    """
    token = _get_token()
    if not token:
        return False
        
    import os
    if os.environ.get('DRY_RUN') == 'true':
        return True

    # Backward compatibility for older calls: send_telegram_message(chat_id, msg)
    if chat_id is not None and _looks_like_chat_id(text):
        text, chat_id = chat_id, str(text)

    chat_id = str(chat_id or _default_chat_id()).strip()
    if not chat_id:
        logger.warning("Telegram delivery skipped: missing TELEGRAM_CHAT_ID / TELEGRAM_DISCUSSION_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    parse_mode = parse_mode if parse_mode is not None else (os.getenv("TELEGRAM_PARSE_MODE") or "").strip()

    ok = True
    for chunk in _split_message(str(text or "")):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if message_thread_id:
            payload["message_thread_id"] = message_thread_id

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=15)
                if response.status_code == 429:
                    retry_after = 1
                    try:
                        retry_after = int(response.json().get("parameters", {}).get("retry_after", 1))
                    except Exception:
                        pass
                    wait_time = min(retry_after + attempt * 2, 30)
                    logger.warning(f"Telegram rate limited (429). Waiting {wait_time}s before retry {attempt+1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                response.raise_for_status()
                time.sleep(0.35)  # baseline rate limiter antar chunk
                break
            except requests.exceptions.HTTPError as e:
                if "429" not in str(e):
                    logger.warning(f"Telegram delivery failed: {e}")
                    ok = False
                    break
            except Exception as e:
                logger.warning(f"Telegram delivery failed: {e}")
                ok = False
                break
        else:
            logger.warning("Telegram delivery failed after max retries (rate limited).")
            ok = False
    return ok


def get_telegram_status() -> str:
    token = _get_token()
    main_chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    discussion_chat = (os.getenv("TELEGRAM_DISCUSSION_CHAT_ID") or "").strip()
    admin_ids = (os.getenv("TELEGRAM_ADMIN_IDS") or "").strip()
    parse_mode = (os.getenv("TELEGRAM_PARSE_MODE") or "").strip() or "none"

    lines = [
        "TELEGRAM STATUS",
        f"Token: {'OK' if token else 'MISSING'}",
        f"Main Chat ID: {main_chat or 'MISSING'}",
        f"Discussion Chat ID: {discussion_chat or '-'}",
        f"Default Send Target: {_default_chat_id() or 'MISSING'}",
        f"Admin IDs: {admin_ids or 'ALL USERS'}",
        f"Parse Mode: {parse_mode}",
    ]
    return "\n".join(lines)


def get_bot_username() -> str:
    token = _get_token()
    if not token:
        return ""
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            return ""
        return data.get("result", {}).get("username", "") or ""
    except Exception as e:
        logger.warning(f"Telegram getMe failed: {e}")
        return ""


def test_telegram():
    if not telegram_is_configured():
        logger.warning("Telegram is not configured. Missing token or chat ID.")
        return False
    username = get_bot_username()
    bot_label = f"@{username}" if username else "Telegram Bot"
    return send_telegram_message(
        f"✅ {bot_label} connected\nXAUUSD Scalping Bot Telegram updated."
    )
