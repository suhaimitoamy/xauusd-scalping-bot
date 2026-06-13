from src.rule_manager import RuleManager


def check_risk_review(storage, m5_candles, config):
    from src.atr_engine import calculate_atr
    atr = calculate_atr(m5_candles)

    if atr > 4.5:
        # High volatility
        rule_manager = RuleManager(storage)
        pending = rule_manager.check_pending_actions()
        if pending:
            return (
                "⚠️ RISK REVIEW\n"
                f"ATR M5 sekarang tinggi ({round(atr, 2)}).\n"
                "Sudah ada pending action yang menunggu YES / NO.\n"
                f"Pending: {pending.get('message')}"
            )
        proposal = {"min_sl_points": 6}
        msg = (
            "⚠️ RISK REVIEW\n"
            f"ATR M5 sekarang tinggi ({round(atr, 2)}).\n"
            "SL 4 poin rawan kena noise.\n"
            "Rekomendasi: naikkan min_sl_points 4 → 6 dalam trial mode?\n"
            "Ketik YES / NO"
        )
        rule_manager.create_pending_action("RISK_UPDATE", msg, proposal)
        return msg
    return "RISK REVIEW\nATR normal. Tidak ada perubahan rule risk."
