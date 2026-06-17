#!/usr/bin/env python3
from pathlib import Path

ROOT = Path.cwd()
lk_path = ROOT / "src" / "local_knowledge_agent.py"
ti_path = ROOT / "src" / "telegram_interactive.py"
config_path = ROOT / "config.yaml"

if not lk_path.exists():
    raise SystemExit("src/local_knowledge_agent.py tidak ditemukan")
if not ti_path.exists():
    raise SystemExit("src/telegram_interactive.py tidak ditemukan")

lk = lk_path.read_text(encoding="utf-8")
ti = ti_path.read_text(encoding="utf-8")

needle = """        if not raw or raw.startswith('/'):
            return None

        # Utility questions (time, etc.) — always check first
"""
insert = """        if not raw or raw.startswith('/'):
            return None

        signal_edu = self._handle_signal_education_question(raw)
        if signal_edu:
            self._log(chat_id, user_id, username, raw, 'SIGNAL_EDUCATION', signal_edu)
            return signal_edu

        # Utility questions (time, etc.) — always check first
"""
if "signal_edu = self._handle_signal_education_question(raw)" not in lk:
    if needle not in lk:
        raise SystemExit("Marker answer() tidak ditemukan")
    lk = lk.replace(needle, insert, 1)
    print("✅ Route edukasi signal dipasang di local_knowledge_agent.py")
else:
    print("ℹ️ Route edukasi signal sudah ada")

