import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from src.telegram_interactive import TelegramBotPolling

q1 = "fvg terbaru di harga berapa"
q2 = "ob terbaru di harga berapa"

print("Q1:", TelegramBotPolling._shortcut_command_for_text(q1))
print("Q2:", TelegramBotPolling._shortcut_command_for_text(q2))
