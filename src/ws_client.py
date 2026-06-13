import websocket
import json
import yaml
import threading
import logging
import time
import os
from dotenv import load_dotenv


class WSClient:
    def __init__(self, config_path='config.yaml', on_tick_callback=None):
        self.config_path = config_path
        self.on_tick_callback = on_tick_callback

        load_dotenv()
        self.api_key = os.getenv("TWELVE_API_KEY")

        self.symbol = self._load_symbol()
        self.ws = None
        self.thread = None
        self.logger = logging.getLogger("WSClient")
        self.is_running = False

    def _load_symbol(self):
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config.get('symbol', 'XAU/USD')
        except Exception as e:
            self.logger.warning(f"Failed to load symbol from config, defaulting to XAU/USD: {e}")
            return 'XAU/USD'

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get('event') == 'price':
                symbol = data.get('symbol')
                price = float(data.get('price'))
                timestamp = data.get('timestamp')

                if self.on_tick_callback:
                    self.on_tick_callback(symbol, price, timestamp, data)
            elif data.get('status') == 'error':
                self.logger.error(f"WebSocket received error message: {data}")
            else:
                self.logger.debug(f"WebSocket received: {data}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def on_error(self, ws, error):
        err_str = str(error)
        if '103' in err_str or 'No address associated with hostname' in err_str or 'Connection refused' in err_str:
            self.logger.warning("WebSocket disconnected, retrying...")
        else:
            self.logger.error(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.logger.info("WebSocket Closed")
        if self.is_running:
            self.logger.info("Attempting to reconnect in 5 seconds...")
            time.sleep(5)
            self._connect()

    def on_open(self, ws):
        self.logger.info(f"WebSocket Opened. Subscribing to {self.symbol}...")
        subscribe_msg = {
            "action": "subscribe",
            "params": {
                "symbols": self.symbol
            }
        }
        ws.send(json.dumps(subscribe_msg))

    def _connect(self):
        url = f"wss://ws.twelvedata.com/v1/quotes/price?apikey={self.api_key}"
        self.ws = websocket.WebSocketApp(url,
                                         on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.ws.run_forever()

    def start(self):
        if not self.api_key:
            self.logger.error(
                "ERROR: TWELVE_API_KEY is empty in .env! Cannot connect to Twelve Data WS.")
            self.logger.error(
                "Please add your TWELVE_API_KEY to the .env file.")
            # Do not crash, just don't start the websocket thread
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._connect)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.ws:
            self.ws.close()