methods = """
    # ══════════════════════════════════════════════════════════════════
    # SIGNAL EDUCATION HANDLER — satu pintu lokal, tanpa AI
    # ══════════════════════════════════════════════════════════════════
    def _handle_signal_education_question(self, text):
        # Jawab pertanyaan signal aktif / follow-up 'kenapa' dari data bot lokal.
        if not self._is_signal_education_question(text):
            return None

        signal = self._active_or_latest_signal()
        if not signal:
            return self._label_local(
                "Source: BOT DATA ONLY\n\n"
                "Belum ada signal BUY/SELL terakhir yang bisa dijelaskan."
            )

        return self._format_signal_education(signal, source="BOT DATA ONLY")

    @staticmethod
    def _is_signal_education_question(text):
        norm = normalize_text(text)
        if not norm:
            return False

        concept_prefixes = (
            'apa itu', 'itu apa', 'pengertian', 'definisi', 'maksud ob',
            'maksud fvg', 'maksud bos', 'maksud choch', 'maksud mss',
        )
        if any(norm.startswith(p) for p in concept_prefixes):
            return False

        exact_followup = {
            'kenapa', 'why', 'alasan', 'alasannya', 'detail', 'detailnya',
            'jelaskan', 'jelasin', 'gimana', 'bagaimana',
        }
        if norm in exact_followup:
            return True

        signal_phrases = (
            'buy atau sell', 'sell atau buy', 'buy apa sell',
            'enaknya buy', 'enaknya sell', 'enaknya sell atau buy',
            'enaknya buy atau sell', 'mending buy', 'mending sell',
            'rekomendasi buy', 'rekomendasi sell',
            'arah signal', 'arah sinyal', 'signal aktif', 'sinyal aktif',
            'setup aktif', 'setup sekarang', 'kenapa buy', 'kenapa sell',
            'kenapa signal', 'kenapa sinyal', 'kenapa setup',
            'alasan buy', 'alasan sell', 'alasan signal', 'alasan sinyal',
        )
        return any(p in norm for p in signal_phrases)

    def _active_or_latest_signal(self):
        # Ambil active signal dari MarketMemory, fallback ke signal terakhir DB.
        try:
            from src.market_memory import MarketMemory
            memory = MarketMemory(self.storage)
            active = memory.active_signal()
            if active and active.get('direction') in ('BUY', 'SELL'):
                return active
        except Exception:
            pass

        try:
            rows = self.storage.fetchall(
                "SELECT * FROM signals WHERE direction IN ('BUY','SELL') ORDER BY id DESC LIMIT 1"
            )
            return rows[0] if rows else None
        except Exception:
            return None

    @staticmethod
    def _signal_fmt(value, nd=3):
        try:
            if value is None or value == '':
                return "N/A"
            return f"{float(value):.{nd}f}"
        except Exception:
            return str(value)

    @staticmethod
    def _parse_signal_raw(signal):
        raw = signal.get('raw_context_json') or signal.get('raw_json') or '{}'
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _latest_price_local(self, symbol='XAU/USD'):
        if self._bot_state:
            price = self._bot_state.get('last_price')
            if price:
                return price
        try:
            rows = self.storage.fetchall(
                "SELECT price FROM ticks WHERE symbol=? ORDER BY id DESC LIMIT 1",
                (symbol,),
            )
            if rows:
                return rows[0].get('price')
        except Exception:
            pass
        try:
            rows = self.storage.fetchall(
                "SELECT close FROM candles WHERE symbol=? AND is_closed=1 ORDER BY open_time DESC LIMIT 1",
                (symbol,),
            )
            if rows:
                return rows[0].get('close')
        except Exception:
            pass
        return None

    def _latest_zone_local(self, table, symbol='XAU/USD'):
        try:
            rows = self.storage.fetchall(
                f"SELECT * FROM {table} WHERE symbol=? ORDER BY id DESC LIMIT 1",
                (symbol,),
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def _format_signal_education(self, signal, source="BOT DATA ONLY"):
        # Format tunggal untuk 'sell/buy?' dan 'kenapa?'.
        raw = self._parse_signal_raw(signal)
        ctx = raw.get('brain_context') or raw.get('context') or raw.get('ctx') or {}

        symbol = signal.get('symbol') or raw.get('symbol') or 'XAU/USD'
        direction = signal.get('direction') or raw.get('direction') or 'N/A'
        entry_low = signal.get('entry_low') or raw.get('entry_low')
        entry_high = signal.get('entry_high') or raw.get('entry_high')
        sl = signal.get('sl') or raw.get('sl')
        tp1 = signal.get('tp1') or raw.get('tp1')
        tp2 = signal.get('tp2') or raw.get('tp2')
        invalid = signal.get('invalid_level') or raw.get('invalid_level') or sl

        pattern = (
            raw.get('pattern_key')
            or signal.get('pattern_key')
            or ctx.get('pattern_key')
            or raw.get('method')
            or "N/A"
        )
        reason = (
            signal.get('reason')
            or raw.get('reason')
            or ctx.get('reason')
            or "Signal dibuat berdasarkan rule bot lokal."
        )

        m15_bias = ctx.get('m15_bias') or ctx.get('bias_m15') or "N/A"
        h1_bias = ctx.get('h1_bias') or ctx.get('bias_h1') or "N/A"
        momentum = ctx.get('momentum') or ctx.get('m5_momentum') or "N/A"
        atr = ctx.get('atr') or raw.get('atr')
        choppy = ctx.get('choppy') if ctx.get('choppy') is not None else "N/A"
        signal_tf = signal.get('signal_timeframe') or raw.get('signal_timeframe') or "N/A"
        signal_class = signal.get('signal_class') or raw.get('signal_class') or "N/A"
        price = self._latest_price_local(symbol)

        supply = self._latest_zone_local('supply_demand_zones', symbol)
        ob = self._latest_zone_local('active_order_blocks', symbol)
        fvg = self._latest_zone_local('active_fvgs', symbol)

        lines = [
            "🤖 Dijawab oleh Bot Lokal",
            f"Source: {source}",
            "",
            "📘 EDUKASI SIGNAL",
            "",
            f"Rekomendasi: {direction}",
            f"Current Price: {self._signal_fmt(price)}",
            f"Entry: {self._signal_fmt(entry_low)} - {self._signal_fmt(entry_high)}",
            f"SL: {self._signal_fmt(sl)}",
            f"TP1: {self._signal_fmt(tp1)}",
            f"TP2: {self._signal_fmt(tp2)}",
            f"Invalidasi: {self._signal_fmt(invalid)}",
            f"Pattern: {pattern}",
            f"Timeframe: {signal_tf}",
            f"Class: {signal_class}",
            "",
            "Alasan:",
            f"1. {reason}",
            f"2. Bias M15: {m15_bias} | Bias H1: {h1_bias}",
            f"3. Momentum M5: {momentum} | ATR: {self._signal_fmt(atr)} | Choppy: {choppy}",
        ]

        if direction == 'SELL':
            lines.append("4. Setup SELL dianggap valid selama harga tidak close kuat di atas SL / invalidasi.")
            lines.append("5. TP diarahkan ke area bawah sesuai target bot.")
        elif direction == 'BUY':
            lines.append("4. Setup BUY dianggap valid selama harga tidak close kuat di bawah SL / invalidasi.")
            lines.append("5. TP diarahkan ke area atas sesuai target bot.")

        idx = 6
        if supply:
            ztype = supply.get('zone_type') or supply.get('type') or 'zone'
            lines.append(
                f"{idx}. Zone terakhir: {ztype} "
                f"{self._signal_fmt(supply.get('low'))} - {self._signal_fmt(supply.get('high'))}"
            )
            idx += 1

        if ob:
            ob_type = ob.get('type') or ob.get('direction') or 'OB'
            lines.append(
                f"{idx}. OB terakhir: {ob_type} "
                f"{self._signal_fmt(ob.get('low'))} - {self._signal_fmt(ob.get('high'))}"
            )
            idx += 1

        if fvg:
            fvg_type = fvg.get('direction') or 'FVG'
            lines.append(
                f"{idx}. FVG terakhir: {fvg_type} "
                f"{self._signal_fmt(fvg.get('low'))} - {self._signal_fmt(fvg.get('high'))}"
            )

        lines.extend([
            "",
            "Status:",
            f"{direction} masih valid selama harga tidak close kuat melewati invalidasi {self._signal_fmt(invalid)}.",
        ])

        return "\n".join(lines)
"""

