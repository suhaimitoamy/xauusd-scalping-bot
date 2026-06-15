"""AI Trainer for adaptive brain.

Learns from closed trades. LOSS gives penalty, TP2 WIN gives reward,
and TP1/PARTIAL_WIN gets only a small reward because TP2 is the final target.
AI can create a draft brain upgrade, but active replacement requires YES approval.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from src.ai_advisor import get_ai_response
from src.ai_context_builder import build_compact_ai_context
from src.brain_writer import BrainWriter
from src.market_memory import MarketMemory


class AdaptiveTrainer:
    def __init__(self, storage, symbol: str = 'XAU/USD', config: Optional[Dict[str, Any]] = None):
        self.storage = storage
        self.symbol = symbol
        self.config = config or {}
        self.memory = MarketMemory(storage)
        cfg = (self.config or {}).get('adaptive_brain', {}).get('trainer', {})
        self.auto_ai_review = bool(cfg.get('auto_ai_review', False))
        self.auto_brain_draft = bool(cfg.get('auto_brain_draft', False))
        self.loss_cooldown_minutes = int(cfg.get('loss_cooldown_minutes', 30))

    def review_closed_signal(self, signal_id: int, current_price: float = 0) -> str:
        signal = self._get_signal(signal_id)
        if not signal:
            return f"Signal #{signal_id} tidak ditemukan."
        result = signal.get('result') or ''
        if result not in ('WIN', 'FULL_WIN', 'LOSS', 'PARTIAL_WIN'):
            return f"Signal #{signal_id} belum punya hasil final."

        prev_training = self.memory.get_training(signal_id)
        prev_result = None
        if prev_training:
            prev_result = prev_training.get('result')
            rank = {'LOSS': 0, 'PARTIAL_WIN': 1, 'WIN': 2, 'FULL_WIN': 3}
            if rank.get(result, -1) <= rank.get(prev_result, -1):
                return f"Signal #{signal_id} sudah pernah dilatih dengan hasil {prev_result}."

        raw = self._raw_signal(signal)
        pattern_key = raw.get('pattern_key') or self._infer_pattern(signal, raw)
        direction = signal.get('direction') or raw.get('direction') or ''

        compact = build_compact_ai_context(self.storage, self.symbol, current_price, raw or signal)
        penalty, reward = self._score_result(result)

        added_penalty = penalty
        added_reward = reward
        if prev_training:
            added_penalty = max(0, penalty - float(prev_training.get('penalty') or 0))
            added_reward = max(0, reward - float(prev_training.get('reward') or 0))

        cooldown = self.loss_cooldown_minutes if result == 'LOSS' else 0
        fallback_lesson = self._fallback_lesson(result, signal, pattern_key)

        self.memory.save_training(signal_id, result, pattern_key, fallback_lesson, penalty, reward, False, {'status': 'pending_ai'})
        pattern = self.memory.update_pattern_result(pattern_key, direction, result, fallback_lesson, added_penalty, added_reward, cooldown, prev_result=prev_result)

        msg = (
            f"🧠 AI TRAINER RESULT (Local Saved)\n"
            f"Signal: #{signal_id} {direction}\n"
            f"Result: {result}" + (f" (Upgraded from {prev_result})" if prev_result else "") + "\n"
            f"Pattern: {pattern_key}\n"
            f"Reward: +{added_reward} | Penalty: -{added_penalty}\n"
            f"Pattern score: {pattern.get('score')}\n"
            f"Local Lesson: {fallback_lesson}\n"
        )

        if (self.auto_ai_review or self.auto_brain_draft) and result in ('LOSS', 'FULL_WIN'):
            import threading
            def bg_ai_task():
                try:
                    lesson, ai_used, ai_json = self._ai_review(signal, raw, compact, result, pattern_key)
                    if ai_used:
                        self.memory.save_training(signal_id, result, pattern_key, lesson, penalty, reward, ai_used, ai_json)
                        self.memory.update_pattern_result(pattern_key, direction, result, lesson, 0.0, 0.0, cooldown, prev_result=result)
                        if self.auto_brain_draft:
                            BrainWriter(self.storage).propose_ai_draft(lesson, compact, pattern_key=pattern_key)
                except Exception as e:
                    import logging
                    logging.getLogger("AITrainer").error(f"Background AI task error: {e}")

            t = threading.Thread(target=bg_ai_task)
            t.daemon = True
            t.start()
            msg += "\n[INFO] Proses AI Trainer & Brain Draft sedang berjalan di background (Timeout 180s)."

        return msg

    def review_latest_closed(self, current_price: float = 0) -> str:
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM signals
            WHERE result IN ('WIN','FULL_WIN','LOSS','PARTIAL_WIN')
            ORDER BY id DESC LIMIT 1
            """
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return "Belum ada signal WIN/LOSS untuk dilatih."
        return self.review_closed_signal(int(row['id']), current_price)

    def _get_signal(self, signal_id: int) -> Optional[Dict[str, Any]]:
        conn = self.storage.get_connection()
        conn.row_factory = __import__('sqlite3').Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM signals WHERE id=?", (signal_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def _raw_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        try:
            raw = json.loads(signal.get('raw_context_json') or '{}')
            return raw if isinstance(raw, dict) else {}
        except Exception as e:
            import logging
            logging.getLogger("AITrainer").warning(f"Error parsing raw_context_json: {e}")
            return {}

    def _infer_pattern(self, signal: Dict[str, Any], raw: Dict[str, Any]) -> str:
        direction = signal.get('direction') or raw.get('direction') or 'UNKNOWN'
        reason = (signal.get('reason') or raw.get('reason') or '').upper()
        if 'SENTUH HIGH' in reason and direction == 'SELL':
            return 'SENTUH_HIGH_SELL'
        if 'SENTUH LOW' in reason and direction == 'BUY':
            return 'SENTUH_LOW_BUY'
        if 'BREAK' in reason:
            return f'BREAK_{direction}'
        return f'ADAPTIVE_{direction}'

    def _score_result(self, result: str) -> tuple[float, float]:
        if result == 'LOSS':
            return 10.0, 0.0
        if result == 'FULL_WIN':
            return 0.0, 15.0
        if result == 'WIN':
            return 0.0, 10.0
        if result == 'PARTIAL_WIN':
            return 0.0, 3.0
        return 0.0, 0.0

    def _ai_review(self, signal: Dict[str, Any], raw: Dict[str, Any], compact: str,
                   result: str, pattern_key: str) -> tuple[str, bool, Dict[str, Any]]:
        fallback = self._fallback_lesson(result, signal, pattern_key)
        if not self.auto_ai_review:
            return fallback, False, {'fallback': True}
        prompt = (
            "Kamu adalah AI Trainer untuk bot XAUUSD adaptive.\n"
            "Tugasmu mengevaluasi SATU hasil trade sebagai pengalaman belajar.\n"
            "Jawab JSON saja, tanpa markdown.\n"
            "Schema:\n"
            "{\"lesson\":\"1 kalimat pelajaran teknis\",\"pattern_key\":\"...\",\"proposed_change\":\"perubahan kecil untuk brain.py\"}\n\n"
            f"RESULT: {result}\n"
            f"PATTERN_KEY: {pattern_key}\n"
            f"SIGNAL: {json.dumps(raw or signal, ensure_ascii=False)}\n"
            f"COMPACT_DB_CONTEXT:\n{compact}\n"
        )
        messages = [
            {"role": "system", "content": "You are a concise AI Trainer for an experimental signal bot. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ]
        response, used = get_ai_response(messages, fallback, max_tokens=350, timeout=180)
        if not used:
            return fallback, False, {'fallback': True}
        try:
            data = json.loads(response.strip())
            lesson = data.get('lesson') or fallback
            return lesson, True, data
        except Exception:
            return response.strip()[:800] or fallback, True, {'raw_response': response}

    def _fallback_lesson(self, result: str, signal: Dict[str, Any], pattern_key: str) -> str:
        direction = signal.get('direction', 'UNKNOWN')
        if result == 'LOSS':
            return f"{pattern_key} {direction} kena SL; beri penalty dan wajib perketat konfirmasi sebelum pola serupa dipakai lagi."
        if result == 'WIN':
            return f"{pattern_key} {direction} TP2; beri reward karena target final tercapai."
        if result == 'FULL_WIN':
            return f"{pattern_key} {direction} TP3; beri reward besar karena full target tercapai."
        return f"{pattern_key} {direction} TP1/PROTECT; reward kecil saja karena TP2 belum final."

    def evaluate_no_trade(self, current_price: float = 0) -> str:
        evaluated = 0
        try:
            pending = self.memory.get_unevaluated_no_trades(minutes_ago=30)
        except Exception as e:
            import logging
            logging.getLogger("AITrainer").error(f"NO_TRADE table error: {e}")
            return "NO_TRADE eval: tabel belum siap."
        if not pending:
            return "Tidak ada NO_TRADE untuk dievaluasi."

        for decision in pending:
            try:
                decision_price = float(decision.get('price') or 0)
                if decision_price <= 0 or current_price <= 0:
                    self.memory.mark_no_trade_evaluated(decision['id'])
                    continue

                move = abs(current_price - decision_price)
                direction = decision.get('direction') or ''
                pattern_key = decision.get('pattern_key') or 'NO_TRADE_GENERIC'
                reason = decision.get('reason') or ''
                price_went_up = current_price > decision_price
                price_went_down = current_price < decision_price

                missed = False
                if move >= 5.0:
                    reason_upper = reason.upper()
                    if price_went_up and any(k in reason_upper for k in ['BUY', 'BULLISH', 'DEMAND', 'LOW']):
                        missed = True
                    elif price_went_down and any(k in reason_upper for k in ['SELL', 'BEARISH', 'SUPPLY', 'HIGH']):
                        missed = True

                if missed:
                    penalty, reward = 3.0, 0.0
                    result_tag = 'MISSED_OPPORTUNITY'
                    lesson = f"NO_TRADE saat harga bergerak ${move:.1f}. Peluang terlewat."
                elif move < 3.0:
                    penalty, reward = 0.0, 2.0
                    result_tag = 'GOOD_SKIP'
                    lesson = f"NO_TRADE benar, harga hanya bergerak ${move:.1f}. Skip tepat."
                else:
                    penalty, reward = 0.0, 0.0
                    result_tag = 'NEUTRAL_SKIP'
                    lesson = f"NO_TRADE netral, harga bergerak ${move:.1f}."

                if penalty > 0 or reward > 0:
                    self.memory.update_pattern_result(pattern_key, direction, result_tag, lesson, penalty, reward, 0)

                self.memory.mark_no_trade_evaluated(decision['id'])
                evaluated += 1
            except Exception as e:
                import logging
                logging.getLogger("AITrainer").error(f"Error evaluating NO_TRADE decision {decision.get('id', 'unknown')}: {e}")
        return f"NO_TRADE eval selesai: {evaluated} keputusan dievaluasi."
