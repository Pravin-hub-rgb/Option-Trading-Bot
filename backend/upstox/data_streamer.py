import upstox_client
from datetime import datetime
import pytz
import time
from core.candle import CandleAggregator
from strategies.red_candle_high_break import RedCandleHighBreak
from core.position_manager import PositionManager
from core.trade_logger import TradeLogger
from settings_db import get_setting, get_as_dict

IST = pytz.timezone('Asia/Kolkata')

GAP_THRESHOLD_SECONDS = 5  # placeholder — derive from real tick-gap distribution
BREAKEVEN_BAND = 1.0  # |pnl| <= this is treated as breakeven (neither win nor loss), in points

def _classify_pnl(pnl):
    """Classify a realised P&L (in points) as 'win', 'loss' or 'breakeven'."""
    if pnl > BREAKEVEN_BAND:
        return 'win'
    if pnl < -BREAKEVEN_BAND:
        return 'loss'
    return 'breakeven'

class DataStreamer:
    def __init__(self, session_name="day", instruments=None, ce_key=None, pe_key=None,
                 live_feed_server=None, bot_manager=None, access_token=None,
                 ce_strike=None, pe_strike=None, prescan_keys=None):
        self.session_name = session_name
        self.running = True
        self._stop_requested = False
        self.streamer = None
        self.last_running_print = {}
        self.tick_count = {}
        self.last_candle_count = {}
        self.last_tick_time = {}

        self.active_instruments = instruments if instruments else ['CE', 'PE']
        self.live_feed_server = live_feed_server
        self.bot_manager = bot_manager
        self._access_token = access_token or get_setting("access_token") or ""

        self._prescan_keys = prescan_keys
        self._prescan_aggregators = {}

        if prescan_keys:
            self.CE_KEY = None
            self.PE_KEY = None
            self.CE_SYMBOL = None
            self.PE_SYMBOL = None
            self.CE_STRIKE = None
            self.PE_STRIKE = None
            self.components = {}
            for key in prescan_keys:
                agg = CandleAggregator(symbol=key)
                self._prescan_aggregators[key] = agg
            print(f"Pre-subscribe mode: {len(prescan_keys)} instruments loaded")
        else:
            if not ce_key or not pe_key:
                raise ValueError("CE and PE keys must be provided")

            self.CE_KEY = ce_key
            self.CE_SYMBOL = f"{ce_strike} CE" if ce_strike else ce_key
            self.PE_KEY = pe_key
            self.PE_SYMBOL = f"{pe_strike} PE" if pe_strike else pe_key
            self.CE_STRIKE = ce_strike
            self.PE_STRIKE = pe_strike

            print(f"Using strikes: CE={self.CE_SYMBOL}, PE={self.PE_SYMBOL}")

            s = self._settings = get_as_dict()

            self.components = {}
            for inst in self.active_instruments:
                symbol = self.CE_SYMBOL if inst == 'CE' else self.PE_SYMBOL
                aggregator = CandleAggregator(symbol=symbol)
                aggregator.add_listener(lambda e, c, i=inst: self._on_candle_event(i, e, c))
                self.components[inst] = {
                    'candle_aggregator': aggregator,
                    'strategy': RedCandleHighBreak(
                        max_wait_candles=s.get('max_wait_candles'),
                        allow_reference_shift=s.get('allow_reference_shift'),
                        initial_sl_points=s.get('initial_sl_points'),
                        label=inst,
                    ),
                    'position_manager': PositionManager(
                        initial_sl_points=s.get('initial_sl_points'),
                        trailing_trigger=s.get('trailing_trigger'),
                        trailing_step=s.get('trailing_step'),
                    ),
                    'trade_logger': TradeLogger(session_name=session_name, symbol=symbol),
                    'trades_taken': 0,
                    'trade_slot': 1,
                    'can_trade': True,
                    'symbol': symbol,
                }
                self.last_running_print[inst] = 0
                self.tick_count[inst] = 0
                self.last_candle_count[inst] = 0
                self.last_tick_time[inst] = None

            print(f"Trading: {', '.join(self.active_instruments)}")

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def is_market_open(self):
        current_time = datetime.now(IST).strftime("%H:%M")
        s = get_as_dict()
        return s.get('market_start', '09:15') <= current_time <= s.get('market_end', '15:30')
    
    def is_entry_window_open(self):
        current_time = datetime.now(IST).strftime("%H:%M")
        s = get_as_dict()
        return s.get('strategy_start', '09:15') <= current_time <= s.get('entry_window_end', '15:00')

    def _on_candle_event(self, inst_type, event_type, candle):
        if self.live_feed_server:
            msg = {"type": event_type, "instrument": inst_type, "candle": candle}
            self.live_feed_server.broadcast_sync(msg)

    def _broadcast_tick(self, inst_type, ltp, timestamp):
        comp = self.components[inst_type]
        pm = comp['position_manager']
        in_pos = pm.is_in_position()

        if in_pos and self.bot_manager:
            with self.bot_manager.lock:
                slot_key = f"trade{comp.get('trade_slot', 1)}"
                pos = self.bot_manager.positions[inst_type][slot_key]
                if pos and pos.get('state') == 'in_position':
                    pos['pnl'] = pm.get_unrealized_pnl(ltp)

        if self.live_feed_server:
            msg = {
                "type": "tick",
                "instrument": inst_type,
                "trade_slot": comp.get('trade_slot', 1),
                "ltp": ltp,
                "timestamp": timestamp.strftime("%H:%M:%S.%f")[:-3],
                "sl": pm.get_current_sl() if in_pos else None,
                "pnl": pm.get_unrealized_pnl(ltp) if in_pos else None,
                "entry": pm.position['entry_price'] if in_pos else None,
                "entry_time": pm.position['entry_time'].strftime("%H:%M:%S.%f")[:-3] if in_pos else None,
                "tp_levels": pm.get_tp_levels(current_ltp=ltp) if in_pos else [],
            }
            self.live_feed_server.broadcast_sync(msg)

    def _update_prescan_ohlc(self, instrument_key, ohlc_list, feed_time=None):
        agg = self._prescan_aggregators.get(instrument_key)
        if not agg:
            return
        i1_candles = [c for c in ohlc_list if c.get('interval') == 'I1']
        i1_candles.sort(key=lambda c: int(c.get('ts', 0)), reverse=True)
        for candle_data in i1_candles[:2]:
            ts_ms = int(candle_data.get('ts', 0))
            candle_ts = datetime.fromtimestamp(ts_ms / 1000, IST)
            open_price = float(candle_data.get('open', 0))
            high_price = float(candle_data.get('high', 0))
            low_price = float(candle_data.get('low', 0))
            close_price = float(candle_data.get('close', 0))
            agg.update_from_ohlc(
                timestamp=candle_ts,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                feed_time=feed_time
            )

    def finalize_selection(self, ce_key, pe_key, ce_strike=None, pe_strike=None, hold_minute=None):
        if not self._prescan_aggregators:
            print(f"[ERROR] finalize_selection called without prescan aggregators")
            return

        s = self._settings = get_as_dict()

        if hold_minute is None:
            hold_minute = datetime.now(IST).replace(second=0, microsecond=0)
        hold_minute = hold_minute.replace(second=0, microsecond=0)

        # Build all components in a local dict FIRST so the WS thread can never
        # observe a half-constructed component (the race that caused KeyError 'PE').
        new_components = {}
        for inst, key, strike in [('CE', ce_key, ce_strike), ('PE', pe_key, pe_strike)]:
            symbol = f"{strike} {inst}" if strike else key

            prescan_agg = self._prescan_aggregators.pop(key, None)
            if not prescan_agg:
                print(f"[WARN] No prescan aggregator for {key}, creating fresh")
                prescan_agg = CandleAggregator(symbol=symbol)
            else:
                prescan_agg.symbol = symbol

            prescan_agg.add_listener(lambda e, c, i=inst: self._on_candle_event(i, e, c))
            # Gate the 09:15 candle: strategy must not see it until REST confirms.
            prescan_agg.arm_hold(hold_minute)

            new_components[inst] = {
                'candle_aggregator': prescan_agg,
                'strategy': RedCandleHighBreak(
                    max_wait_candles=s.get('max_wait_candles'),
                    allow_reference_shift=s.get('allow_reference_shift'),
                    initial_sl_points=s.get('initial_sl_points'),
                    label=inst,
                ),
                'position_manager': PositionManager(
                    initial_sl_points=s.get('initial_sl_points'),
                    trailing_trigger=s.get('trailing_trigger'),
                    trailing_step=s.get('trailing_step'),
                ),
                'trade_logger': TradeLogger(session_name=self.session_name, symbol=symbol),
                'trades_taken': 0,
                'trade_slot': 1,
                'can_trade': True,
                'symbol': symbol,
            }

        # Atomic swap: publish all components at once.
        self.components = new_components

        for inst in self.active_instruments:
            if inst not in ('CE', 'PE'):
                continue
            self.last_running_print[inst] = 0
            self.tick_count[inst] = 0
            self.last_candle_count[inst] = 0
            self.last_tick_time[inst] = None

        # Keys/symbols published LAST so on_message routing only sees them once
        # self.components is fully built.
        self.CE_KEY = ce_key
        self.PE_KEY = pe_key
        self.CE_STRIKE = ce_strike
        self.PE_STRIKE = pe_strike
        self.CE_SYMBOL = f"{ce_strike} CE" if ce_strike else ce_key
        self.PE_SYMBOL = f"{pe_strike} PE" if pe_strike else pe_key

        remaining = list(self._prescan_aggregators.keys())
        self._prescan_aggregators.clear()
        self._prescan_keys = None  # So reconnect subscribes only to the 2 selected keys
        if remaining and self.streamer:
            try:
                self.streamer.unsubscribe(remaining)
                print(f"Unsubscribed {len(remaining)} prescan instruments")
            except Exception as e:
                print(f"[WARN] Unsubscribe failed: {e}")
        print(f"Finalized selection: CE={self.CE_SYMBOL}, PE={self.PE_SYMBOL} "
              f"(prescan aggregators injected, {hold_minute.strftime('%H:%M')} candle held for REST confirm)")

    def _commit_candle(self, inst_type, candle, source):
        comp = self.components.get(inst_type)
        if not comp:
            print(f"[ERROR] _commit_candle: no component for {inst_type}")
            return
        o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
        if h < o or l > o or h < c or l > c or h < l:
            print(f"[ERROR] {inst_type}: refusing to commit impossible candle "
                  f"O={o} H={h} L={l} C={c} ({source})")
            return
        candle['symbol'] = comp['symbol']
        if not comp['candle_aggregator'].commit_corrected_candle(candle):
            return
        color = 'RED' if o > c else 'GREEN'
        print(f"[{inst_type}] CANDLE {candle['timestamp'].strftime('%H:%M')} "
              f"O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f} {color} ({source})")
        comp['strategy'].on_new_candle_closed()

    def commit_confirmed_candle(self, inst_type, candle):
        """Called by the REST poller with the verified 09:15 candle."""
        self._commit_candle(inst_type, candle, "REST-confirmed 09:16:20")

    def commit_ws_fallback(self, inst_type):
        """Called by the REST poller when no confirmed candle is available;
        commits the WS candle that the gate parked (today's behavior)."""
        comp = self.components.get(inst_type)
        if not comp:
            print(f"[ERROR] commit_ws_fallback: no component for {inst_type}")
            return
        held = comp['candle_aggregator'].release_hold()
        if held is None:
            print(f"[ERROR] {inst_type}: held 09:15 candle was never received from WS "
                  f"before commit time — no reference set for this side")
            return
        self._commit_candle(inst_type, held, "WS fallback (REST unavailable)")

    def exit_position(self, inst_type, exit_price, exit_time, exit_reason):
        comp = self.components[inst_type]
        trade_summary = comp['position_manager'].close_position(exit_price, exit_time)
        if not trade_summary:
            return
        
        try:
            comp['trade_logger'].log_exit(
                symbol=comp['symbol'],
                exit_price=exit_price,
                stop_loss=trade_summary['sl_final'],
                exit_time=exit_time,
                exit_reason=exit_reason,
                pnl=trade_summary['pnl']
            )
        except Exception as e:
            print(f"[ERROR] exit_position: log_exit failed: {e}")
        
        comp['strategy'].reset()

        slot = comp['trade_slot']
        outcome = _classify_pnl(trade_summary['pnl'])
        state_map = {'win': 'exited_win', 'loss': 'exited_loss', 'breakeven': 'exited_breakeven'}
        if self.bot_manager:
            with self.bot_manager.lock:
                slot_key = f"trade{slot}"
                pos = self.bot_manager.positions[inst_type][slot_key]
                if pos:
                    pos['state'] = state_map[outcome]
                    pos['exit_price'] = exit_price
                    pos['exit_time'] = exit_time.strftime("%H:%M:%S.%f")[:-3]
                    pos['exit_reason'] = exit_reason
                    pos['pnl'] = trade_summary['pnl']
                    pos['duration_seconds'] = trade_summary['duration_seconds']

        print(f"[{inst_type}] EXIT at {exit_price:.2f} | P&L: {trade_summary['pnl']:.2f} "
              f"({outcome}) | Reason: {exit_reason}")
        
        if self.live_feed_server:
            self.live_feed_server.broadcast_sync({
                "type": "trade",
                "instrument": inst_type,
                "trade_slot": slot,
                "action": "exit",
                "price": exit_price,
                "timestamp": exit_time.strftime("%H:%M:%S.%f")[:-3],
                "pnl": trade_summary['pnl'],
                "reason": exit_reason,
                "outcome": outcome,
            })

        s = get_as_dict()
        if outcome == 'win':
            if s.get('stop_after_first_win', True):
                comp['can_trade'] = False
                print(f"[{inst_type}] First win achieved - No more trades today")
        else:
            if comp['trades_taken'] >= s.get('max_trades_per_side', 2):
                comp['can_trade'] = False
                print(f"[{inst_type}] Max trades reached - No more trades today")
            elif comp['can_trade']:
                comp['trade_slot'] = 2
                print(f"[{inst_type}] Moving to slot 2 for next trade")

    def process_tick(self, inst_type, ltp, timestamp):
        comp = self.components[inst_type]
        self.tick_count[inst_type] += 1
        
        prev_tick_time = self.last_tick_time.get(inst_type)
        self.last_tick_time[inst_type] = timestamp
        gap_seconds = (timestamp - prev_tick_time).total_seconds() if prev_tick_time else 0
        
        candle_history = comp['candle_aggregator'].get_candle_history()
        
        if comp['position_manager'].is_in_position():
            if comp['position_manager'].check_exit(ltp) and not comp.get('_exiting', False):
                comp['_exiting'] = True
                try:
                    is_gap = gap_seconds > GAP_THRESHOLD_SECONDS
                    if is_gap:
                        sl_price = comp['position_manager'].get_current_sl()
                        slippage = sl_price - ltp
                        reason = f"Trailing SL Hit — gap {gap_seconds:.0f}s, slippage {slippage:.2f}"
                        print(f"[{inst_type}] GAP EXIT: SL was {sl_price:.2f}, filled at {ltp:.2f} "
                              f"(slippage {slippage:.2f}) after {gap_seconds:.0f}s gap")
                    else:
                        reason = "Trailing SL Hit"
                    self.exit_position(inst_type, ltp, timestamp, reason)
                    self._broadcast_tick(inst_type, ltp, timestamp)
                finally:
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

                slot = comp['trade_slot']
                if self.bot_manager:
                    with self.bot_manager.lock:
                        self.bot_manager.positions[inst_type][f"trade{slot}"] = {
                            'state': 'in_position',
                            'instrument': inst_type,
                            'trade_slot': slot,
                            'entry_price': entry_signal['entry_price'],
                            'current_sl': entry_signal['stop_loss'],
                            'entry_time': timestamp.strftime("%H:%M:%S.%f")[:-3],
                        }

                print(f"[{inst_type}] ENTRY at {entry_signal['entry_price']:.2f} | SL: {entry_signal['stop_loss']:.2f} (slot {slot})")

                if self.live_feed_server:
                    self.live_feed_server.broadcast_sync({
                        "type": "trade",
                        "instrument": inst_type,
                        "trade_slot": slot,
                        "action": "entry",
                        "price": entry_signal['entry_price'],
                        "timestamp": timestamp.strftime("%H:%M:%S.%f")[:-3],
                        "sl": entry_signal['stop_loss'],
                    })

        self._broadcast_tick(inst_type, ltp, timestamp)

    def process_ohlc_candles(self, inst_type, ohlc_list, feed_time=None):
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
                close_price=close_price,
                feed_time=feed_time
            )
            
            if is_new:
                color = 'RED' if open_price > close_price else 'GREEN'
                print(f"[{inst_type}] CANDLE {candle_ts.strftime('%H:%M')} "
                      f"O={open_price:.2f} H={high_price:.2f} L={low_price:.2f} "
                      f"C={close_price:.2f} {color} (feed_time={feed_time.strftime('%H:%M:%S.%f')[:-3] if feed_time else 'N/A'})")
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
                    inst_type = None
                    is_prescan = self._prescan_aggregators and instrument_key in self._prescan_aggregators
                    
                    if self.components and instrument_key == self.CE_KEY and 'CE' in self.active_instruments:
                        inst_type = 'CE'
                    elif self.components and instrument_key == self.PE_KEY and 'PE' in self.active_instruments:
                        inst_type = 'PE'
                    elif not is_prescan:
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
                        if inst_type:
                            self.process_ohlc_candles(inst_type, ohlc_list, feed_time=timestamp)
                        elif is_prescan:
                            self._update_prescan_ohlc(instrument_key, ohlc_list, feed_time=timestamp)
                    
                    if inst_type:
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
                        inst_type = None
                        is_prescan = self._prescan_aggregators and instrument_key in self._prescan_aggregators
                        
                        if self.components and instrument_key == self.CE_KEY and 'CE' in self.active_instruments:
                            inst_type = 'CE'
                        elif self.components and instrument_key == self.PE_KEY and 'PE' in self.active_instruments:
                            inst_type = 'PE'
                        elif not is_prescan:
                            continue
                        
                        ltp = None
                        timestamp = None
                        ohlc_list = []
                        
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
                        
                        elif feed_data.HasField('ltpc'):
                            ltpc = feed_data.ltpc
                            ltp = float(ltpc.ltp)
                            timestamp = datetime.fromtimestamp(ltpc.ltt / 1000, IST) if ltpc.ltt else datetime.now(IST)
                        
                        if ltp is None:
                            continue
                        
                        if ohlc_list:
                            if inst_type:
                                self.process_ohlc_candles(inst_type, ohlc_list, feed_time=timestamp)
                            elif is_prescan:
                                self._update_prescan_ohlc(instrument_key, ohlc_list, feed_time=timestamp)
                        
                        if inst_type:
                            self.process_tick(inst_type, ltp, timestamp)
                    
                    return
                    
                except Exception as e:
                    print(f"Protobuf decode error: {e}")
                    return
                
        except Exception as e:
            import traceback
            print(f"Error processing message: {e}")
            traceback.print_exc()

    def on_open(self):
        self.running = True
        print(f"WebSocket connected")
        time.sleep(2)
        
        try:
            if self._prescan_keys:
                self.streamer.subscribe(self._prescan_keys, "full")
                print(f"Subscribed to {len(self._prescan_keys)} pre-subscribe instruments")
            elif self.streamer:
                keys_to_subscribe = []
                if 'CE' in self.active_instruments:
                    keys_to_subscribe.append(self.CE_KEY)
                if 'PE' in self.active_instruments:
                    keys_to_subscribe.append(self.PE_KEY)
                self.streamer.subscribe(keys_to_subscribe, "full")
                print(f"Subscribed to instruments")
        except Exception as e:
            print(f"Subscription error: {e}")

    def on_error(self, error):
        print(f"WebSocket error: {error}")

    def on_close(self, *args):
        print(f"WebSocket closed")
        self.running = False

    def _connect_ws(self, configuration):
        self.streamer = upstox_client.MarketDataStreamerV3(
            upstox_client.ApiClient(configuration)
        )
        self.streamer.on("open", self.on_open)
        self.streamer.on("message", self.on_message)
        self.streamer.on("error", self.on_error)
        self.streamer.on("close", self.on_close)
        self.streamer.auto_reconnect(False)
        print(f"Connecting to market data...")
        self.streamer.connect()

    def run(self):
        configuration = upstox_client.Configuration()
        configuration.access_token = self._access_token
        
        reconnect_attempts = 0
        max_reconnect = 20
        base_delay = 2
        
        while not self._stop_requested and reconnect_attempts < max_reconnect:
            try:
                self.running = True
                self._connect_ws(configuration)
                reconnect_attempts = 0
                
                while self.running and not self._stop_requested:
                    time.sleep(1)
                
                if self._stop_requested:
                    break
                
                reconnect_attempts += 1
                delay = min(base_delay * reconnect_attempts, 30)
                print(f"Disconnected — reconnecting in {delay}s (attempt {reconnect_attempts}/{max_reconnect})")
                time.sleep(delay)
                    
            except Exception as e:
                reconnect_attempts += 1
                delay = min(base_delay * reconnect_attempts, 30)
                print(f"Connection failed (attempt {reconnect_attempts}/{max_reconnect}): {e}")
                time.sleep(delay)
        
        if reconnect_attempts >= max_reconnect and not self._stop_requested:
            print("Max reconnection attempts reached — giving up")
            for inst in self.active_instruments:
                comp = self.components.get(inst)
                if comp:
                    comp['trade_logger'].close()
            self.running = False

    def close(self):
        self._stop_requested = True
        self.running = False
        if self.streamer:
            self.streamer.disconnect()
        for inst in self.active_instruments:
            comp = self.components.get(inst)
            if comp:
                comp['trade_logger'].close()
