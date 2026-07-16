import upstox_client
from config import (ACCESS_TOKEN, MARKET_START, MARKET_END, STRATEGY_START, 
                    ENTRY_WINDOW_END, STOP_AFTER_FIRST_WIN, MAX_TRADES_PER_SIDE)
from datetime import datetime
import pytz
import time
from core.candle import CandleAggregator
from strategies.red_candle_high_break import RedCandleHighBreak
from core.position_manager import PositionManager
from core.trade_logger import TradeLogger

IST = pytz.timezone('Asia/Kolkata')

class DataStreamer:
    def __init__(self, session_name="day", instruments=None, ce_key=None, pe_key=None):
        self.session_name = session_name
        self.running = True
        self.streamer = None
        self.last_running_print = {}
        self.tick_count = {}
        self.last_candle_count = {}

        self.active_instruments = instruments if instruments else ['CE', 'PE']

        self.live_feed_server = getattr(self, 'live_feed_server', None)
        self.price_history = {}
        self.bot_manager = getattr(self, 'bot_manager', None)

        if not ce_key or not pe_key:
            raise ValueError("CE and PE keys must be provided")

        self.CE_KEY = ce_key
        self.CE_SYMBOL = ce_key
        self.PE_KEY = pe_key
        self.PE_SYMBOL = pe_key

        print(f"Using strikes: CE={self.CE_SYMBOL}, PE={self.PE_SYMBOL}")

        self.components = {}
        for inst in self.active_instruments:
            symbol = self.CE_SYMBOL if inst == 'CE' else self.PE_SYMBOL
            aggregator = CandleAggregator(symbol=symbol)
            aggregator.add_listener(lambda e, c, i=inst: self._on_candle_event(i, e, c))
            self.components[inst] = {
                'candle_aggregator': aggregator,
                'strategy': RedCandleHighBreak(),
                'position_manager': PositionManager(),
                'trade_logger': TradeLogger(session_name=session_name, symbol=symbol),
                'trades_taken': 0,
                'can_trade': True,
                'symbol': symbol,
            }
            self.last_running_print[inst] = 0
            self.tick_count[inst] = 0
            self.last_candle_count[inst] = 0
            self.price_history[inst] = []

        print(f"Trading: {', '.join(self.active_instruments)}")

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def is_market_open(self):
        current_time = datetime.now(IST).strftime("%H:%M")
        return MARKET_START <= current_time <= MARKET_END
    
    def is_entry_window_open(self):
        current_time = datetime.now(IST).strftime("%H:%M")
        return STRATEGY_START <= current_time <= ENTRY_WINDOW_END

    def _on_candle_event(self, inst_type, event_type, candle):
        if self.live_feed_server:
            msg = {"type": event_type, "instrument": inst_type, "candle": candle}
            self.live_feed_server.broadcast_sync(msg)

    def _broadcast_tick(self, inst_type, ltp, timestamp):
        if self.live_feed_server:
            comp = self.components[inst_type]
            pm = comp['position_manager']
            msg = {
                "type": "tick",
                "instrument": inst_type,
                "ltp": ltp,
                "timestamp": timestamp.strftime("%H:%M:%S.%f")[:-3],
                "sl": pm.current_sl if pm.is_in_position() else None,
                "pnl": pm.get_unrealized_pnl(ltp) if pm.is_in_position() else None,
            }
            self.live_feed_server.broadcast_sync(msg)

    def exit_position(self, inst_type, exit_price, exit_time, exit_reason):
        comp = self.components[inst_type]
        trade_summary = comp['position_manager'].close_position(exit_price, exit_time)
        if not trade_summary:
            return
        
        comp['trade_logger'].log_exit(
            symbol=comp['symbol'],
            exit_price=exit_price,
            stop_loss=trade_summary['sl_final'],
            exit_time=exit_time,
            exit_reason=exit_reason,
            pnl=trade_summary['pnl']
        )
        
        comp['strategy'].reset()
        
        print(f"[{inst_type}] EXIT at {exit_price:.2f} | P&L: {trade_summary['pnl']:.2f} | Reason: {exit_reason}")
        
        if self.live_feed_server:
            self.live_feed_server.broadcast_sync({
                "type": "trade",
                "instrument": inst_type,
                "action": "exit",
                "price": exit_price,
                "timestamp": exit_time.isoformat(),
                "pnl": trade_summary['pnl'],
                "reason": exit_reason,
            })

        if trade_summary['pnl'] > 0:
            if STOP_AFTER_FIRST_WIN:
                comp['can_trade'] = False
                print(f"[{inst_type}] First win achieved - No more trades today")
        else:
            if comp['trades_taken'] >= MAX_TRADES_PER_SIDE:
                comp['can_trade'] = False
                print(f"[{inst_type}] Max trades reached - No more trades today")

    def process_tick(self, inst_type, ltp, timestamp):
        comp = self.components[inst_type]
        self.tick_count[inst_type] += 1
        
        candle_history = comp['candle_aggregator'].get_candle_history()
        
        if comp['position_manager'].is_in_position():
            if comp['position_manager'].check_exit(ltp) and not comp.get('_exiting', False):
                comp['_exiting'] = True
                self.exit_position(inst_type, ltp, timestamp, "Trailing SL Hit")
                comp['_exiting'] = False
                return
            
            sl_moved, new_sl = comp['position_manager'].update_trailing_sl(ltp)
            if sl_moved:
                print(f"[{inst_type}] SL moved to {new_sl:.2f} (LTP: {ltp:.2f})")
        
        elif comp['can_trade'] and self.is_entry_window_open():
            entry_signal = comp['strategy'].check_entry(ltp, candle_history)
            
            if entry_signal and entry_signal['enter']:
                comp['position_manager'].open_position(
                    entry_price=entry_signal['entry_price'],
                    entry_time=timestamp,
                    symbol=comp['symbol']
                )
                
                comp['trade_logger'].log_entry(
                    symbol=comp['symbol'],
                    entry_price=entry_signal['entry_price'],
                    stop_loss=entry_signal['stop_loss'],
                    entry_time=timestamp
                )
                
                comp['trades_taken'] += 1
                print(f"[{inst_type}] ENTRY at {entry_signal['entry_price']:.2f} | SL: {entry_signal['stop_loss']:.2f}")

                if self.live_feed_server:
                    self.live_feed_server.broadcast_sync({
                        "type": "trade",
                        "instrument": inst_type,
                        "action": "entry",
                        "price": entry_signal['entry_price'],
                        "timestamp": timestamp.isoformat(),
                        "sl": entry_signal['stop_loss'],
                    })

        if comp['position_manager'].is_in_position():
            self.price_history[inst_type].append((timestamp, ltp))
            if len(self.price_history[inst_type]) > 1000:
                self.price_history[inst_type] = self.price_history[inst_type][-1000:]

    def process_ohlc_candles(self, inst_type, ohlc_list):
        comp = self.components[inst_type]
        
        i1_candles = [c for c in ohlc_list if c.get('interval') == 'I1']
        i1_candles.sort(key=lambda c: int(c.get('ts', 0)), reverse=True)
        
        for candle_data in i1_candles[:2]:
            ts_ms = int(candle_data.get('ts', 0))
            candle_ts = datetime.fromtimestamp(ts_ms / 1000, IST)
            
            open_price = float(candle_data.get('open', 0))
            high_price = float(candle_data.get('high', 0))
            low_price = float(candle_data.get('low', 0))
            close_price = float(candle_data.get('close', 0))
            
            is_new = comp['candle_aggregator'].update_from_ohlc(
                timestamp=candle_ts,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price
            )
            
            if is_new:
                comp['strategy'].on_new_candle_closed()

    def on_message(self, message):
        try:
            if not hasattr(self, '_dict_feed_count'):
                self._dict_feed_count = 0
                self._first_feed_logged = False
            
            if isinstance(message, dict) and 'marketInfo' in message:
                return
            
            if isinstance(message, dict) and 'feeds' in message:
                self._dict_feed_count += 1
                
                if not self._first_feed_logged:
                    print(f"Live data streaming started")
                    self._first_feed_logged = True
                
                feeds = message['feeds']
                
                for instrument_key, feed_data in feeds.items():
                    if instrument_key == self.CE_KEY and 'CE' in self.active_instruments:
                        inst_type = 'CE'
                    elif instrument_key == self.PE_KEY and 'PE' in self.active_instruments:
                        inst_type = 'PE'
                    else:
                        continue
                    
                    ltp = None
                    timestamp = None
                    ohlc_list = []
                    
                    if isinstance(feed_data, dict):
                        if 'fullFeed' in feed_data:
                            full_feed = feed_data['fullFeed']
                            if isinstance(full_feed, dict) and 'marketFF' in full_feed:
                                market_ff = full_feed['marketFF']
                                if isinstance(market_ff, dict):
                                    if 'ltpc' in market_ff:
                                        ltpc_data = market_ff['ltpc']
                                        if isinstance(ltpc_data, dict):
                                            ltp = ltpc_data.get('ltp')
                                            ltt = ltpc_data.get('ltt', 0)
                                            timestamp = datetime.fromtimestamp(int(ltt) / 1000, IST) if ltt else datetime.now(IST)
                                    
                                    if 'marketOHLC' in market_ff:
                                        market_ohlc = market_ff['marketOHLC']
                                        if isinstance(market_ohlc, dict) and 'ohlc' in market_ohlc:
                                            ohlc_list = market_ohlc['ohlc']
                        
                        elif 'ltpc' in feed_data:
                            ltpc_data = feed_data['ltpc']
                            if isinstance(ltpc_data, dict):
                                ltp = ltpc_data.get('ltp')
                                ltt = ltpc_data.get('ltt', 0)
                                timestamp = datetime.fromtimestamp(int(ltt) / 1000, IST) if ltt else datetime.now(IST)
                    
                    if ltp is None:
                        continue
                    
                    ltp = float(ltp)
                    if timestamp is None:
                        timestamp = datetime.now(IST)
                    
                    if ohlc_list:
                        self.process_ohlc_candles(inst_type, ohlc_list)
                    
                    self.process_tick(inst_type, ltp, timestamp)
                
                return
            
            if isinstance(message, dict):
                return
            
            if isinstance(message, bytes):
                if not hasattr(self, '_binary_count'):
                    self._binary_count = 0
                
                self._binary_count += 1
                
                if self._binary_count == 1:
                    print(f"Live data streaming started (binary mode)")
                
                try:
                    from upstox.MarketDataFeedV3_pb2 import FeedResponse
                    feed_response = FeedResponse()
                    feed_response.ParseFromString(message)
                    
                    if not feed_response.feeds:
                        return
                    
                    for instrument_key, feed_data in feed_response.feeds.items():
                        if instrument_key == self.CE_KEY and 'CE' in self.active_instruments:
                            inst_type = 'CE'
                        elif instrument_key == self.PE_KEY and 'PE' in self.active_instruments:
                            inst_type = 'PE'
                        else:
                            continue
                        
                        ltp = None
                        timestamp = None
                        
                        if feed_data.HasField('fullFeed'):
                            full_feed = feed_data.fullFeed
                            if full_feed.HasField('marketFF'):
                                market_ff = full_feed.marketFF
                                if market_ff.HasField('ltpc'):
                                    ltpc = market_ff.ltpc
                                    ltp = float(ltpc.ltp)
                                    timestamp = datetime.fromtimestamp(ltpc.ltt / 1000, IST) if ltpc.ltt else datetime.now(IST)
                                
                                if market_ff.HasField('marketOHLC'):
                                    market_ohlc = market_ff.marketOHLC
                                    ohlc_list = []
                                    for ohlc_data in market_ohlc.ohlc:
                                        if ohlc_data.interval == "I1":
                                            ohlc_list.append({
                                                'interval': 'I1',
                                                'ts': ohlc_data.ts,
                                                'open': ohlc_data.open,
                                                'high': ohlc_data.high,
                                                'low': ohlc_data.low,
                                                'close': ohlc_data.close
                                            })
                                    if ohlc_list:
                                        self.process_ohlc_candles(inst_type, ohlc_list)
                        
                        elif feed_data.HasField('ltpc'):
                            ltpc = feed_data.ltpc
                            ltp = float(ltpc.ltp)
                            timestamp = datetime.fromtimestamp(ltpc.ltt / 1000, IST) if ltpc.ltt else datetime.now(IST)
                        
                        if ltp is None:
                            continue
                        
                        self.process_tick(inst_type, ltp, timestamp)
                    
                    return
                    
                except Exception as e:
                    print(f"Protobuf decode error: {e}")
                    return
                
        except Exception as e:
            print(f"Error processing message: {e}")

    def on_open(self):
        print(f"WebSocket connected")
        time.sleep(2)
        
        keys_to_subscribe = []
        if 'CE' in self.active_instruments:
            keys_to_subscribe.append(self.CE_KEY)
        if 'PE' in self.active_instruments:
            keys_to_subscribe.append(self.PE_KEY)
        
        try:
            self.streamer.subscribe(keys_to_subscribe, "full")
            print(f"Subscribed to instruments")
        except Exception as e:
            print(f"Subscription error: {e}")

    def on_error(self, error):
        print(f"WebSocket error: {error}")

    def on_close(self, *args):
        print(f"WebSocket closed")
        self.running = False

    def run(self):
        configuration = upstox_client.Configuration()
        configuration.access_token = ACCESS_TOKEN
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.streamer = upstox_client.MarketDataStreamerV3(
                    upstox_client.ApiClient(configuration)
                )
                
                self.streamer.on("open", self.on_open)
                self.streamer.on("message", self.on_message)
                self.streamer.on("error", self.on_error)
                self.streamer.on("close", self.on_close)
                
                print(f"Connecting to market data...")
                self.streamer.connect()
                
                while self.running:
                    time.sleep(1)
                return
                
            except Exception as e:
                print(f"Connection failed: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(f"Max retries reached")
                    for inst in self.active_instruments:
                        self.components[inst]['trade_logger'].close()
                    raise

    def close(self):
        if self.streamer:
            self.streamer.disconnect()
        for inst in self.active_instruments:
            self.components[inst]['trade_logger'].close()
