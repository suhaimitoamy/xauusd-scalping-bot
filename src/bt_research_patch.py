"""Backtest-only research logic for NON-LIVE_MAIN methods.

Aktif hanya saat BT_RESEARCH=true.
Live trading tidak berubah.

V3: cover-all candidate lab.
- LIVE_MAIN dilewati otomatis dari config.yaml.
- Cooldown dimatikan hanya saat BT_RESEARCH.
- Active signal lock dimatikan hanya saat BT_RESEARCH.
- Setiap slot research memilih satu metode non-main secara rotasi.
- Kalau logic natural keluarga metode cocok, signal diberi alasan natural.
- Kalau tidak cocok, tetap dibuat forced-sample agar semua metode punya data.
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
    per_day = max(1, int(os.environ.get("BT_RESEARCH_PER_DAY", "24") or 24))
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
    h1 = str(ctx.get("h1_bias") or "").lower()
    if prev_high and close > prev_high:
        return "BUY"
    if prev_low and close < prev_low:
        return "SELL"
    if momentum == "bullish" or (m15 == "bullish" and h1 != "bearish"):
        return "BUY"
    if momentum == "bearish" or (m15 == "bearish" and h1 != "bullish"):
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

    fallback = []
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
    bullish = close > open_
    bearish = close < open_
    strong = st["ratio"] >= 0.35
    very_strong = st["ratio"] >= 0.55
    small = st["ratio"] <= 0.32
    near_high = close >= st["high"] - st["range"] * 0.35
    near_low = close <= st["low"] + st["range"] * 0.35
    lower_reject = st["lower_wick"] >= max(st["body"] * 0.35, atr * 0.08)
    upper_reject = st["upper_wick"] >= max(st["body"] * 0.35, atr * 0.08)
    buy = direction == "BUY"
    sell = direction == "SELL"

    if "SESSION_OPEN_BREAKOUT" in method:
        if buy and hour in {7, 8, 9, 13, 14, 15} and bullish and (break_bull or near_high):
            return direction, "SESSION OPEN BUY v3: session push + close near high", method, 73.0
        if sell and hour in {7, 8, 9, 13, 14, 15} and bearish and (break_bear or near_low):
            return direction, "SESSION OPEN SELL v3: session push + close near low", method, 73.0

    if "LONDON_OPEN" in method or "LONDON_KILLZONE" in method:
        if hour in {7, 8, 9, 10} and ((buy and bullish) or (sell and bearish)):
            return direction, "LONDON v3: london directional candle", method, 69.0

    if "NY_OPEN" in method or "NY_KILLZONE" in method:
        if hour in {13, 14, 15, 16} and ((buy and bullish) or (sell and bearish)):
            return direction, "NY v3: new york directional candle", method, 69.0

    if "ASIA" in method or "ASIAN" in method:
        if buy and hour in {0, 1, 2, 3, 4, 5, 6} and (sentuh_low or lower_reject) and bullish:
            return direction, "ASIA BUY v3: low reaction + bullish close", method, 66.0
        if sell and hour in {0, 1, 2, 3, 4, 5, 6} and (sentuh_high or upper_reject) and bearish:
            return direction, "ASIA SELL v3: high reaction + bearish close", method, 66.0

    if "IFVG" in method or "FVG" in method:
        if buy and bullish and (break_bull or lower_reject or m15 == "bullish") and momentum != "bearish":
            return direction, "FVG/IFVG BUY v3: imbalance continuation/retest proxy", method, 71.0
        if sell and bearish and (break_bear or upper_reject or m15 == "bearish") and momentum != "bullish":
            return direction, "FVG/IFVG SELL v3: imbalance continuation/retest proxy", method, 71.0

    if "BOS" in method or "BREAKOUT" in method or "CONTINUATION" in method:
        if buy and (break_bull or (bullish and near_high and very_strong)):
            return direction, "BOS/BREAKOUT BUY v3: break/strong expansion", method, 70.0
        if sell and (break_bear or (bearish and near_low and very_strong)):
            return direction, "BOS/BREAKOUT SELL v3: break/strong expansion", method, 70.0

    if "BREAK_AND_RETEST" in method or "RETEST" in method or "ORDER_BLOCK" in method or "BREAKER" in method or "OB_" in method:
        if buy and (m15 == "bullish" or break_bull) and (bullish or lower_reject):
            return direction, "RETEST/OB BUY v3: reclaim/reaction after displacement", method, 68.0
        if sell and (m15 == "bearish" or break_bear) and (bearish or upper_reject):
            return direction, "RETEST/OB SELL v3: rejection/reaction after displacement", method, 68.0

    if "POI" in method or "ACCUMULATION" in method or "REBOUND" in method or "OTE" in method:
        if buy and pos in {"discount", "equilibrium", "unknown", ""} and (lower_reject or bullish or sentuh_low):
            return direction, "POI BUY v3: discount/equilibrium reaction", method, 67.0
        if sell and pos in {"premium", "equilibrium", "unknown", ""} and (upper_reject or bearish or sentuh_high):
            return direction, "POI SELL v3: premium/equilibrium reaction", method, 67.0

    if "SWEEP" in method or "TURTLE" in method or "LIQUIDITY" in method or "DRAW_ON_LIQUIDITY" in method:
        if buy and (sentuh_low or lower_reject) and bullish:
            return direction, "LIQUIDITY BUY v3: sell-side sweep/reclaim", method, 69.0
        if sell and (sentuh_high or upper_reject) and bearish:
            return direction, "LIQUIDITY SELL v3: buy-side sweep/reclaim", method, 69.0

    if "INDUCEMENT" in method or "TRAP" in method or "CHOCH" in method or "REVERSAL" in method or "EXHAUSTION" in method:
        if buy and (sentuh_low or lower_reject) and bullish and momentum != "bearish":
            return direction, "REVERSAL BUY v3: trap/rejection + bullish reclaim", method, 66.0
        if sell and (sentuh_high or upper_reject) and bearish and momentum != "bullish":
            return direction, "REVERSAL SELL v3: trap/rejection + bearish reclaim", method, 66.0

    if "PULLBACK" in method or "FOLLOW_THE_TREND" in method or "STRICT_M15" in method:
        if buy and m15 == "bullish" and h1 != "bearish" and (bullish or lower_reject):
            return direction, "PULLBACK BUY v3: M15 trend + reclaim", method, 65.0
        if sell and m15 == "bearish" and h1 != "bullish" and (bearish or upper_reject):
            return direction, "PULLBACK SELL v3: M15 trend + rejection", method, 65.0

    if "MOMENTUM" in method or "MARUBOZU" in method:
        if buy and bullish and strong and near_high and momentum != "bearish":
            return direction, "MOMENTUM BUY v3: strong body continuation", method, 66.0
        if sell and bearish and strong and near_low and momentum != "bullish":
            return direction, "MOMENTUM SELL v3: strong body continuation", method, 66.0

    if "CHOPPY" in method:
        if choppy or bias == "sideways" or small:
            if buy and (lower_reject or close <= open_ + atr * 0.20 or sentuh_low):
                return direction, "CHOPPY BUY v3: lower range reaction", method, 60.0
            if sell and (upper_reject or close >= open_ - atr * 0.20 or sentuh_high):
                return direction, "CHOPPY SELL v3: upper range reaction", method, 60.0

    if "NEWS_SPIKE" in method or "SPIKE_FADE" in method:
        big = st["range"] >= max(atr * 1.35, 1.8)
        if big and buy and (lower_reject or bearish):
            return direction, "NEWS FADE BUY v3: spike down fade proxy", method, 58.0
        if big and sell and (upper_reject or bullish):
            return direction, "NEWS FADE SELL v3: spike up fade proxy", method, 58.0

    if method.startswith(("AI_METHOD_", "ANTIGRAVITY_", "RR2_")):
        if buy and (bullish or momentum == "bullish"):
            return direction, "AI/ANTIGRAVITY BUY v3: generic bullish candidate", method, 55.0
        if sell and (bearish or momentum == "bearish"):
            return direction, "AI/ANTIGRAVITY SELL v3: generic bearish candidate", method, 55.0

    return None


def _forced_decision(method: str, ctx: Dict[str, Any]) -> Optional[Decision]:
    direction = _direction_from_method(method) or _side_from_context(ctx)
    return (
        direction,
        "BT_RESEARCH_COVER_ALL v3: forced sample for non-main method; WR ignored for discovery",
        method,
        50.0,
    )


def _research_decision(ctx: Dict[str, Any]) -> Optional[Decision]:
    if not active():
        return None
    slot, should_fire = _research_slot(ctx)
    if not should_fire:
        return None
    methods = _all_non_main_methods()
    if not methods:
        return None

    # Cover-all mode: setiap slot memilih satu metode non-main agar semua metode dapat data.
    method = methods[slot % len(methods)]
    hit = _method_rule(method, ctx)
    if hit:
        return hit

    # Jika metode pilihan tidak cocok dengan market, tetap sample agar metode tidak 0 trade.
    if _on(os.environ.get("BT_RESEARCH_FORCE_ALL", "true")):
        return _forced_decision(method, ctx)

    # Optional: kalau force dimatikan, cari metode lain yang natural cocok.
    side = _side_from_context(ctx)
    for m in methods:
        if (_direction_from_method(m) or side) != side:
            continue
        hit = _method_rule(m, ctx)
        if hit:
            return hit
    return None


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
        "confidence": round(float(confidence or 50.0), 1),
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
            "cover_all_v3": True,
        },
    }


def apply_bt_research_patch() -> None:
    if not active():
        return

    try:
        from src.market_memory import MarketMemory
        if not getattr(MarketMemory, "_bt_research_patched_v3", False):
            MarketMemory.active_signal = lambda self, signal_timeframe=None: None
            MarketMemory.is_pattern_in_cooldown = lambda self, pattern_key: False
            MarketMemory._bt_research_patched_v3 = True
    except Exception:
        pass

    try:
        from src.ai_trainer import AdaptiveTrainer
        if not getattr(AdaptiveTrainer, "_bt_research_patched_v3", False):
            old_init = AdaptiveTrainer.__init__

            @wraps(old_init)
            def init_no_cd(self, *args, **kwargs):
                old_init(self, *args, **kwargs)
                self.loss_cooldown_minutes = 0
                self.auto_ai_review = False
                self.auto_brain_draft = False

            AdaptiveTrainer.__init__ = init_no_cd
            AdaptiveTrainer._bt_research_patched_v3 = True
    except Exception:
        pass

    try:
        from src.signal_gate import SignalGate
        if not getattr(SignalGate, "_bt_research_patched_v3", False):
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
            SignalGate._bt_research_patched_v3 = True
    except Exception:
        pass

    try:
        from src.market_brain import BrainEngine
        if getattr(BrainEngine, "_bt_research_patched_v3", False):
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
                    natural = _research_decision(ctx)
                    return natural or original
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
        BrainEngine._bt_research_patched_v3 = True
    except Exception:
        pass
