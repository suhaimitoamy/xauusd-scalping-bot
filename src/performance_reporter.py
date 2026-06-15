import sqlite3
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

load_dotenv(os.path.join(base_dir, '.env'))


def generate_report(send_telegram: bool = False):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'data', 'xauusd_bot.sqlite')
    report_dir = os.path.join(base_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, 'KINERJA_METODE_REPORT.md')

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT signal_class, result, status
        FROM signals
        WHERE status LIKE 'CLOSED%'
        AND result IS NOT NULL
        AND result != ''
    ''')

    rows = cursor.fetchall()
    conn.close()

    methods = {}
    import re
    brain_path = os.path.join(base_dir, 'src', 'market_brain.py')
    if os.path.exists(brain_path):
        with open(brain_path, 'r', encoding='utf-8') as f:
            code = f.read()
            found = set(re.findall(r"'(METHOD_[A-Z0-9_]+)'", code))
            found.add('METHOD_CRT_H4')
            found.add('METHOD_CRT_D1')
            for m in found:
                name = m.replace('METHOD_', '')
                methods[name] = {'win': 0, 'loss': 0, 'total': 0}

    for sig_cls, result, status in rows:
        if not sig_cls:
            continue
        method_name = str(sig_cls).replace('METHOD_', '')
        if method_name not in methods:
            methods[method_name] = {'win': 0, 'loss': 0, 'total': 0}
        methods[method_name]['total'] += 1
        res = str(result).upper()
        if 'WIN' in res:
            methods[method_name]['win'] += 1
        elif 'LOSS' in res:
            methods[method_name]['loss'] += 1

    report_lines = [
        "# 📊 Laporan Kinerja Metode Bot XAUUSD",
        f"**Waktu Update:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "| Nama Metode | Total Trade | WIN | LOSS | Win Rate |",
        "|---|---|---|---|---|"
    ]

    tg_lines = ["📊 UPDATE KINERJA METODE AKTIF\n"]
    sorted_methods = sorted(methods.items(), key=lambda x: (-x[1]['total'], x[0]))

    for method_name, stats in sorted_methods:
        total = stats['total']
        win = stats['win']
        loss = stats['loss']
        win_rate = (win / total) * 100 if total > 0 else 0.0
        report_lines.append(f"| {method_name} | {total} | {win} | {loss} | {win_rate:.1f}% |")
        if total > 0:
            emoji = "🟢" if win_rate >= 60 else "🟠" if win_rate >= 40 else "🔴"
            tg_lines.append(f"{emoji} {method_name}: {win}W/{loss}L | WR {win_rate:.1f}%")

    report_md = "\n".join(report_lines)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_md)

    print(f"Laporan berhasil dibuat di {report_path}")

    env_send = os.environ.get('SEND_METHOD_REPORT_TELEGRAM', '').lower() in {'1', 'true', 'yes', 'on'}
    if not (send_telegram or env_send):
        print("Telegram report skipped. Use SEND_METHOD_REPORT_TELEGRAM=true untuk kirim manual.")
        return

    tg_message = "\n".join(tg_lines)
    if not tg_message.strip() or len(tg_lines) <= 1:
        tg_message = "📊 UPDATE KINERJA METODE\nBelum ada closed trade."
    if len(tg_message) > 3500:
        tg_message = tg_message[:3400] + "\n... lihat reports/KINERJA_METODE_REPORT.md"

    try:
        from src.telegram_notifier import send_telegram_message, telegram_is_configured
        is_simulator = os.environ.get('DRY_RUN', '').lower() == 'true'
        if telegram_is_configured() and not is_simulator:
            send_telegram_message(tg_message)
            print("Laporan dikirim ke Telegram.")
    except Exception as e:
        print(f"Gagal mengirim ke Telegram: {e}")


if __name__ == "__main__":
    generate_report(send_telegram=os.environ.get('SEND_METHOD_REPORT_TELEGRAM', '').lower() in {'1', 'true', 'yes', 'on'})