marker = """    # ══════════════════════════════════════════════════════════════════
    # MARKET HANDLER
"""
if "_handle_signal_education_question" not in lk:
    if marker not in lk:
        raise SystemExit("Marker MARKET HANDLER tidak ditemukan")
    lk = lk.replace(marker, methods + "\n" + marker, 1)
    print("✅ Method edukasi signal digabung ke local_knowledge_agent.py")
else:
    print("ℹ️ Method edukasi signal sudah ada")

old = """            active = memory.active_signal()
            if active:
                return f"Saat ini bot sedang merekomendasikan setup {active.get('direction')} di area {active.get('entry_low')} - {active.get('entry_high')} dengan SL di {active.get('sl')}."
"""
new = """            active = memory.active_signal()
            if active:
                return self._format_signal_education(active, source="BOT DATA ONLY")
"""
if old in lk:
    lk = lk.replace(old, new, 1)
    print("✅ Jawaban buy/sell diarahkan ke format edukasi signal")
else:
    print("ℹ️ Blok buy/sell lama tidak ditemukan / sudah diganti")

lk_path.write_text(lk, encoding="utf-8")

old_ti = """        self.ai_fallback = None
        if storage is not None:
            try:
                from src.market_context_ai import TelegramMarketAI
                self.ai_fallback = TelegramMarketAI(storage, bot_state=self.bot_state)
            except Exception as e:
                logger.warning(f"Telegram AI fallback init failed: {e}")
"""
new_ti = """        self.ai_fallback = None
        ai_fallback_enabled = os.getenv("TELEGRAM_AI_FALLBACK_ENABLED", "false").lower() in ("true", "1", "yes", "on")
        if storage is not None and ai_fallback_enabled:
            try:
                from src.market_context_ai import TelegramMarketAI
                self.ai_fallback = TelegramMarketAI(storage, bot_state=self.bot_state)
            except Exception as e:
                logger.warning(f"Telegram AI fallback init failed: {e}")
"""
if old_ti in ti:
    ti = ti.replace(old_ti, new_ti, 1)
    print("✅ Telegram AI fallback default OFF")
elif "TELEGRAM_AI_FALLBACK_ENABLED" in ti:
    print("ℹ️ Telegram AI fallback sudah dikunci env")
else:
    print("⚠️ Blok AI fallback tidak ditemukan")

ti_path.write_text(ti, encoding="utf-8")

if config_path.exists():
    config = config_path.read_text(encoding="utf-8")
    config = config.replace("ai:\n  enabled: true", "ai:\n  enabled: false")
    config = config.replace("  provider: deepseek", "  provider: local_bot")
    config = config.replace("  allow_ai_for_sweep_break_important: true", "  allow_ai_for_sweep_break_important: false")
    config = config.replace("  allow_ai_for_poi_report: true", "  allow_ai_for_poi_report: false")
    config = config.replace("  allow_ai_for_premium_signal: true", "  allow_ai_for_premium_signal: false")
    config = config.replace("  use_ai: true", "  use_ai: false")
    config_path.write_text(config, encoding="utf-8")
    print("✅ Config AI dipastikan OFF")

dup = ROOT / "src" / "local_bot_education.py"
if dup.exists():
    dup.unlink()
    print("✅ src/local_bot_education.py dihapus agar satu pintu")

print("✅ Patch selesai")
