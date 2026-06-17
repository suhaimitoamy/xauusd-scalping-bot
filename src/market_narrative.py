"""
Build final mapping narrative.
"""

from __future__ import annotations


def _f(x):
    if x is None:
        return "N/A"
    try:
        return f"{float(x):.2f}"
    except Exception:
        return str(x)


def build_market_narrative(
    current_price,
    htf_bias=None,
    range_map=None,
    liquidity_map=None,
    session_context=None,
    nearest_ob=None,
    nearest_fvg=None,
    structure=None,
):
    htf_bias = htf_bias or {}
    range_map = range_map or {}
    liquidity_map = liquidity_map or {}
    session_context = session_context or {}
    structure = structure or {}

    lines = [
        "📊 MARKET NARRATIVE",
        "",
        f"Current Price: {_f(current_price)}",
        f"Active Session: {session_context.get('active_session', 'N/A')}",
        f"NY Timezone: {session_context.get('ny_tz', 'N/A')}",
        f"HTF Bias: {htf_bias.get('final_bias', 'N/A')}",
        f"Range Position: {range_map.get('position', 'N/A')}",
        f"Liquidity Terdekat: BSL {_f(liquidity_map.get('nearest_bsl'))} | SSL {_f(liquidity_map.get('nearest_ssl'))}",
        f"Structure Phase: {structure.get('trend', 'N/A')}",
        f"Invalidasi Structure: {structure.get('invalidation_label', 'N/A')} di {_f(structure.get('invalidation_level'))}",
    ]

    if nearest_fvg:
        lines.append(
            f"FVG Terdekat: {nearest_fvg.get('direction')} {nearest_fvg.get('timeframe')} "
            f"{_f(nearest_fvg.get('low'))} - {_f(nearest_fvg.get('high'))}"
        )
    else:
        lines.append("FVG Terdekat: N/A")

    if nearest_ob:
        lines.append(
            f"OB Terdekat: {nearest_ob.get('type', nearest_ob.get('direction'))} "
            f"{_f(nearest_ob.get('low'))} - {_f(nearest_ob.get('high'))}"
        )
    else:
        lines.append("OB Terdekat: N/A")

    conclusion = "Kesimpulan: tunggu struktur lebih jelas."
    final_bias = htf_bias.get("final_bias")
    position = range_map.get("position")
    phase = structure.get("trend")

    if final_bias == "bullish" and position in ("discount", "equilibrium"):
        conclusion = "Kesimpulan: bullish masih lebih sehat selama invalidasi Higher Low belum jebol."
    elif final_bias == "bearish" and position in ("premium", "equilibrium"):
        conclusion = "Kesimpulan: bearish masih lebih sehat selama invalidasi Lower High belum jebol."
    elif phase == "FAKE_BREAK":
        conclusion = "Kesimpulan: hati-hati fake break, jangan kejar harga sebelum retest/reclaim jelas."
    elif phase == "TREND_INVALIDATED":
        conclusion = "Kesimpulan: struktur sebelumnya sudah invalid, tunggu struktur baru terbentuk."

    lines.extend(["", conclusion])
    return "\n".join(lines)
