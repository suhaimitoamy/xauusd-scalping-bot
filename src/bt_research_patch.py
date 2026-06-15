"""Backtest-only research logic for NON-LIVE_MAIN methods.

Aktif hanya saat BT_RESEARCH=true.
Live trading tidak berubah.

Mode ini sengaja agresif untuk mencari kandidat baru:
- LIVE_MAIN dilewati.
- Cooldown dimatikan.
- Active-signal lock dimatikan.
- Metode non-main diberi logic riset berdasarkan keluarga namanya.
- Jika tidak ada setup alami, engine membuat trigger eksplorasi terjadwal
  agar metode yang jarang trigger tetap punya data untuk disaring manual.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

Decision = Tuple[str, str, str, float]


def _on(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def active() -> bool:
    return _on(os.environ.get("BT_RESEARCH", ""))


def _equiv(method: str) -> set[str]:
    try:
        from src.method_registry import equivalent_method_names
        return equivalent_method_names(method)
    except Exception:
        name = str(method or "").strip().upper()
        return {name} if name else set()


def _main_methods() -> set[str]:
    try:
        from src.method_registry import get_main_methods, load_config
        out: set[str] = set()
        for method in get_main_methods(load_config()):
            out.update(_equiv(method))
        return out
    except Exception:
        return set()


def _is_main(method: str) -> bool:
    return bool(_equiv(method) & _main_methods())


def _num(ctx: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(ctx.get(key) if ctx.get(key) is not None else default)
    except Exception:
        return default


def _ctx_datetime(ctx: Dict[str, Any]) -> Optional[datetime]:
    raw = ctx.get("last_time") or ctx.get("timestamp") or ctx.get("open_time")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _session_hour(ctx: Dict[str, Any]) -> int:
    dt = _ctx_datetime(ctx)
    return int(dt.hour) if dt else 0


def _research_slot(ctx: Dict[str, Any]) -> Tuple[int, bool]:
    dt = _ctx_datetime(ctx)
    if dt is None:
        return 0, True
    per_day = max(1, int(os.environ.get("BT_RESEARCH_PER_DAY", "8") or 8))
    spacing_minutes = max(5, int(1440 / per_day))
    minute_of_day = dt.hour * 60 + dt.minute
    slot = (dt.timetuple().tm_yday * per_day) + int(minute_of_day / spacing_minutes)
    return slot, (minute_of_day % spacing_minutes == 0)


def _direction_from_method(method: str) -> str:
    m = str(method or "").upper()
    if m.endswith("_BUY") or "_BUY_" in m or m.endswith("BUY"):
        return "BUY"
    if m.endswith("_SELL") or "_SELL_" in m or m.endswith("SELL"):
        return "SELL"
    return ""


def _side_from_context(ctx: Dict[str, Any]) -> str:
    close = _num(ctx, "last_close")
    open_ = _num(ctx, "last_open")
    prev_high = _num(ctx, "prev_high")
    prev_low = _num(ctx, "prev_low")
    momentum = str(ctx.get("momentum") or "").lower()
    m15 = str(ctx.get("m15_bias") or "").lower()
    if prev_high and close > prev_high:
        return "BUY"
    if prev_low and close < prev_low:
        return "SELL"
    if momentum == "bullish" or m15 == "bullish":
        return "BUY"
    if momentum == "bearish" or m15 == "bearish":
        return "SELL"
    return "BUY" if close >= open_ else "SELL"


def _body_stats(ctx: Dict[str, Any]) -> Dict[str, float]:
    open_ = _num(ctx, "last_open")
    close = _num(ctx, "last_close")
    high = _num(ctx, "last_high")
    low = _num(ctx, "last_low")
    rng = max(high - low, 0.01)
    body = abs(close - open_)
    top = max(open_, close)
    bottom = min(open_, close)
    return {
        "open": open_,
        "close": close,
        "high": high,
        "low": low,
        "range": rng,
        "body": body,
        "ratio": body / rng,
        "upper_wick": max(high - top, 0.0),
        "lower_wick": max(bottom - low, 0.0),
    }


def _intraday(ctx: Dict[str, Any]) -> Dict[str, Any]:
    data = ctx.get("intraday_context")
    return data if isinstance(data, dict) else {}


def _all_non_main_methods() -> List[str]:
    main = _main_methods()
    methods: List[str] = []
    try:
        with open("config/method_registry.json", "r", encoding="utf-8") as f:
            payload = json.load(f)
        registry = payload.get("methods", payload) if isinstance(payload, dict) else {}
        for name, data in sorted(registry.items()):
            method = str(name or "").strip().upper()
            if not method.startswith(("METHOD_", "AI_METHOD_", "ANTIGRAVITY_", "RR2_")):
                continue
            if _equiv(method) & main:
                continue
            if str((data or {}).get("status") or "").upper() == "LIVE_MAIN":
                continue
            if method not in methods:
                methods.append(method)
    except Exception:
        pass

    fallback = [
        "METHOD_BREAK_AND_RETEST_BUY", "METHOD_BREAK_AND_RETEST_SELL",
        "METHOD_BOS_RETEST_OB_BUY", "METHOD_BOS_RETEST_OB_SELL",
        "METHOD_ORDER_BLOCK_TAP_BUY", "METHOD_ORDER_BLOCK_TAP_SELL",
        "METHOD_NY_OPEN_BREAKOUT_BUY", "METHOD_NY_OPEN_BREAKOUT_SELL",
        "METHOD_LONDON_OPEN_BREAKOUT_BUY", "METHOD_LONDON_OPEN_BREAKOUT_SELL",
        "METHOD_DRAW_ON_LIQUIDITY_BUY", "METHOD_DRAW_ON_LIQUIDITY_SELL",
        "METHOD_INDUCEMENT_TRAP_BUY", "METHOD_INDUCEMENT_TRAP_SELL",
        "METHOD_ASIA_RANGE_SWEEP_BUY", "METHOD_ASIA_RANGE_SWEEP_SELL",
        "METHOD_MOMENTUM_IGNITION_BUY", "METHOD_MOMENTUM_IGNITION_SELL",
        "METHOD_POI_ACCUMULATION_BUY", "METHOD_POI_ACCUMULATION_SELL",
        "METHOD_POI_REBOUND_OB_BUY", "METHOD_POI_REBOUND_OB_SELL",
        "METHOD_CHOPPY_SCALP_BUY", "METHOD_CHOPPY_SCALP_SELL",
        "METHOD_MICRO_SWEEP_SCALP_BUY", "METHOD_MICRO_SWEEP_SCALP_SELL",
        "METHOD_NEWS_SPIKE_FADE_BUY", "METHOD_NEWS_SPIKE_FADE_SELL",
    ]
    for method in fallback:
        if not _is_main(method) and method not in methods:
            methods.append(method)
    return methods


def _method_rule(method: str, ctx: Dict[str, Any]) -> Optional[Decision]:
    method = str(method or "").upper()
    direction = _direction_from_method(method) or _side_from_context(ctx)
    st = _body_stats(ctx)
    hour = _session_hour(ctx)
    close = st["close"]
    open_ = st["open"]
    atr = max(_num(ctx, "atr", 1.5), 0.01)
    prev_high = _num(ctx, "prev_high")
    prev_low = _num(ctx, "prev_low")
    m15 = str(ctx.get("m15_bias") or "").lower()
    h1 = str(ctx.get("h1_bias") or "").lower()
    momentum = str(ctx.get("momentum") or "").lower()
    intraday = _intraday(ctx)
    pos = str(intraday.get("position") or "").lower()
    bias = str(intraday.get("bias") or "").lower()
    choppy = bool(ctx.get("choppy"))
    break_bull = bool(ctx.get("break_bull")) or (prev_high and close > prev_high)
    break_bear = bool(ctx.get("break_bear")) or (prev_low and close < prev_low)
    sentuh_low = bool(ctx.get("sentuh_low")) or (prev_low and st["low"] <= prev_low)
    sentuh_high = bool(ctx.get("sentuh_high")) or (prev_high and st["high"] >= prev_high)
    bullish_candle = close > open_
    bearish_candle = close < open_
    strong_body = st["ratio"] >= 0.35
    small_body = st["ratio"] <= 0.32
    near_high = close >= st["high"] - st["range"] * 0.35
    near_low = close <= st["low"] + st["range"] * 0.35

    def ok_buy() -> bool:
        return direction == "BUY"

    def ok_sell() -> bool:
        return direction == "SELL"

    # Session methods: sengaja lebih aktif, tapi tetap berbasis jam London/NY/Asia.
    if "SESSION_OPEN_BREAKOUT" in method:
        if ok_buy() and hour in {7, 8, 9, 13, 14} and bullish_candle and (break_bull or momentum != "bearish"):
            return direction, "SESSION OPEN BUY: open-session push + bullish close", method, 72.0
        if ok_sell() and hour in {7, 8, 9, 13, 14} and bearish_candle and (break_bear or momentum != "bullish"):
            return direction, "SESSION OPEN SELL: open-session push + bearish close", method, 72.0

    if "LONDON_OPEN_BREAKOUT" in method:
        if hour in {7, 8, 9} and ((ok_buy() and bullish_candle) or (ok_sell() and bearish_candle)):
            return direction, "LONDON OPEN: candle searah di jam London", method, 69.0

    if "NY_OPEN_BREAKOUT" in method:
        if hour in {13, 14, 15} and ((ok_buy() and bullish_candle) or (ok_sell() and bearish_candle)):
            return direction, "NY OPEN: candle searah di jam NY", method, 69.0

    # Asia methods.
    if "ASIA" in method or "ASIAN" in method:
        if ok_buy() and hour in {0, 1, 2, 3, 4, 5} and sentuh_low and bullish_candle:
            return direction, "ASIA BUY: low sweep/reclaim during Asia", method, 66.0
        if ok_sell() and hour in {0, 1, 2, 3, 4, 5} and sentuh_high and bearish_candle:
            return direction, "ASIA SELL: high sweep/reclaim during Asia", method, 66.0

    # BOS / continuation / breakout families.
    if "BOS" in method or "BREAKOUT" in method or "CONTINUATION" in method:
        if ok_buy() and break_bull and bullish_candle and strong_body:
            return direction, "BOS/BREAKOUT BUY: break high + strong close", method, 70.0
        if ok_sell() and break_bear and bearish_candle and strong_body:
            return direction, "BOS/BREAKOUT SELL: break low + strong close", method, 70.0

    # Break and retest / OB / breaker.
    if "BREAK_AND_RETEST" in method or "RETEST" in method or "ORDER_BLOCK" in method or "BREAKER" in method:
        if ok_buy() and (break_bull or m15 == "bullish") and bullish_candle and close >= (prev_high - atr * 0.60 if prev_high else close):
            return direction, "RETEST/OB BUY: bullish reclaim near broken level", method, 68.0
        if ok_sell() and (break_bear or m15 == "bearish") and bearish_candle and close <= (prev_low + atr * 0.60 if prev_low else close):
            return direction, "RETEST/OB SELL: bearish reclaim near broken level", method, 68.0

    # POI / accumulation / rebound.
    if "POI" in method or "ACCUMULATION" in method or "REBOUND" in method:
        if ok_buy() and pos in {"discount", "equilibrium", "unknown", ""} and (sentuh_low or bullish_candle) and momentum != "bearish":
            return direction, "POI BUY: discount/equilibrium reaction + bullish reclaim", method, 67.0
        if ok_sell() and pos in {"premium", "equilibrium", "unknown", ""} and (sentuh_high or bearish_candle) and momentum != "bullish":
            return direction, "POI SELL: premium/equilibrium reaction + bearish reject", method, 67.0

    # Sweep / turtle / liquidity.
    if "SWEEP" in method or "TURTLE" in method or "LIQUIDITY" in method or "DRAW_ON_LIQUIDITY" in method:
        if ok_buy() and sentuh_low and bullish_candle and st["lower_wick"] >= st["body"] * 0.35:
            return direction, "LIQUIDITY BUY: low sweep + close back up", method, 69.0
        if ok_sell() and sentuh_high and bearish_candle and st["upper_wick"] >= st["body"] * 0.35:
            return direction, "LIQUIDITY SELL: high sweep + close back down", method, 69.0

    # Inducement trap / CHoCH reversal.
    if "INDUCEMENT" in method or "TRAP" in method or "CHOCH" in method or "REVERSAL" in method:
        if ok_buy() and sentuh_low and bullish_candle and near_high:
            return direction, "TRAP BUY: sell-side sweep then strong bullish close", method, 66.0
        if ok_sell() and sentuh_high and bearish_candle and near_low:
            return direction, "TRAP SELL: buy-side sweep then strong bearish close", method, 66.0

    # Pullback / trend continuation.
    if "PULLBACK" in method or "FOLLOW_THE_TREND" in method:
        if ok_buy() and m15 == "bullish" and h1 != "bearish" and bullish_candle and not break_bear:
            return direction, "PULLBACK BUY: M15 bullish + candle reclaim", method, 65.0
        if ok_sell() and m15 == "bearish" and h1 != "bullish" and bearish_candle and not break_bull:
            return direction, "PULLBACK SELL: M15 bearish + candle reject", method, 65.0

    # Momentum / marubozu / ignition.
    if "MOMENTUM" in method or "MARUBOZU" in method:
        if ok_buy() and bullish_candle and strong_body and near_high and momentum != "bearish":
            return direction, "MOMENTUM BUY: strong body close near high", method, 66.0
        if ok_sell() and bearish_candle and strong_body and near_low and momentum != "bullish":
            return direction, "MOMENTUM SELL: strong body close near low", method, 66.0

    # Choppy scalp deliberately trades ranges, not trend.
    if "CHOPPY" in method:
        if choppy or bias == "sideways" or small_body:
            if ok_buy() and (sentuh_low or close <= open_ + atr * 0.2):
                return direction, "CHOPPY BUY: range scalp from lower side", method, 60.0
            if ok_sell() and (sentuh_high or close >= open_ - atr * 0.2):
                return direction, "CHOPPY SELL: range scalp from upper side", method, 60.0

    # News spike fade: treat abnormally large candle as fade candidate.
    if "NEWS_SPIKE" in method or "SPIKE_FADE" in method:
        big = st["range"] >= max(atr * 1.6, 2.0)
        if big and ok_buy() and bearish_candle and st["lower_wick"] > st["body"] * 0.25:
            return direction, "NEWS FADE BUY: large bearish spike with lower rejection", method, 58.0
        if big and ok_sell() and bullish_candle and st["upper_wick"] > st["body"] * 0.25:
            return direction, "NEWS FADE SELL: large bullish spike with upper rejection", method, 58.0

    # AI/Antigravity candidates: generic exploration but still use candle side.
    if method.startswith(("AI_METHOD_", "ANTIGRAVITY_")):
        if ok_buy() and bullish_candle and momentum != "bearish":
            return direction, "AI/ANTIGRAVITY BUY: generic bullish candidate", method, 55.0
        if ok_sell() and bearish_candle and momentum != "bullish":
            return direction, "AI/ANTIGRAVITY SELL: generic bearish candidate", method, 55.0

    return None


def _rule_candidates(ctx: Dict[str, Any]) -> List[Decision]:
    slot, should_fire = _research_slot(ctx)
    if not should_fire:
        return []
    side = _side_from_context(ctx)
    methods = _all_non_main_methods()
    preferred = [m for m in methods if (_direction_from_method(m) or side) == side]
    others = [m for m in methods if m not in preferred]
    ordered = preferred + others
    candidates: List[Decision] = []
    for method in ordered:
        hit = _method_rule(method, ctx)
        if hit:
            candidates.append(hit)
    if candidates:
        candidates.sort(key=lambda x: (x[0] != side, -x[3], x[2]))
        return candidates
    return []


def _fallback_decision(ctx: Dict[str, Any]) -> Optional[Decision]:
    slot, should_fire = _research_slot(ctx)
    if not should_fire:
        return None
    side = _side_from_context(ctx)
    methods = [m for m in _all_non_main_methods() if (_direction_from_method(m) or side) == side]
    if not methods:
        methods = _all_non_main_methods()
    if not methods:
        return None
    method = methods[slot % len(methods)]
    direction = _direction_from_method(method) or side
    return (
        direction,
        "BT_RESEARCH fallback: forced non-main sample; WR ignored; use only for candidate discovery",
        method,
        52.0,
    )


def _research_decision(ctx: Dict[str, Any]) -> Optional[Decision]:
    if not active():
        return None
    slot, should_fire = _research_slot(ctx)
    if not should_fire:
        return None
    candidates = _rule_candidates(ctx)
    if candidates:
        return candidates[slot % len(candidates)]
    return _fallback_decision(ctx)


def _research_signal(symbol: str, direction: str, price: float, ctx: Dict[str, Any], pattern_key: str, reason: str, confidence: float) -> Dict[str, Any]:
    entry = float(price)
    sl_dist = float(os.environ.get("BT_RESEARCH_SL", "2.0") or 2.0)
    tp1_dist = float(os.environ.get("BT_RESEARCH_TP1", "1.0") or 1.0)
    tp2_dist = float(os.environ.get("BT_RESEARCH_TP2", "2.0") or 2.0)
    if direction == "BUY":
        sl = entry - sl_dist
        tp1 = entry + tp1_dist
        tp2 = entry + tp2_dist
    else:
        sl = entry + sl_dist
        tp1 = entry - tp1_dist
        tp2 = entry - tp2_dist
    return {
        "symbol": symbol,
        "direction": direction,
        "entry_low": round(entry - 0.15, 3),
        "entry_high": round(entry + 0.15, 3),
        "sl": round(sl, 3),
        "tp1": round(tp1, 3),
        "tp2": round(tp2, 3),
        "tp3": None,
        "invalid_level": round(sl, 3),
        "confidence": round(float(confidence or 52.0), 1),
        "reason": reason,
        "status": "ACTIVE",
        "entry_type": "MARKET",
        "pending_price": None,
        "pending_expire_time": None,
        "signal_timeframe": "M5",
        "signal_class": "BT_RESEARCH_NON_MAIN",
        "current_price": entry,
        "pattern_key": pattern_key,
        "source": "BT_RESEARCH",
        "brain_context": {
            "prev_high": ctx.get("prev_high"),
            "prev_low": ctx.get("prev_low"),
            "atr": ctx.get("atr"),
            "momentum": ctx.get("momentum"),
            "choppy": ctx.get("choppy"),
            "m15_bias": ctx.get("m15_bias"),
            "h1_bias": ctx.get("h1_bias"),
            "intraday_context": ctx.get("intraday_context"),
            "bt_research": True,
        },
    }


def apply_bt_research_patch() -> None:
    if not active():
        return

    try:
        from src.market_memory import MarketMemory
        if not getattr(MarketMemory, "_bt_research_patched", False):
            MarketMemory.active_signal = lambda self, signal_timeframe=None: None
            MarketMemory.is_pattern_in_cooldown = lambda self, pattern_key: False
            MarketMemory._bt_research_patched = True
    except Exception:
        pass

    try:
        from src.ai_trainer import AdaptiveTrainer
        if not getattr(AdaptiveTrainer, "_bt_research_patched", False):
            old_init = AdaptiveTrainer.__init__

            @wraps(old_init)
            def init_no_cd(self, *args, **kwargs):
                old_init(self, *args, **kwargs)
                self.loss_cooldown_minutes = 0

            AdaptiveTrainer.__init__ = init_no_cd
            AdaptiveTrainer._bt_research_patched = True
    except Exception:
        pass

    try:
        from src.signal_gate import SignalGate
        if not getattr(SignalGate, "_bt_research_patched", False):
            old_check = SignalGate.check

            @wraps(old_check)
            def check_research(self, signal):
                if not active():
                    return old_check(self, signal)
                if not signal or signal.get("direction") == "NO_TRADE":
                    return False, "NO_SIGNAL"
                pattern_key = signal.get("pattern_key") or ""
                if _is_main(pattern_key):
                    return False, f"BT_RESEARCH_SKIP_MAIN: {pattern_key}"
                try:
                    from src.rr_guard import attach_rr, validate_rr
                    attach_rr(signal)
                    ok, msg, rr = validate_rr(signal, min_rr=2.0)
                    signal["rr_gate_status"] = "PASS" if ok else "RESEARCH_AUDIT_ONLY_FAIL"
                    signal["rr_gate_message"] = msg
                except Exception:
                    signal["rr_gate_status"] = "RESEARCH_AUDIT_ONLY_ERROR"
                if float(signal.get("confidence") or 0) <= 0:
                    return False, "CONFIDENCE_INVALID"
                return True, "BT_RESEARCH_ALLOW"

            SignalGate.check = check_research
            SignalGate._bt_research_patched = True
    except Exception:
        pass

    try:
        from src.market_brain import BrainEngine
        if getattr(BrainEngine, "_bt_research_patched_v2", False):
            return

        old_decide = BrainEngine._decide
        old_build = BrainEngine._build_signal

        @wraps(old_decide)
        def decide_research(self, ctx):
            original = old_decide(self, ctx)
            try:
                direction, reason, pattern_key, confidence = original
                if pattern_key and _is_main(pattern_key):
                    return _research_decision(ctx) or ("NO_TRADE", f"BT_RESEARCH_SKIP_MAIN: {pattern_key}", "WAITING", 0)
                if direction == "NO_TRADE" or str(pattern_key or "").upper() in {"WAITING", "NO_TRADE"}:
                    return _research_decision(ctx) or original
                if pattern_key and not _is_main(pattern_key):
                    # Non-main natural trigger boleh lewat, tapi memory score tetap dinetralkan di build.
                    return original
            except Exception:
                pass
            return _research_decision(ctx) or original

        @wraps(old_build)
        def build_research(self, direction, price, ctx, confidence, reason, pattern_key, pattern):
            if active() and str(reason or "").startswith("BT_RESEARCH"):
                return _research_signal(self.symbol, direction, price, ctx, pattern_key, reason, confidence)
            if active():
                pattern = {"wins": 0, "losses": 0, "score": 0}
            return old_build(self, direction, price, ctx, confidence, reason, pattern_key, pattern)

        BrainEngine._decide = decide_research
        BrainEngine._build_signal = build_research
        BrainEngine._bt_research_patched_v2 = True
    except Exception:
        pass
