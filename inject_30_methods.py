import re

with open("src/market_brain.py", "r") as f:
    content = f.read()

new_methods_code = """
    def _aggressive_30_methods(self, ctx: Dict[str, Any]) -> Optional[Tuple[str, str, str, float]]:
        price = ctx.get('price', 0)
        close = ctx.get('last_close', 0)
        open_ = ctx.get('last_open', 0)
        high = ctx.get('last_high', 0)
        low = ctx.get('last_low', 0)
        momentum = ctx.get('momentum')
        atr = ctx.get('atr', 2.0)
        m15_bias = ctx.get('m15_bias')
        h1_bias = ctx.get('h1_bias')
        fvgs = ctx.get('fvgs', [])
        obs = ctx.get('obs', [])
        struct = ctx.get('structure', {})
        sweep_type = struct.get('sweep_type')
        candles = ctx.get('candles', [])
        
        if len(candles) < 2: return None
        
        body_top = max(open_, close)
        body_bottom = min(open_, close)
        body_size = max(body_top - body_bottom, 0.01)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        
        is_bullish_close = close > open_
        is_bearish_close = close < open_
        is_strong_bullish = is_bullish_close and body_size > atr * 0.8
        is_strong_bearish = is_bearish_close and body_size > atr * 0.8

        prev_c = candles[-2] if len(candles) >= 2 else None
        
        # CATEGORY 1: Turtle Soup & Liquidity Sweeps
        # 1-2. Micro Turtle Soup
        if sweep_type == 'bullish' and is_bullish_close and lower_wick > body_size * 1.2:
            return ('BUY', 'MICRO_TURTLE_SOUP: Sweep Low + Pinbar Rejection', 'METHOD_MICRO_TURTLE_SOUP_BUY', 86.0)
        if sweep_type == 'bearish' and is_bearish_close and upper_wick > body_size * 1.2:
            return ('SELL', 'MICRO_TURTLE_SOUP: Sweep High + Pinbar Rejection', 'METHOD_MICRO_TURTLE_SOUP_SELL', 86.0)

        # 3-4. H1 Sweep Scalp
        if ctx.get('h1_sweep_low') and is_strong_bullish and m15_bias == 'bullish':
            return ('BUY', 'H1_SWEEP_SCALP: H1 Low Swept + M15 Bullish Engulf', 'METHOD_H1_SWEEP_SCALP_BUY', 88.0)
        if ctx.get('h1_sweep_high') and is_strong_bearish and m15_bias == 'bearish':
            return ('SELL', 'H1_SWEEP_SCALP: H1 High Swept + M15 Bearish Engulf', 'METHOD_H1_SWEEP_SCALP_SELL', 88.0)

        # 5-6. Equal Highs/Lows Sweep
        if struct.get('eqh_sweep') and is_bearish_close and upper_wick > body_size:
            return ('SELL', 'EQUAL_HIGHS_SWEEP: Double Top Swept + Rejection', 'METHOD_EQUAL_HIGHS_SWEEP_SELL', 89.0)
        if struct.get('eql_sweep') and is_bullish_close and lower_wick > body_size:
            return ('BUY', 'EQUAL_LOWS_SWEEP: Double Bottom Swept + Rejection', 'METHOD_EQUAL_LOWS_SWEEP_BUY', 89.0)

        # 7-8. Asia Liquidity Run
        try:
            from datetime import datetime, timezone
            dt_str = ctx.get('timestamp') or ''
            if dt_str:
                dt = datetime.fromisoformat(dt_str)
                hour = dt.hour
            else:
                hour = datetime.now(timezone.utc).hour
            if hour in [7, 8, 9]: # London Open
                if sweep_type == 'bullish' and is_bullish_close:
                    return ('BUY', 'ASIA_LIQUIDITY_RUN: Asian Low Swept at London Open', 'METHOD_ASIA_LIQUIDITY_RUN_BUY', 88.5)
                if sweep_type == 'bearish' and is_bearish_close:
                    return ('SELL', 'ASIA_LIQUIDITY_RUN: Asian High Swept at London Open', 'METHOD_ASIA_LIQUIDITY_RUN_SELL', 88.5)
        except: pass

        # CATEGORY 2: ICT Order Blocks & FVG
        # 9-10. M5 FVG Instant Rebound
        for fvg in fvgs:
            if fvg['direction'] == 'Bullish' and low <= fvg['high'] and close > fvg['low']:
                if is_bullish_close and lower_wick > atr * 0.5:
                    return ('BUY', 'M5_FVG_INSTANT_REBOUND: Bullish FVG Tapped & Rejected', 'METHOD_M5_FVG_INSTANT_REBOUND_BUY', 87.5)
            if fvg['direction'] == 'Bearish' and high >= fvg['low'] and close < fvg['high']:
                if is_bearish_close and upper_wick > atr * 0.5:
                    return ('SELL', 'M5_FVG_INSTANT_REBOUND: Bearish FVG Tapped & Rejected', 'METHOD_M5_FVG_INSTANT_REBOUND_SELL', 87.5)
        
        # 11-12. Inversion FVG Momentum
        for fvg in fvgs:
            if fvg['direction'] == 'Bearish' and close > fvg['high'] and open_ <= fvg['high']:
                if is_strong_bullish and upper_wick < body_size * 0.5:
                    return ('BUY', 'IFVG_MOMENTUM: Bearish FVG broken upwards', 'METHOD_IFVG_MOMENTUM_BUY', 87.0)
            if fvg['direction'] == 'Bullish' and close < fvg['low'] and open_ >= fvg['low']:
                if is_strong_bearish and lower_wick < body_size * 0.5:
                    return ('SELL', 'IFVG_MOMENTUM: Bullish FVG broken downwards', 'METHOD_IFVG_MOMENTUM_SELL', 87.0)

        # 13-14. Breaker Block
        for ob in obs:
            ob_dir = str(ob.get('type') or ob.get('direction') or '').lower()
            if 'bull' in ob_dir and high >= float(ob.get('low', 0)) and close < float(ob.get('low', 0)): # Broken bull OB retest
                if is_bearish_close and upper_wick > body_size:
                    return ('SELL', 'BREAKER_BLOCK_SCALP: Broken Bullish OB Retested as Resistance', 'METHOD_BREAKER_BLOCK_SCALP_SELL', 88.0)
            if 'bear' in ob_dir and low <= float(ob.get('high', 0)) and close > float(ob.get('high', 0)): # Broken bear OB retest
                if is_bullish_close and lower_wick > body_size:
                    return ('BUY', 'BREAKER_BLOCK_SCALP: Broken Bearish OB Retested as Support', 'METHOD_BREAKER_BLOCK_SCALP_BUY', 88.0)

        # 15-16. Order Block Tap
        for ob in obs:
            ob_dir = str(ob.get('type') or ob.get('direction') or '').lower()
            ob_low, ob_high = float(ob.get('low', 0)), float(ob.get('high', 0))
            is_fresh = ob.get('touches', 0) == 0 or ob.get('fresh', True)
            if is_fresh:
                if 'bull' in ob_dir and low <= ob_high and close > ob_low:
                    if is_bullish_close and lower_wick > atr * 0.4:
                        return ('BUY', 'ORDER_BLOCK_TAP: First tap on fresh Bullish OB', 'METHOD_ORDER_BLOCK_TAP_BUY', 88.0)
                if 'bear' in ob_dir and high >= ob_low and close < ob_high:
                    if is_bearish_close and upper_wick > atr * 0.4:
                        return ('SELL', 'ORDER_BLOCK_TAP: First tap on fresh Bearish OB', 'METHOD_ORDER_BLOCK_TAP_SELL', 88.0)

        # CATEGORY 3: Momentum Ignition & Breakouts
        # 17-18. Momentum Marubozu
        if body_size > atr * 1.8 and upper_wick < atr * 0.2 and lower_wick < atr * 0.2:
            if is_bullish_close and ctx.get('break_bull'):
                return ('BUY', 'MOMENTUM_MARUBOZU: Giant Bullish breakout no wick', 'METHOD_MOMENTUM_MARUBOZU_BUY', 87.0)
            if is_bearish_close and ctx.get('break_bear'):
                return ('SELL', 'MOMENTUM_MARUBOZU: Giant Bearish breakout no wick', 'METHOD_MOMENTUM_MARUBOZU_SELL', 87.0)

        # 19-22. Session Open Breakout
        try:
            hour = datetime.now(timezone.utc).hour
            minute = datetime.now(timezone.utc).minute
            is_ny_open = (hour == 13) and minute <= 30
            is_london_open = (hour == 8) and minute <= 30
        except:
            is_ny_open = False
            is_london_open = False
            
        if is_ny_open:
            if ctx.get('break_bull') and is_strong_bullish: return ('BUY', 'NY_OPEN_BREAKOUT: NY Breakout Up', 'METHOD_NY_OPEN_BREAKOUT_BUY', 86.5)
            if ctx.get('break_bear') and is_strong_bearish: return ('SELL', 'NY_OPEN_BREAKOUT: NY Breakout Down', 'METHOD_NY_OPEN_BREAKOUT_SELL', 86.5)
        if is_london_open:
            if ctx.get('break_bull') and is_strong_bullish: return ('BUY', 'LONDON_OPEN_BREAKOUT: London Breakout Up', 'METHOD_LONDON_OPEN_BREAKOUT_BUY', 86.5)
            if ctx.get('break_bear') and is_strong_bearish: return ('SELL', 'LONDON_OPEN_BREAKOUT: London Breakout Down', 'METHOD_LONDON_OPEN_BREAKOUT_SELL', 86.5)

        # CATEGORY 4: Market Structure & BOS
        # 23-24. Shallow Pullback
        if m15_bias == 'bullish' and h1_bias == 'bullish' and prev_c:
            if prev_c['close'] < prev_c['open'] and is_strong_bullish and close > prev_c['high']:
                return ('BUY', 'SHALLOW_PULLBACK: Trend Bullish, quick red candle engulfed', 'METHOD_SHALLOW_PULLBACK_BUY', 88.0)
        if m15_bias == 'bearish' and h1_bias == 'bearish' and prev_c:
            if prev_c['close'] > prev_c['open'] and is_strong_bearish and close < prev_c['low']:
                return ('SELL', 'SHALLOW_PULLBACK: Trend Bearish, quick green candle engulfed', 'METHOD_SHALLOW_PULLBACK_SELL', 88.0)

        # 25-26. Continuation BOS
        if ctx.get('break_bull') and m15_bias == 'bullish' and is_bullish_close and lower_wick > atr * 0.5:
            return ('BUY', 'CONTINUATION_BOS: Bullish BOS confirmed with rejection', 'METHOD_CONTINUATION_BOS_BUY', 87.0)
        if ctx.get('break_bear') and m15_bias == 'bearish' and is_bearish_close and upper_wick > atr * 0.5:
            return ('SELL', 'CONTINUATION_BOS: Bearish BOS confirmed with rejection', 'METHOD_CONTINUATION_BOS_SELL', 87.0)

        # CATEGORY 5: Exhaustion & Mean Reversion
        # 27-28. Parabolic Exhaustion
        if not ctx.get('choppy'):
            # Simple check if price moved very fast
            if low < atr * 3.0 and is_bullish_close and lower_wick > body_size * 2.0 and lower_wick > atr * 1.5:
                return ('BUY', 'PARABOLIC_EXHAUSTION: Huge drop exhausted with massive wick', 'METHOD_PARABOLIC_EXHAUSTION_BUY', 85.0)
            if high > atr * 3.0 and is_bearish_close and upper_wick > body_size * 2.0 and upper_wick > atr * 1.5:
                return ('SELL', 'PARABOLIC_EXHAUSTION: Huge pump exhausted with massive wick', 'METHOD_PARABOLIC_EXHAUSTION_SELL', 85.0)

        # 29-30. News Spike Fade (Using ATR burst)
        if atr > 3.0 and body_size < atr * 0.3:
            if upper_wick > atr * 1.5 and is_bearish_close:
                return ('SELL', 'NEWS_SPIKE_FADE: Massive upper wick fade during volatility', 'METHOD_NEWS_SPIKE_FADE_SELL', 84.0)
            if lower_wick > atr * 1.5 and is_bullish_close:
                return ('BUY', 'NEWS_SPIKE_FADE: Massive lower wick fade during volatility', 'METHOD_NEWS_SPIKE_FADE_BUY', 84.0)

        return None
"""

if "_aggressive_30_methods" not in content:
    # Insert new method right before _decide
    content = content.replace("def _decide(self", new_methods_code + "\n    def _decide(self")
    
    # Hook it inside _decide
    hook = """
        # 4. Aggressive 30 Methods (Fase 2)
        aggro_match = self._aggressive_30_methods(ctx)
        if aggro_match:
            return aggro_match
"""
    content = content.replace("ag_match = self._antigravity_experimental_method(ctx)\n        if ag_match:\n            return ag_match", 
                              "ag_match = self._antigravity_experimental_method(ctx)\n        if ag_match:\n            return ag_match" + hook)

    with open("src/market_brain.py", "w") as f:
        f.write(content)
    print("Methods injected successfully!")
else:
    print("Methods already exist.")
