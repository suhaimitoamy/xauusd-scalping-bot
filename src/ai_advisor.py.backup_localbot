import os
import requests
import json
from src.formatter import setup_logger

logger = setup_logger("AIAdvisor")

_AI_CONFIG = {
    "enabled": True,
    "max_tokens": None,
    "temperature": 0.2,
}


def configure_ai(config):
    ai_config = (config or {}).get("ai", {})
    _AI_CONFIG["enabled"] = bool(ai_config.get("enabled", True))
    _AI_CONFIG["max_tokens"] = ai_config.get("max_tokens")
    _AI_CONFIG["temperature"] = ai_config.get("temperature", 0.2)


def get_ai_response(messages, fallback_text, max_tokens=None, timeout=15):
    if not _AI_CONFIG.get("enabled", True):
        return fallback_text, False

    provider = os.getenv("AI_PROVIDER", "openrouter").lower()

    try:
        if provider == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY")
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            if not api_key:
                return fallback_text, False
            url = "https://api.deepseek.com/v1/chat/completions"
        else:
            api_key = os.getenv("OPENROUTER_API_KEY")
            model = os.getenv("OPENROUTER_MODEL")
            if not api_key or not model:
                return fallback_text, False
            url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": _AI_CONFIG.get("temperature", 0.2)
        }
        token_limit = max_tokens if max_tokens is not None else _AI_CONFIG.get("max_tokens")
        if token_limit:
            payload["max_tokens"] = token_limit

        response = requests.post(
            url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip(), True
    except Exception as e:
        print(f"DEBUG: AI Advisor error: {e}")
        logger.error(f"Failed to get AI explanation from {provider}: {e}")
        return fallback_text, False


def fallback_explanation(signal_data):
    if signal_data.get('direction') == 'NO_TRADE':
        return signal_data.get(
            'reason', 'Kondisi pasar tidak memenuhi rule entry.')

    return (
        f"Rule engine generated a {
            signal_data.get(
                'direction',
                'Unknown')} signal. "
        f"Entry area: {signal_data.get('entry_low',
                                       'N/A')} - {signal_data.get('entry_high',
                                                                  'N/A')}. "
        f"SL: {signal_data.get('sl', 'N/A')}, "
        f"TP1: {signal_data.get('tp1', 'N/A')}. "
        f"Confidence is {signal_data.get('confidence', 'N/A')}% "
        f"based on: {signal_data.get('reason', 'N/A')}."
    )


def explain_signal(signal_data, use_premium=False):
    """
    Uses OpenRouter or DeepSeek API. Now acts as AI Challenger.
    """
    if signal_data.get('direction') == 'NO_TRADE':
        return signal_data.get('reason', 'NO TRADE'), False

    prompt = (
        f"Kamu adalah AI Challenger untuk bot XAUUSD scalping.\n"
        f"Jawab singkat, tegas, dan praktis.\n"
        f"Jangan mengarang angka baru.\n"
        f"Jangan mengubah POI, entry, SL, TP, confidence.\n"
        f"Gunakan hanya data dari rule engine.\n"
        f"Jika setup belum valid, katakan WAIT.\n"
        f"Jika entry sudah telat, katakan LATE / NO TRADE.\n"
        f"Jangan menulis 'tentu', 'berikut', atau pembuka basa-basi.\n"
        f"Jangan menulis artikel.\n"
        f"Jangan menulis Chain of Thought.\n"
        f"Output harus cocok untuk Telegram.\n\n"
        f"Signal details:\n"
        f"- Direction: {signal_data.get('direction')}\n"
        f"- Entry Area: {signal_data.get('entry_low')} - {signal_data.get('entry_high')}\n"
        f"- Stop Loss: {signal_data.get('sl')}\n"
        f"- Take Profit 1: {signal_data.get('tp1')}\n"
        f"- Take Profit 2: {signal_data.get('tp2')}\n"
        f"- Take Profit 3: {signal_data.get('tp3')}\n"
        f"- Confidence Final: {signal_data.get('confidence')}%\n"
        f"- Reason: {signal_data.get('reason')}\n\n"
    )

    if use_premium:
        prompt += (
            "Provide output in this EXACT format:\n"
            "AI Review: [AGREE / REJECT / WAIT]\n"
            "AI Note: [1-2 kalimat analisa singkat]"
        )
    else:
        prompt += "Berikan 1-2 kalimat analisa pendek yang tegas."

    messages = [
        {"role": "system", "content": "You are AI Challenger for XAUUSD bot. Respond strictly in format. No introductory words."},
        {"role": "user", "content": prompt}
    ]

    return get_ai_response(messages, fallback_explanation(signal_data))


