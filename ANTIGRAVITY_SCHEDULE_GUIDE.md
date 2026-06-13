# Antigravity Schedule Guide — XAUUSD Method Evaluator

## Tujuan
Schedule Antigravity dipakai sebagai AI evaluator, bukan auto-editor.
Bot live tetap jalan seperti biasa. Antigravity hanya membaca hasil trade, menjalankan script laporan, dan membuat ringkasan.

## Command evaluator
Dari root project:

```bash
python tools/schedule_method_report.py --period weekly --send-telegram
```

```bash
python tools/schedule_method_report.py --period monthly --send-telegram
```

Report tersimpan di:

```text
reports/
```

## Weekly schedule
Pakai prompt dari:

```text
antigravity_schedules/weekly_method_review_prompt.md
```

Frekuensi: 1 minggu sekali.

## Monthly schedule
Pakai prompt dari:

```text
antigravity_schedules/monthly_method_review_prompt.md
```

Frekuensi: 1 bulan sekali.

## Guardrail
- Metode utama ada di `config.yaml > adaptive_brain > main_methods`.
- Metode LOCKED ada di `config.yaml > adaptive_brain > method_governance > locked_methods`.
- AI/Antigravity tidak boleh mengubah metode LOCKED.
- Semua perubahan metode harus approval owner.

## Env yang diperlukan
```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat
```
