def adapt_confidence(base_confidence, structure, risk, session, stats_history):
    # This acts as an adapter that can bump or lower confidence based on
    # history
    final_confidence = base_confidence

    direction = 'BUY' if structure.get('sweep_type') == 'bullish' else 'SELL'

    # Very simple example: if winrate for this direction is very high, bump
    # confidence
    dir_stats = stats_history.get(
        'direction_stats', {}).get(
        direction, {
            'w': 0, 'l': 0})
    w = dir_stats['w']
    l = dir_stats['l']
    if w + l >= 5:
        wr = w / (w + l)
        if wr > 0.6:
            final_confidence += 5
        elif wr < 0.4:
            final_confidence -= 5

    return max(0, min(100, final_confidence))
