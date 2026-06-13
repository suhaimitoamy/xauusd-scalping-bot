from src.market_structure import get_swings


def detect_fvg(candles):
    for i in range(len(candles) - 3, 0, -1):
        c1, _, c3 = candles[i - 1], candles[i], candles[i + 1]
        # Bullish FVG
        if c3['low'] > c1['high']:
            return f"{c1['high']} - {c3['low']}", "Bullish FVG"
        # Bearish FVG
        if c3['high'] < c1['low']:
            return f"{c3['high']} - {c1['low']}", "Bearish FVG"
    return None, None


def detect_ob(candles):
    # simple OB logic
    for i in range(len(candles) - 2, 1, -1):
        c = candles[i]
        prev = candles[i - 1]
        # Bullish OB: bearish candle followed by strong bullish displacement
        if prev['close'] < prev['open'] and c['close'] > c['open'] and (
                c['close'] - c['open']) > (prev['open'] - prev['close']) * 1.5:
            return f"{prev['low']} - {prev['high']}", "Bullish OB"
        # Bearish OB: bullish candle followed by strong bearish displacement
        if prev['close'] > prev['open'] and c['close'] < c['open'] and (
                c['open'] - c['close']) > (prev['close'] - prev['open']) * 1.5:
            return f"{prev['low']} - {prev['high']}", "Bearish OB"
    return None, None


def build_poi_map(storage, symbol):
    # Retrieve candles for H4, H1, M15, M5
    h4 = storage.get_recent_candles(symbol, "H4", 100)
    h1 = storage.get_recent_candles(symbol, "H1", 100)
    m15 = storage.get_recent_candles(symbol, "M15", 100)
    m5 = storage.get_recent_candles(symbol, "M5", 100)

    poi_data = {
        "timeframe": "MULTI",
        "h4": {"bias": "Data belum cukup", "main_poi": "Data belum cukup", "type": "Data belum cukup", "strength": 0, "reason": "Menunggu data H4"},
        "h1": {"main_poi": "Data belum cukup", "type": "Data belum cukup", "strength": 0, "reason": "Menunggu data H1"},
        "m15": {"bias": "MIXED", "poi": "Data belum cukup", "type": "Data belum cukup", "liquidity_above": "Data belum cukup", "liquidity_below": "Data belum cukup"},
        "m5": {"trigger_area": "Data belum cukup", "type": "Data belum cukup", "status": "no setup"}
    }

    if len(h4) >= 10:
        h4_highs, h4_lows = get_swings(h4, 2, 2)
        h4_bias = "BEARISH" if h4[-1]['close'] < h4[0]['open'] else "BULLISH"
        poi_data["h4"]["bias"] = h4_bias

        area, ptype = detect_ob(h4)
        if not area:
            area, ptype = detect_fvg(h4)
        if not area and h4_highs and h4_lows:
            area = f"{h4_lows[-1]['low']} - {h4_highs[-1]['high']}"
            ptype = "Supply" if h4_bias == "BEARISH" else "Demand"

        if area:
            poi_data["h4"]["main_poi"] = area
            poi_data["h4"]["type"] = ptype
            poi_data["h4"]["strength"] = 80
            poi_data["h4"]["reason"] = f"Detected {ptype} in {h4_bias} trend"

    if len(h1) >= 10:
        h1_highs, h1_lows = get_swings(h1, 3, 3)
        curr = h1[-1]['close']

        area, ptype = detect_ob(h1)
        if not area:
            area, ptype = detect_fvg(h1)

        if not area:
            sups = [l['low'] for l in h1_lows if l['low'] < curr]
            ress = [h['high'] for h in h1_highs if h['high'] > curr]
            nearest_sup = max(sups) if sups else None
            nearest_res = min(ress) if ress else None

            if poi_data["h4"]["bias"] == "BEARISH" and nearest_res:
                area = f"{nearest_res} - {nearest_res + 2.0}"
                ptype = "Supply / Resistance"
            elif poi_data["h4"]["bias"] == "BULLISH" and nearest_sup:
                area = f"{nearest_sup - 2.0} - {nearest_sup}"
                ptype = "Demand / Support"
            elif nearest_sup and nearest_res:
                area = f"{nearest_sup} / {nearest_res}"
                ptype = "Support/Resistance"

        if area:
            poi_data["h1"]["main_poi"] = area
            poi_data["h1"]["type"] = ptype
            poi_data["h1"]["strength"] = 70
            poi_data["h1"]["reason"] = f"{ptype} area near current price"

    if len(m15) >= 10:
        m15_highs, m15_lows = get_swings(m15, 2, 2)
        curr = m15[-1]['close']

        m15_bias = "BEARISH" if m15[-1]['close'] < m15[0]['open'] else "BULLISH"
        poi_data["m15"]["bias"] = m15_bias

        area, ptype = detect_fvg(m15)
        if not area:
            area, ptype = detect_ob(m15)

        if area:
            poi_data["m15"]["poi"] = area
            poi_data["m15"]["type"] = ptype

        liqs_above = [h['high'] for h in m15_highs if h['high'] > curr]
        liqs_below = [l['low'] for l in m15_lows if l['low'] < curr]

        if liqs_above:
            poi_data["m15"]["liquidity_above"] = str(min(liqs_above))
        if liqs_below:
            poi_data["m15"]["liquidity_below"] = str(max(liqs_below))

    if len(m5) >= 10:
        m5_highs, m5_lows = get_swings(m5, 2, 2)

        area, ptype = detect_ob(m5)
        if not area:
            area, ptype = detect_fvg(m5)

        if not area and m5_highs and m5_lows:
            area = f"{m5_lows[-1]['low']} - {m5_highs[-1]['high']}"
            ptype = "Consolidation"

        if area:
            poi_data["m5"]["trigger_area"] = area
            poi_data["m5"]["type"] = ptype
            poi_data["m5"]["status"] = "wait sweep / wait MSS"

    try:
        from src.fvg_engine import get_nearest_fvg
        fvgs_m15 = storage.get_active_fvgs(symbol, "M15")
        if fvgs_m15:
            m15_bias = poi_data["m15"]["bias"]
            direction = None
            if m15_bias == "BEARISH":
                direction = "Bearish"
            elif m15_bias == "BULLISH":
                direction = "Bullish"
            last_price = m15[-1]['close'] if m15 else 0
            nearest_fvg = get_nearest_fvg(last_price, fvgs_m15, direction)

            if nearest_fvg:
                poi_data["m15"]["poi"] = f"{
                    nearest_fvg['low']:.2f} - {
                    nearest_fvg['high']:.2f}"
                poi_data["m15"]["type"] = f"{nearest_fvg['direction']} FVG"
                poi_data["m15"]["fvg_status"] = nearest_fvg['status']
    except Exception as e:
        import logging
        logging.getLogger("POI").error(f"Failed to integrate FVG: {e}")

    return poi_data