def explain_weekly_report(stats):
    fallback = "Data mingguan menunjukkan performa rule engine tanpa catatan tambahan."
    prompt = f"Berikan 3 kalimat kesimpulan performa mingguan XAUUSD berdasar data berikut:\n{
        json.dumps(stats)}"
    messages = [
        {"role": "system", "content": "You are an AI market performance analyst."},
        {"role": "user", "content": prompt}
    ]
    res, _ = get_ai_response(messages, fallback)
    return res


def explain_rule_review(stats):
    total = int(stats.get('total', 0) or 0)
    if total < 30:
        return (
            "📊 XAUUSD RULE REVIEW\nSource: RULE ENGINE\n\n"
            f"Data trade masih terlalu sedikit: {total} trade.\n"
            "Belum cukup untuk mengubah rule.\n\n"
            "Observasi:\n- Jalankan bot sampai minimal 30 trade untuk evaluasi awal.\n"
            "- Minimal 100 trade untuk rekomendasi rule yang lebih kuat.\n\n"
            "Action:\nTidak ada perubahan rule."
        )
    fallback = "Tidak ada rekomendasi khusus saat ini. Kumpulkan lebih banyak data."
    prompt = (
        f"Analisa performa rule engine bot ini berdasarkan statistik 7 hari:\n{json.dumps(stats)}\n"
        "Berikan 3 bullet rekomendasi ringan. Jangan klaim profit."
    )
    messages = [
        {"role": "system", "content": "You are an AI trading bot evaluator. Keep it concise."},
        {"role": "user", "content": prompt}
    ]
    res, used_ai = get_ai_response(messages, fallback, max_tokens=250)
    title = "📊 XAUUSD RULE REVIEW\nSource: RULE ENGINE + AI ADVISOR" if used_ai else "📊 XAUUSD RULE REVIEW\nSource: RULE ENGINE"
    return f"{title}\n\n{res}"


def explain_market_plan(prompt_data):
    fallback = "Data tidak cukup untuk menyusun MARKET PLAN saat ini."

    import json
    try:
        data = json.loads(prompt_data)
        wib_time = data.get("timestamp_wib", "<waktu_sekarang>")
    except BaseException:
        wib_time = "<waktu_sekarang>"

    prompt = (
        f"Buat XAUUSD MARKET PLAN berdasarkan data dari RULE ENGINE ini:\n"
        f"{prompt_data}\n\n"
        f"Gunakan format ini persis (tanpa basa-basi):\n"
        f"📍 XAUUSD SCALPING PLAN\n"
        f"Source: RULE ENGINE + AI ADVISOR\n"
        f"Update: {wib_time} WIB\n\n"
        f"Bias M15: ...\n"
        f"M5 Status: ...\n"
        f"Phase: ...\n"
        f"Session: ...\n"
        f"Prioritas: BUY / SELL / WAIT\n"
        f"Area pantau: ...\n"
        f"Setup: FVG / OB / Breaker / OTE / Sweep / Retest / None\n"
        f"Action: ...\n"
        f"Invalid: ...\n"
    )

    messages = [
        {"role": "system",
         "content": "You are a formatting assistant for an automated trading bot. STRICT RULES: You must NEVER detect or invent your own setups (FVG/OB/OTE/Liquidity). You must ONLY format, explain, and audit the exact data provided by the Rule Engine. Do not use markdown backticks around your answer."},
        {"role": "user", "content": prompt}
    ]
    res, _ = get_ai_response(messages, fallback, max_tokens=200)
    return res


