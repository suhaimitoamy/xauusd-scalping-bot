"""Backtest-only research patch.

Tujuan:
- Mode ini hanya aktif saat environment BT_RESEARCH=true.
- Live trading tidak berubah.
- Backtest riset mengabaikan active-signal lock dan cooldown.
- LIVE_MAIN tidak ikut dites sebagai kandidat.
- Saat brain tidak menemukan setup non-main, mode ini membuat trigger eksplorasi
  untuk metode non-main agar metode yang jarang/tidak pernah trigger bisa dinilai.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple


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
        return dt
    except Exception:
        return None


def _research_slot(ctx: Dict[str, Any]) -> Tuple[int, bool]:
    dt = _ctx_datetime(ctx)
    if dt is None:
        return 0, True
    per_day = max(1, int(os.environ.get("BT_RESEARCH_PER_DAY", "8") or 8))
    spacing_minutes = max(5, int(1440 / per_day))
    minute_of_day = dt.hour * 60 + dt.minute
    slot = (dt.timetuple().tm_yday * per_day) + int(minute_of_day / spacing_minutes)
    return slot, (minute_of_day % spacing_minutes == 0)


def _side(ctx: Dict[str, Any]) -> str:
    close = _num(ctx, "last_close")
    open_ = _num(ctx, "last_open")
    prev_high = _num(ctx, "prev_high")
    prev_low = _num(ctx, "prev_low")
    if prev_high and close > prev_high:
        return "BUY"
    if prev_low and close < prev_low:
        return "SELL"
    return "BUY" if close >= open_ else "SELL"


def _load_registry_methods(direction: str) -> List[str]:
    direction = str(direction or "").upper()
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
            if direction and not (method.endswith("_" + direction) or direction in method):
                continue
            if method not in methods:
                methods.append(method)
    except Exception:
        pass

    fallback = [
        f"METHOD_BREAK_AND_RETEST_{direction}",
        f"METHOD_BOS_RETEST_OB_{direction}",
        f"METHOD_ORDER_BLOCK_TAP_{direction}",
        f"METHOD_NY_OPEN_BREAKOUT_{direction}",
        f"METHOD_LONDON_OPEN_BREAKOUT_{direction}",
        f"METHOD_DRAW_ON_LIQUIDITY_{direction}",
        f"METHOD_INDUCEMENT_TRAP_{direction}",
        f"METHOD_ASIA_RANGE_SWEEP_{direction}",
        f"METHOD_MOMENTUM_IGNITION_{direction}",
        f"METHOD_POI_ACCUMULATION_{direction}",
        f"METHOD_POI_REBOUND_OB_{direction}",
    ]
    for method in fallback:
        if not _is_main(method) and method not in methods:
            methods.append(method)
    return methods


def _research_decision(ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
    if not active():
        return None
    slot, should_fire = _research_slot(ctx)
    if not should_fire:
        return None
    direction = _side(ctx)
    methods = _load_registry_methods(direction)
    if not methods:
        return None
    method = methods[slot % len(methods)]
    return (
        direction,
        "BT_RESEARCH candidate trigger; cooldown off; LIVE_MAIN excluded; WR ignored",
        method,
        65.0,
    )


def _research_signal(symbol: str, direction: str, price: float, ctx: Dict[str, Any], pattern_key: str, reason: str) -> Dict[str, Any]:
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
        "confidence": 65.0,
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
        if getattr(BrainEngine, "_bt_research_patched", False):
            return

        old_decide = BrainEngine._decide
        old_build = BrainEngine._build_signal

        @wraps(old_decide)
        def decide_research(self, ctx):
            result = old_decide(self, ctx)
            try:
                direction, reason, pattern_key, confidence = result
                if pattern_key and _is_main(pattern_key):
                    return _research_decision(ctx) or ("NO_TRADE", f"BT_RESEARCH_SKIP_MAIN: {pattern_key}", "WAITING", 0)
                if direction == "NO_TRADE" or str(pattern_key or "").upper() in {"WAITING", "NO_TRADE"}:
                    return _research_decision(ctx) or result
            except Exception:
                pass
            return result

        @wraps(old_build)
        def build_research(self, direction, price, ctx, confidence, reason, pattern_key, pattern):
            if active() and str(reason or "").startswith("BT_RESEARCH"):
                return _research_signal(self.symbol, direction, price, ctx, pattern_key, reason)
            if active():
                pattern = {"wins": 0, "losses": 0, "score": 0}
            return old_build(self, direction, price, ctx, confidence, reason, pattern_key, pattern)

        BrainEngine._decide = decide_research
        BrainEngine._build_signal = build_research
        BrainEngine._bt_research_patched = True
    except Exception:
        pass
