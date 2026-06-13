import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from src.telegram_interactive import TelegramBotPolling

router = TelegramBotPolling._shortcut_command_for_text

queries = [
    "fvg terbaru dimana bos?",
    "tolong cek area order block terdekat dong",
    "ada liquidity di mana aja sekarang?",
    "masuk buy atau sell nih bagusnya?",
    "apa itu fvg?",
    "jelaskan order block"
]

for q in queries:
    cmd = router(q)
    print(f"User: '{q}' -> Bot Command: {cmd}")
