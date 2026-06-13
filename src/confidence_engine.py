"""
Confidence Engine for XAUUSD Scalping Signal Bot.
Calculates a confidence score (0-100) based on multiple factors.
"""


def calculate_confidence(structure, risk, session, data_health):
    """
    Calculates the confidence score for a setup using the 10-Agent Confluence Engine.
    """
    score = 0

    # Base Additions
    if structure.get('sweep_type') is not None:
        score += 20
    if structure.get('reclaim_valid'):
        score += 20

    # Momentum & Bias
    direction = 'bullish' if structure.get(
        'sweep_type') == 'bullish' else 'bearish'
    if structure.get('m5_momentum') == direction:
        score += 10
    if structure.get('m15_bias') == direction:
        score += 15
    if structure.get('h1_bias') == direction:
        score += 10
    elif structure.get('h1_bias') == 'neutral':
        score += 5

    # Confluence Boosters
    if structure.get('fvg_alignment'):
        score += 10
    if structure.get('ob_alignment'):
        score += 10
    if structure.get('sd_alignment'):
        score += 10
    if structure.get('ote_alignment'):
        score += 10
    if structure.get('liquidity_alignment'):
        score += 10

    # Risk
    if risk is not None and risk.get('rr_ratio', 0) >= 1.5:
        score += 10

    # Session & Data Health (No penalty for Asia session anymore)
    if session.get('is_valid') and session.get('session_name') != 'Outside':
        score += 5
    if data_health.get('is_healthy', True):
        score += 5

    # Minor counter-trend penalty (valid counter-HTF scalp if aligns with
    # M15/M5)
    h4_bias = structure.get('h4_bias', 'N/A')
    if (direction == 'bullish' and h4_bias == 'bearish') or (
            direction == 'bearish' and h4_bias == 'bullish'):
        score -= 5  # Reduced penalty for scalping

    # Penalties
    if structure.get('middle_of_range'):
        score -= 15
    if structure.get('choppy') or structure.get('trend') == 'CHOPPY':
        score -= 40
    if structure.get('trend') == 'EXPANSION':
        score -= 15  # Wait for pullback

    if risk is not None:
        if risk.get('rr_ratio', 0) < 2.0:  # Enforced strict 1:2 RR
            score -= 50

    if not (structure.get('fvg_alignment') or structure.get('ob_alignment') or structure.get('sd_alignment') or structure.get('ote_alignment') or structure.get('liquidity_alignment')):
        score -= 30

    if structure.get('h1_bias') not in (direction, 'neutral'):
        score -= 10

    if not data_health.get('is_healthy', True):
        score -= 50

    return max(0, min(100, score))
