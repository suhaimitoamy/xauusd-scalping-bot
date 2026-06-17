import time
from datetime import datetime, timezone
import logging

try:
    from src.fvg_engine import detect_fvgs
except ImportError:
    detect_fvgs = None

try:
    from src.telegram_notifier import send_telegram_message, telegram_is_configured
except ImportError:
    send_telegram_message = None
    def telegram_is_configured(): return False

try:
    from src.candle_sync import sync_closed_higher_timeframes_from_m5, canonical_time
except ImportError:
    sync_closed_higher_timeframes_from_m5 = None
    canonical_time = None

logger = logging.getLogger("CandleBuilder")


class Candle:
    def __init__(self, symbol, timeframe, open_time):
        self.symbol = symbol
        self.timeframe = timeframe
        self.open_time = open_time
        self.close_time = None
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.volume_tick = 0
        self.is_closed = False

    def update(self, price):
        if self.open is None:
            self.open = price
            self.high = price
            self.low = price
            self.close = price
        else:
            self.high = max(self.high, price)
            self.low = min(self.low, price)
            self.close = price
        self.volume_tick += 1


class CandleBuilder:
    def __init__(self, storage, on_candle_closed=None, on_m5_closed=None):
        self.storage = storage
        self.on_candle_closed = on_candle_closed
        self.on_m5_closed = on_m5_closed

        self.tf_seconds = {
            'M1': 60,
            'M5': 300,
            'M15': 900,
            'H1': 3600,
            'H4': 14400,
            'D1': 86400
        }

        self.current_candles = {
            'M1': None,
            'M5': None,
            'M15': None,
            'H1': None,
            'H4': None,
            'D1': None
        }

    def _get_candle_open_time(self, timestamp, tf_seconds):
        return (timestamp // tf_seconds) * tf_seconds

    def _normalize_timestamp(self, timestamp):
        try:
            ts = float(timestamp)
        except (ValueError, TypeError):
            ts = time.time()

        # Some feeds return milliseconds; internal candle buckets must use seconds.
        if ts > 10_000_000_000:
            ts = ts / 1000.0
        return int(ts)

    def _hydrate_or_create_candle(self, symbol, tf, candle_open_ts):
        candle = Candle(symbol, tf, candle_open_ts)
        open_dt = datetime.fromtimestamp(candle_open_ts, timezone.utc).isoformat(timespec='seconds')
        legacy_open_dt = open_dt.replace('T', ' ').replace('+00:00', '')

        try:
            rows = self.storage.fetchall(
                """
                SELECT * FROM candles
                WHERE symbol=? AND timeframe=? AND open_time IN (?, ?)
                ORDER BY id DESC LIMIT 1
                """,
                (symbol, tf, open_dt, legacy_open_dt)
            )
        except Exception:
            rows = []

        if rows and int(rows[0].get('is_closed') or 0) == 0:
            row = rows[0]
            try:
                candle.open = float(row.get('open'))
                candle.high = float(row.get('high'))
                candle.low = float(row.get('low'))
                candle.close = float(row.get('close'))
                candle.volume_tick = int(row.get('volume_tick') or 0)
                candle.close_time = None
                candle.is_closed = False
            except Exception:
                pass

        return candle

    def _sync_htf_from_m5(self, symbol):
        if not sync_closed_higher_timeframes_from_m5:
            return
        result = sync_closed_higher_timeframes_from_m5(self.storage, symbol)
        if result.get('ok'):
            saved = result.get('saved') or {}
            logger.info(
                "HTF resync from M5 closed candles: "
                f"M15={saved.get('M15', 0)} H1={saved.get('H1', 0)} H4={saved.get('H4', 0)}"
            )
        else:
            logger.warning(f"HTF resync skipped: {result.get('error')}")

    def process_tick(self, symbol, price, timestamp, raw_data):
        ts = self._normalize_timestamp(timestamp)

        dt_utc = datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec='seconds')
        dt_local = datetime.fromtimestamp(ts).isoformat(timespec='seconds')

        import os
        if os.environ.get('DRY_RUN') != 'true':
            self.storage.save_tick(symbol, dt_utc, dt_local, price, raw_data)

        for tf, seconds in self.tf_seconds.items():
            candle_open_ts = self._get_candle_open_time(ts, seconds)

            candle = self.current_candles[tf]

            if candle and candle.open_time != candle_open_ts:
                # Close the old candle
                candle.is_closed = True
                candle.close_time = candle.open_time + seconds - 1

                # M15/H1/H4 closed rows must come from closed M5 aggregation,
                # not from a direct tick fallback candle that may have started mid-bucket.
                if tf in ['M15', 'H1', 'H4']:
                    logger.info(f"Skip direct {tf} closed save; HTF DB rows are rebuilt from closed M5.")
                else:
                    self._save_candle(candle)

                if tf == 'M5':
                    try:
                        self._sync_htf_from_m5(symbol)
                    except Exception as e:
                        logger.error(f"Error syncing HTF candles from closed M5: {e}")

                if tf in ['M5', 'M15', 'H1']:
                    try:
                        from src.fvg_engine import detect_fvgs
                        from src.telegram_notifier import send_telegram_message, telegram_is_configured
                        candles_for_fvg = self.storage.get_recent_candles(
                            symbol, tf, 5)
                        if candles_for_fvg:
                            new_fvgs = detect_fvgs(candles_for_fvg, tf)
                            for fvg in new_fvgs:
                                self.storage.upsert_fvg({
                                    'symbol': symbol,
                                    'timeframe': tf,
                                    'direction': fvg['direction'],
                                    'low': fvg['low'],
                                    'high': fvg['high'],
                                    'mid': fvg['mid'],
                                    'status': 'UNFILLED',
                                    'strength': 10,
                                    'source_candle_time': fvg['source_candle_time'],
                                    'raw_json': {}
                                })
                                if tf in ['M15',
                                          'H1'] and telegram_is_configured():
                                    msg = (
                                        f"📍 XAUUSD FVG DETECTED\n"
                                        f"TF: {tf}\n"
                                        f"Type: {fvg['direction']} FVG\n"
                                        f"Area: {fvg['low']:.2f} - {fvg['high']:.2f}\n"
                                        f"Status: UNFILLED\n"
                                        f"Action: tunggu retest + rejection\n"
                                        f"Source: RULE ENGINE"
                                    )
                                    send_telegram_message(msg)
                    except Exception as e:
                        logger.error(
                            f"Error in FVG detection on {tf} close: {e}")

                    # --- CONFLUENCE AGENTS WIRING ---
                    try:
                        candles_for_conf = self.storage.get_recent_candles(
                            symbol, tf, 20)
                        if candles_for_conf and len(candles_for_conf) >= 10:
                            # 1. OB Agent
                            from src.ob_engine import OrderBlockEngine
                            ob_engine = OrderBlockEngine(self.storage)
                            new_obs = ob_engine.detect_order_blocks(
                                tf, candles_for_conf)
                            for ob in new_obs:
                                ob_engine.save_order_block(ob)

                            # 2. SD Agent
                            from src.sd_engine import SupplyDemandEngine
                            sd_engine = SupplyDemandEngine(self.storage)
                            new_zones = sd_engine.detect_zones(
                                symbol, tf, candles_for_conf)
                            if new_zones:
                                sd_engine.save_zones(new_zones)

                            # 3. Liquidity Agent
                            from src.liquidity_engine import LiquidityEngine
                            liq_engine = LiquidityEngine(self.storage)
                            new_pools = liq_engine.detect_pools(
                                symbol, tf, candles_for_conf)
                            if new_pools:
                                liq_engine.save_pools(new_pools)

                            # 4. OTE Agent
                            from src.ote_engine import OTEEngine
                            ote_engine = OTEEngine(self.storage)
                            new_otes = ote_engine.detect_ote(
                                candles_for_conf, tf)
                            if new_otes:
                                for ote in new_otes:
                                    ote_engine.save_ote_zone(ote)
                    except Exception as e:
                        logger.error(
                            f"Error in Confluence Agents detection on {tf} close: {e}")

                if self.on_candle_closed:
                    try:
                        self.on_candle_closed(candle)
                    except Exception as e:
                        logger.error(
                            f"Error in on_candle_closed callback: {e}")

                if tf == 'M5' and self.on_m5_closed:
                    try:
                        self.on_m5_closed(candle)
                    except Exception as e:
                        logger.error(f"Error in on_m5_closed callback: {e}")

                # Create new candle
                self.current_candles[tf] = self._hydrate_or_create_candle(symbol, tf, candle_open_ts)
                self.current_candles[tf].update(price)
            elif not candle:
                # Initialize new candle
                self.current_candles[tf] = self._hydrate_or_create_candle(symbol, tf, candle_open_ts)
                self.current_candles[tf].update(price)
            else:
                # Update existing candle
                candle.update(price)

            # Save the running lower-timeframe candle state.
            # HTF closed rows are rebuilt from closed M5; avoid trusting direct HTF fallback rows.
            if self.current_candles[tf] and tf not in ['M15', 'H1', 'H4']:
                self._save_candle(self.current_candles[tf])

    def _save_candle(self, candle):
        open_dt = datetime.fromtimestamp(
            candle.open_time, timezone.utc).isoformat(timespec='seconds')
        close_dt = None
        if candle.close_time:
            close_dt = datetime.fromtimestamp(
                candle.close_time, timezone.utc).isoformat(timespec='seconds')

        self.storage.save_candle(
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            open_time=open_dt,
            close_time=close_dt,
            open_p=candle.open,
            high_p=candle.high,
            low_p=candle.low,
            close_p=candle.close,
            volume_tick=candle.volume_tick,
            is_closed=candle.is_closed
        )