def format_ask_output(prompt_data):
    fallback = "Maaf, sistem AI sedang offline. Silakan cek data mentah via CLI."
    prompt = f"Data dari RULE ENGINE:\n{prompt_data}\n\nJawab pertanyaan user berdasarkan data di atas secara ringkas dan informatif. Jangan mendeteksi setup baru, cukup gunakan data yang ada."
    messages = [
        {"role": "system", "content": "You are a helpful trading assistant. STRICT RULES: You must NEVER invent setups or predict prices on your own. You must ONLY explain the Rule Engine's data. If data is missing, admit it. Keep answers under 3 paragraphs."},
        {"role": "user", "content": prompt}
    ]
    res, _ = get_ai_response(messages, fallback, max_tokens=300)
    return res


def explain_admin_review(context_data):
    fallback = "Admin Review tidak tersedia karena API error."

    import re
    total_match = re.search(r'- Total Trades: (\d+)', context_data)
    total_trades = int(total_match.group(1)) if total_match else 0

    if total_trades < 30:
        rules_prompt = "Karena Total Trades masih di bawah 30, HANYA berikan OBSERVASI (jangan buat rekomendasi YES/NO mengubah rule)."
        req_format = (
            f"Kondisi bot: [1 kalimat rangkuman]\n\n"
            f"Masalah terdeteksi:\n"
            f"1. ...\n"
            f"2. ...\n\n"
            f"Observasi:\n"
            f"1. ..."
        )
    elif total_trades < 100:
        rules_prompt = "Total Trades antara 30-99. Berikan rekomendasi ringan untuk penyesuaian rule (jangan jadikan HTF (H1/H4) alasan utama memblokir trade)."
        req_format = (
            f"Kondisi bot: [1 kalimat rangkuman]\n\n"
            f"Masalah terdeteksi:\n"
            f"1. ...\n"
            f"2. ...\n\n"
            f"Rekomendasi Ringan:\n"
            f"1. ...\n\n"
            f"JSON_PROPOSAL: {{\"parameter_to_change\": value}} atau {{}}"
        )
    else:
        rules_prompt = "Total Trades >= 100. Usulkan rekomendasi YES/NO rule update. PENTING: Jangan jadikan HTF (H1/H4) alasan utama memblokir trade scalping."
        req_format = (
            f"Kondisi bot: [1 kalimat rangkuman]\n\n"
            f"Masalah terdeteksi:\n"
            f"1. ...\n"
            f"2. ...\n\n"
            f"Rekomendasi:\n"
            f"1. ...\n"
            f"2. ...\n\n"
            f"Butuh persetujuan:\n"
            f"[Pertanyaan persetujuan misal: Naikkan min confidence counter-trend BUY?]\n"
            f"YES / NO\n\n"
            f"JSON_PROPOSAL: {{\"min_confidence\": 70}} atau {{}}"
        )

    prompt = (
        f"Sebagai AI Admin Agent, evaluasi BOT CONTEXT SUMMARY berikut dan berikan rekomendasi teknis:\n"
        f"{context_data}\n\n"
        f"Instruksi tambahan:\n"
        f"{rules_prompt}\n\n"
        f"Format output yang wajib:\n"
        f"{req_format}"
    )

    messages = [
        {"role": "system", "content": "You are an AI Admin Agent analyzing a trading bot's health and performance. Give strict, concise technical recommendations."},
        {"role": "user", "content": prompt}
    ]

    res, _ = get_ai_response(messages, fallback, max_tokens=400)
    return res