def format_poi_map(poi_data):
    if poi_data['m15'].get('poi') == "Data belum cukup" and poi_data['h1'].get(
            'main_poi') == "Data belum cukup":
        return "NO POI VALID\n"

    bias = poi_data['m15'].get('bias', 'MIXED')
    h1_type = poi_data['h1'].get('type', 'N/A')

    if bias == 'BEARISH':
        prio = "WAIT SELL"
    elif bias == 'BULLISH':
        prio = "WAIT BUY"
    else:
        prio = "WAIT"

    return (
        f"M15 Bias: {bias}\n"
        f"Prioritas: {prio}\n\n"
        f"POI utama: {poi_data['h1']['main_poi']}\n"
        f"Type: {h1_type}\n"
        f"Alasan: {poi_data['h1'].get('reason', 'N/A')}\n"
    )


def generate_poi_action(poi_data, current_price):
    try:
        area_str = poi_data['m5'].get('trigger_area', 'N/A')
        if area_str == 'Data belum cukup' or area_str == 'N/A':
            area_str = poi_data['h1'].get('main_poi', 'N/A')

        if area_str == 'Data belum cukup' or area_str == 'N/A':
            return (
                "Action:\n"
                "- Status: WAIT\n"
                "- Area pantau: N/A\n"
                "- Entry valid jika: N/A\n"
                "- Invalid jika: N/A"
            )

        parts = area_str.replace(' / ', ' - ').split(' - ')
        low = float(parts[0])
        high = float(parts[1]) if len(parts) > 1 else low
        if low > high:
            low, high = high, low

        bias = poi_data['m15'].get('bias', 'MIXED')

        status = "WAIT"
        valid_entry = ""
        dont_entry = "Jangan entry di tengah range tanpa konfirmasi."

        if bias == 'BEARISH':
            valid_entry = f"Harga retest {high} lalu M5 reject / MSS bearish."
            if current_price > high + 5:
                status = "NO TRADE"
                dont_entry = "Harga sudah terlalu jauh di atas POI."
            elif current_price >= low - 2:
                status = "WATCH POI"
            else:
                status = "WAIT SELL"
        elif bias == 'BULLISH':
            valid_entry = f"Harga sweep {low} lalu M5 reject / MSS bullish."
            if current_price < low - 5:
                status = "NO TRADE"
                dont_entry = "Harga sudah terlalu jauh di bawah POI."
            elif current_price <= high + 2:
                status = "WATCH POI"
            else:
                status = "WAIT BUY"
        else:
            valid_entry = "Tunggu struktur jelas."

        if poi_data['m5'].get('status') != "wait sweep / wait MSS":
            if status == "WATCH POI":
                status = "ENTRY POSSIBLE"

        action_text = (
            "Action:\n"
            f"- Status: {status}\n"
            f"- Area pantau: {low} - {high}\n"
            f"- Entry valid jika: {valid_entry}\n"
            f"- Jangan entry jika: {dont_entry}\n"
            f"- Invalid jika: M15 close kuat melewati area."
        )
        return action_text
    except Exception as e:
        return f"Action:\n- Status: WAIT\n- Error generating action: {str(e)}"
