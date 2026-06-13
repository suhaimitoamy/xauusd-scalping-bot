import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from src.telegram_interactive import TelegramBotPolling

q1 = "support dimana"
q2 = "resistance dimana"

print("Q1:", TelegramBotPolling._shortcut_command_for_text(q1))
print("Q2:", TelegramBotPolling._shortcut_command_for_text(q2))
