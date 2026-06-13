from src.performance_analyzer import PerformanceAnalyzer
from src.ai_advisor import explain_weekly_report


def generate_weekly_report(storage):
    analyzer = PerformanceAnalyzer(storage)
    stats = analyzer.get_weekly_stats()

    tp1_rate = round(
        stats['tp1_hits'] / stats['total'] * 100,
        2) if stats['total'] > 0 else 0
    tp2_rate = round(
        stats['tp2_hits'] / stats['total'] * 100,
        2) if stats['total'] > 0 else 0

    # Simple evaluation for Best/Weak setup for now
    b_win = stats['direction_stats']['BUY']['w']
    b_loss = stats['direction_stats']['BUY']['l']
    s_win = stats['direction_stats']['SELL']['w']
    s_loss = stats['direction_stats']['SELL']['l']

    b_wr = b_win / (b_win + b_loss) if (b_win + b_loss) > 0 else 0
    s_wr = s_win / (s_win + s_loss) if (s_win + s_loss) > 0 else 0

    best_setup = "BUY" if b_wr > s_wr else (
        "SELL" if s_wr > b_wr else "Neutral")
    weak_setup = "SELL" if b_wr > s_wr else (
        "BUY" if s_wr > b_wr else "Neutral")

    ai_notes = explain_weekly_report(stats)

    report = (
        f"📊 XAUUSD WEEKLY REPORT\n"
        f"Source: RULE ENGINE + AI ADVISOR\n\n"
        f"Total Signal: {stats['total']}\n"
        f"Win: {stats['wins']}\n"
        f"Loss: {stats['losses']}\n"
        f"Expired: {stats['expired']}\n"
        f"Winrate: {stats['winrate']}%\n"
        f"TP1 Hit Rate: {tp1_rate}%\n"
        f"TP2 Hit Rate: {tp2_rate}%\n"
        f"Best Session: {stats['best_session']}\n"
        f"Worst Session: {stats['worst_session']}\n"
        f"Best Setup: {best_setup}\n"
        f"Weak Setup: {weak_setup}\n\n"
        f"AI Notes:\n{ai_notes}"
    )
    return report


def generate_rule_review(storage):
    analyzer = PerformanceAnalyzer(storage)
    stats = analyzer.get_weekly_stats()
    from src.ai_advisor import explain_rule_review
    return explain_rule_review(stats)
