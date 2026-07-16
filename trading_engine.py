# trading_engine.py
import upstox_client
from config import ACCESS_TOKEN, DEBUG_MODE, LOT_SIZE, BREAKOUT_WINDOW, TRAILING_SL_TRIGGER, TRAILING_SL_DISTANCE, MAX_TRADES_PER_DAY
from datetime import datetime
import pytz
import csv
import os

IST = pytz.timezone('Asia/Kolkata')

class TradingEngine:
    def __init__(self):
        self.positions = {'CE': None, 'PE': None}  # {symbol: {'entry_price': float, 'high_price': float, 'quantity': int, 'order_id': str}}
        self.red_candle_high = {'CE': None, 'PE': None}  # {symbol: {'high': float, 'candle_index': int}}
        self.trade_count = 0
        self.trade_log_file = f"trade_log_{datetime.now(IST).strftime('%Y%m%d')}.csv"
        self._init_log()

    def _init_log(self):
        if not os.path.exists(self.trade_log_file):
            with open(self.trade_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Symbol', 'Action', 'Price', 'Quantity', 'OrderID', 'P&L'])

    def _log_trade(self, symbol, action, price, quantity, order_id, pnl=0):
        with open(self.trade_log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"), symbol, action, price, quantity, order_id, pnl])

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def place_order(self, instrument_key, symbol, price, side='buy'):
        if DEBUG_MODE:
            print(f"[{self.now()}] 🟢 [DEBUG] Simulated {side} order: {symbol} @ ₹{price:.2f}, Qty: {LOT_SIZE}")
            return f"simulated_{side}_{symbol}_{int(time.time())}"
        try:
            configuration = upstox_client.Configuration()
            configuration.access_token = ACCESS_TOKEN
            order_api = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
            order = upstox_client.OrderPlaceRequest(
                quantity=LOT_SIZE,
                product="I",
                validity="DAY",
                price=price,
                tag="scalper_bot",
                instrument_token=instrument_key,
                order_type="LIMIT",
                transaction_type=side.upper(),
                disclosed_quantity=0,
                trigger_price=0,
                is_amo=False
            )
            response = order_api.place_order(order, api_version="2.0")
            print(f"[{self.now()}] 🟢 Order placed: {side} {symbol} @ ₹{price:.2f}, Order ID: {response.data.order_id}")
            self._log_trade(symbol, side, price, LOT_SIZE, response.data.order_id)
            return response.data.order_id
        except Exception as e:
            print(f"[{self.now()}] ❌ Order placement failed: {e}")
            return None

    def process_candle(self, candle_builder):
        if self.trade_count >= MAX_TRADES_PER_DAY:
            return
        symbol = candle_builder.symbol
        symbol_type = 'CE' if 'CE' in symbol else 'PE'
        candles = candle_builder.candles
        current_candle = candle_builder.current_candle
        if not candles or not current_candle:
            return
        last_candle = candles[-1]
        if last_candle['close'] < last_candle['open'] and not self.red_candle_high[symbol_type]:
            self.red_candle_high[symbol_type] = {'high': last_candle['high'], 'candle_index': len(candles) - 1}
            print(f"[{self.now()}] 🔴 Red candle detected for {symbol}: High ₹{last_candle['high']:.2f}")
        if self.red_candle_high[symbol_type]:
            candles_since_red = len(candles) - 1 - self.red_candle_high[symbol_type]['candle_index']
            if candles_since_red <= BREAKOUT_WINDOW and current_candle['close'] > self.red_candle_high[symbol_type]['high'] and not self.positions[symbol_type]:
                print(f"[{self.now()}] 🚀 Breakout detected for {symbol}: ₹{current_candle['close']:.2f} > ₹{self.red_candle_high[symbol_type]['high']:.2f}")
                order_id = self.place_order(candle_builder.key, symbol, current_candle['close'], 'buy')
                if order_id:
                    self.positions[symbol_type] = {
                        'entry_price': current_candle['close'],
                        'high_price': current_candle['close'],
                        'quantity': LOT_SIZE,
                        'order_id': order_id
                    }
                    self.trade_count += 1
                    self.red_candle_high[symbol_type] = None
            elif candles_since_red > BREAKOUT_WINDOW:
                self.red_candle_high[symbol_type] = None
        if self.positions[symbol_type]:
            self.positions[symbol_type]['high_price'] = max(self.positions[symbol_type]['high_price'], current_candle['close'])
            current_profit = current_candle['close'] - self.positions[symbol_type]['entry_price']
            if current_profit >= TRAILING_SL_TRIGGER:
                trail_price = self.positions[symbol_type]['high_price'] - TRAILING_SL_DISTANCE
                if current_candle['close'] <= trail_price:
                    print(f"[{self.now()}] 🛑 Trailing stop hit for {symbol}: ₹{current_candle['close']:.2f} <= ₹{trail_price:.2f}")
                    order_id = self.place_order(candle_builder.key, symbol, current_candle['close'], 'sell')
                    if order_id:
                        pnl = (current_candle['close'] - self.positions[symbol_type]['entry_price']) * LOT_SIZE
                        self._log_trade(symbol, 'sell', current_candle['close'], LOT_SIZE, order_id, pnl)
                        self.positions[symbol_type] = None