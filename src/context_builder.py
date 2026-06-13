import json
from src.performance_analyzer import PerformanceAnalyzer
from src.poi_engine import build_poi_map


def build_bot_context(storage, bot_state, symbol="XAU/USD"):
    analyzer = PerformanceAnalyzer(storage)
    stats = analyzer.get_weekly_stats()

    # Active rules
    active_rule = storage.get_active_rule_version()
    rule_version = active_rule['version_name'] if active_rule else "None"

    # Total Trades (all time)
    conn = storage.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT COUNT(*) FROM signals WHERE direction IN ("BUY", "SELL")')
    total_trades_count = cursor.fetchone()[0]
    conn.close()

    # Active signals
    open_signals = storage.get_open_signals()
    active_signals_str = ""
    for s in open_signals:
        active_signals_str += f"- {
            s['direction']} at {
            s['entry_low']}-{
            s['entry_high']} (SL: {
                s['sl']}, TP1: {
                    s['tp1']})\n"
    if not active_signals_str:
        active_signals_str = "None\n"

    # Pending action
    pending = storage.get_pending_action()
    pending_str = f"Action: {
        pending['action_type']} | Status: {
        pending['status']}" if pending else "None"

    # POI & Bias
    poi_data = build_poi_map(storage, symbol)
    h4_bias = poi_data['h4'].get('bias', 'N/A')
    h1_context = poi_data['h1'].get('main_poi', 'N/A')

    # Last 10 structure events
    conn = storage.get_connection()
    conn.row_factory = __import__('sqlite3').Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT event_type, direction, level, created_at FROM structure_events
        ORDER BY id DESC LIMIT 5
    ''')
    recent_events = cursor.fetchall()
    conn.close()

    events_str = ""
    for ev in recent_events:
        events_str += f"- {
            ev['event_type']} {
            ev['direction']} at {
            ev['level']}\n"

    current_price = bot_state.get('last_price', 'Unknown')
    retest_mode = bot_state.get('retest_mode', 'None')

    context_str = (
        f"BOT CONTEXT SUMMARY\n"
        f"===================\n"
        f"Symbol: {symbol}\n"
        f"Current Price: {current_price}\n"
        f"H4 Bias: {h4_bias}\n"
        f"H1 Context: {h1_context}\n"
        f"Retest Mode: {retest_mode}\n\n"
        f"ACTIVE SIGNALS:\n{active_signals_str}\n"
        f"RECENT EVENTS:\n{events_str}\n"
        f"PERFORMANCE:\n"
        f"- Total Trades: {total_trades_count}\n"
        f"- Weekly Wins: {stats.get('wins', 0)}\n"
        f"- Weekly Losses: {stats.get('losses', 0)}\n"
        f"- Weekly Winrate: {stats.get('winrate', 0)}%\n"
        f"- Best Session: {stats.get('best_session', 'N/A')}\n\n"
        f"SYSTEM STATE:\n"
        f"- Active Rule Version: {rule_version}\n"
        f"- Pending Action: {pending_str}\n"
    )
    return context_str


def build_live_market_context(storage, symbol="XAUUSD", bot_state=None):
    """Single live context source for CLI and Telegram."""
    from src.bot_views import build_context
    ctx = build_context(storage, symbol, bot_state)
    s = ctx.get('structure', {})
    return {
        "symbol": symbol,
        "current_price": ctx.get('price'),
        "timestamp_wib": ctx.get('time'),
        "m15_bias": s.get('m15_bias', 'N/A'),
        "m5_structure": s.get('trend', 'N/A'),
        "m5_momentum": s.get('m5_momentum', 'N/A'),
        "h1_bias": s.get('h1_bias', 'N/A'),
        "h4_bias": s.get('h4_bias', 'N/A'),
        "phase": s.get('trend', 'N/A'),
        "session": ctx.get('session', 'N/A'),
        "sweep_type": s.get('sweep_type'),
        "reclaim_valid": s.get('reclaim_valid', False),
        "retest_mode": s.get('retest_mode', 'NONE'),
        "active_fvgs": ctx.get('fvgs', []),
        "active_obs": ctx.get('obs', []),
        "active_breakers": ctx.get('breakers', []),
        "supply_demand_zones": ctx.get('sd', []),
        "liquidity_pools": ctx.get('liquidity', []),
        "active_otes": ctx.get('ote', []),
    }
