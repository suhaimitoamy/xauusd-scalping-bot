"""
Mapping Assistant runner.

Can be used by scripts/send_mapping_summary.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.session_context import get_session_context, format_session_context
from src.htf_bias_engine import analyze_htf_bias, format_htf_bias
from src.range_map import build_range_map, format_range_map
from src.liquidity_map import build_liquidity_map, format_liquidity_map
from src.order_block_engine import detect_order_blocks, save_order_blocks, nearest_order_block, format_ob_alert
from src.fvg_mapping import nearest_fvg, format_fvg_map
from src.market_narrative import build_market_narrative

try:
    from src.market_structure import analyze_structure
except Exception:
    analyze_structure = None


class MappingAssistant:
    def __init__(self, storage, symbol="XAU/USD"):
        self.storage = storage
        self.symbol = symbol

    def _candles(self, timeframe, limit):
        try:
            return self.storage.get_recent_candles(self.symbol, timeframe, limit)
        except Exception:
            return []

    def build_snapshot(self):
        m5 = self._candles("M5", 180)
        m15 = self._candles("M15", 180)
        h1 = self._candles("H1", 120)
        h4 = self._candles("H4", 120)
        d1 = self._candles("D1", 120)

        base = m5 or m15 or h1
        current_price = float(base[-1]["close"]) if base else 0.0

        session_ctx = get_session_context(datetime.now(timezone.utc))
        htf_ctx = analyze_htf_bias(h1, h4, d1)
        range_ctx = build_range_map(h1 or m15 or m5, current_price=current_price)
        liquidity_ctx = build_liquidity_map(m15, h1, d1, current_price=current_price)

        structure_ctx = {}
        if analyze_structure and m5:
            structure_ctx = analyze_structure(m5, m15, h1)

        detected_obs = detect_order_blocks(m15 or h1 or m5, "M15" if m15 else "H1", self.symbol)
        if detected_obs:
            save_order_blocks(self.storage, detected_obs)

        try:
            stored_obs = self.storage.fetchall(
                "SELECT * FROM active_order_blocks WHERE symbol=? AND status IN ('VALID','ACTIVE') ORDER BY id DESC LIMIT 50",
                (self.symbol,),
            )
        except Exception:
            stored_obs = detected_obs

        near_ob = nearest_order_block(stored_obs or detected_obs, current_price)
        near_fvg = nearest_fvg(self.storage, self.symbol, current_price)

        narrative = build_market_narrative(
            current_price=current_price,
            htf_bias=htf_ctx,
            range_map=range_ctx,
            liquidity_map=liquidity_ctx,
            session_context=session_ctx,
            nearest_ob=near_ob,
            nearest_fvg=near_fvg,
            structure=structure_ctx,
        )

        blocks = [
            narrative,
            format_session_context(session_ctx),
            format_htf_bias(htf_ctx),
            format_range_map(range_ctx),
            format_liquidity_map(liquidity_ctx),
            format_fvg_map(near_fvg, current_price),
        ]

        if near_ob:
            blocks.append(format_ob_alert(near_ob, current_price))
        else:
            blocks.append("🧱 ORDER BLOCK MAP\nTidak ada OB aktif terdekat.")

        return {
            "symbol": self.symbol,
            "current_price": current_price,
            "session": session_ctx,
            "htf": htf_ctx,
            "range": range_ctx,
            "liquidity": liquidity_ctx,
            "structure": structure_ctx,
            "nearest_ob": near_ob,
            "nearest_fvg": near_fvg,
            "message": "\n\n".join(blocks),
        }

    def send_snapshot(self):
        snapshot = self.build_snapshot()
        try:
            from src.telegram_notifier import send_telegram_message, telegram_is_configured
            if telegram_is_configured():
                send_telegram_message(snapshot["message"])
                return True, snapshot
        except Exception:
            pass
        return False, snapshot
