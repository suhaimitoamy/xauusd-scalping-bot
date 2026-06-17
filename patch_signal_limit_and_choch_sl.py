#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path.cwd()
config_path = ROOT / "config.yaml"
brain_path = ROOT / "src" / "market_brain.py"

if not config_path.exists():
    raise SystemExit("config.yaml tidak ditemukan")
if not brain_path.exists():
    raise SystemExit("src/market_brain.py tidak ditemukan")

config = config_path.read_text(encoding="utf-8")
brain = brain_path.read_text(encoding="utf-8")

config_new = re.sub(
    r"(^\s*max_signals_per_day:\s*)\d+(\s*$)",
    r"\g<1>999\2",
    config,
    count=1,
    flags=re.MULTILINE,
)

if config_new == config:
    print("⚠️ max_signals_per_day tidak ditemukan / sudah berubah.")
else:
    config_path.write_text(config_new, encoding="utf-8")
    print("✅ max_signals_per_day diubah ke 999")

helper = '''
    def _choch_reversal_sell_sl_plan(self, price: float, ctx: Dict[str, Any]) -> Tuple[float, float, float]:
        """SL khusus METHOD_CHOCH_REVERSAL_SELL.

        Hanya untuk METHOD_CHOCH_REVERSAL_SELL.
        SL dibuat di atas swing/sweep high + ATR buffer.
        """
        struct = ctx.get('structure', {}) or {}
        atr = max(float(ctx.get('atr') or 2.0), 0.50)

        last_high = float(ctx.get('last_high') or price)
        prev_high = float(ctx.get('prev_high') or last_high)

        candidates = [last_high, prev_high]

        for key in ('nearest_resistance', 'liquidity_above', 'break_level', 'sweep_extreme'):
            value = struct.get(key)
            if value is not None:
                try:
                    candidates.append(float(value))
                except Exception:
                    pass

        inv_level = struct.get('invalidation_level')
        inv_label = str(struct.get('invalidation_label') or '').lower()
        if inv_level is not None and ('lower high' in inv_label or 'high' in inv_label):
            try:
                candidates.append(float(inv_level))
            except Exception:
                pass

        structure_high = max(candidates) if candidates else last_high
        buffer_points = max(atr * 0.55, 1.50)

        raw_sl = structure_high + buffer_points
        min_sl_dist = max(atr * 1.80, 8.00)

        method_cfg = (
            ((self.config or {}).get('adaptive_brain', {}) or {})
            .get('method_risk_overrides', {}) or {}
        ).get('METHOD_CHOCH_REVERSAL_SELL', {}) or {}

        max_sl_dist = float(method_cfg.get('max_sl_points', 14.0))
        sl_dist = max(raw_sl - float(price), min_sl_dist)
        sl_dist = min(sl_dist, max_sl_dist)

        sl = float(price) + sl_dist
        tp1 = float(price) - (sl_dist * self.tp1_rr)
        tp2 = float(price) - (sl_dist * self.tp2_rr)

        return round(sl, 3), round(tp1, 3), round(tp2, 3)
'''

if "_choch_reversal_sell_sl_plan" not in brain:
    marker = "    def _build_signal(self, direction: str, price: float, ctx: Dict[str, Any], confidence: float,\n"
    if marker not in brain:
        raise SystemExit("Marker _build_signal tidak ditemukan")
    brain = brain.replace(marker, helper + "\n" + marker, 1)
    print("✅ Helper SL khusus METHOD_CHOCH_REVERSAL_SELL ditambahkan")
else:
    print("ℹ️ Helper METHOD_CHOCH_REVERSAL_SELL sudah ada")

target = """        elif direction == 'BUY':
            # SL is nearest support or swing low
"""

replacement = """        elif pattern_key == 'METHOD_CHOCH_REVERSAL_SELL':
            sl, tp1, tp2 = self._choch_reversal_sell_sl_plan(price, ctx)

        elif direction == 'BUY':
            # SL is nearest support or swing low
"""

if "elif pattern_key == 'METHOD_CHOCH_REVERSAL_SELL':" not in brain:
    if target not in brain:
        raise SystemExit("Target branch default BUY tidak ditemukan")
    brain = brain.replace(target, replacement, 1)
    print("✅ Branch SL khusus METHOD_CHOCH_REVERSAL_SELL dipasang")
else:
    print("ℹ️ Branch METHOD_CHOCH_REVERSAL_SELL sudah ada")

brain_path.write_text(brain, encoding="utf-8")
print("✅ Patch selesai")
