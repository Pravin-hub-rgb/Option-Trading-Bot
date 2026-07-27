#!/usr/bin/env python3
"""
OHLC Monitor Test Script

Standalone test to monitor and print OHLC values of completed 1-minute candles
in real-time, just like the main bot processes them.

This version fetches fresh option chain data and picks strikes close to ₹100.

Usage: python test_ohlc_monitor.py
"""

import upstox_client
import requests
from config import ACCESS_TOKEN
from core.candle import CandleAggregator
from datetime import datetime
import pytz
import signal
import sys
import time

IST = pytz.timezone('Asia/Kolkata')

class OHLCMonitor:
    def __init__(self):
        self.running = True
        self.streamer = None
        self.candle_aggregators = {}
        
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Fetch fresh option chain and select strikes
        self.CE_KEY, self.CE_SYMBOL, self.PE_KEY, self.PE_SYMBOL = self.select_strikes()
        
        # Initialize candle aggregators
        self.candle_aggregators['CE'] = CandleAggregator(self.CE_SYMBOL)
        self.candle_aggregators['PE'] = CandleAggregator(self.PE_SYMBOL)
        
        print(f"[{self.now()}] 📊 OHLC Monitor initialized")
        print(f"[{self.now()}] 📡 Monitoring: CE={self.CE_SYMBOL}, PE={self.PE_SYMBOL}")

    def signal_handler(self, sig, frame):
        print(f"\n[{self.now()}] 🛑 Shutting down OHLC Monitor...")
        self.running = False
        if self.streamer:
            self.streamer.disconnect()
        sys.exit(0)

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def is_market_open(self):
        current_time = datetime.now(IST).strftime("%H:%M")
        return "09:15" <= current_time <= "15:30"

    def get_expiry(self):
        """Get next weekly expiry date"""
        try:
            resp = requests.get(
                f"https://api.upstox.com/v2/option/contract",
                headers={'Authorization': f'Bearer {ACCESS_TOKEN}', 'Accept': 'application/json'},
                params={'instrument_key': 'NSE_INDEX|Nifty 50'},
                timeout=10
            )
            data = resp.json().get('data', [])
            today = datetime.now(IST).date()
            expiries = sorted(set(
                item['expiry'] for item in data
                if datetime.strptime(item['expiry'], "%Y-%m-%d").date() >= today
            ))
            if expiries:
                expiry = expiries[0]
                print(f"[{self.now()}] 📅 Expiry: {expiry}")
                return expiry
        except Exception as e:
            print(f"[{self.now()}] ❌ Expiry fetch failed: {e}")
        return None

    def fetch_chain(self, expiry):
        """Fetch option chain for given expiry"""
        try:
            print(f"[{self.now()}] 📊 Fetching option chain for {expiry}...")
            resp = requests.get(
                f"https://api.upstox.com/v2/option/chain",
                headers={'Authorization': f'Bearer {ACCESS_TOKEN}', 'Accept': 'application/json'},
                params={
                    'instrument_key': 'NSE_INDEX|Nifty 50',
                    'expiry_date': expiry
                },
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data:
                    print(f"[{self.now()}] ✅ Chain fetched – {len(data['data'])} strikes")
                    return data['data']
        except Exception as e:
            print(f"[{self.now()}] ❌ Chain fetch error: {e}")
        return None

    def find_strikes_ge_target(self, chain, target=100):
        """Find CE/PE strikes with premium >= target, closest to target"""
        ce_list = []
        pe_list = []

        for entry in chain:
            strike = int(float(entry.get('strike_price', 0)))

            # CE
            ce = entry.get('call_options', {})
            if ce:
                ltp = float(ce.get('market_data', {}).get('ltp', 0))
                key = ce.get('instrument_key', '')
                if ltp >= target and ltp > 0:
                    ce_list.append({
                        'strike': strike,
                        'premium': ltp,
                        'key': key,
                        'diff': ltp - target
                    })

            # PE
            pe = entry.get('put_options', {})
            if pe:
                ltp = float(pe.get('market_data', {}).get('ltp', 0))
                key = pe.get('instrument_key', '')
                if ltp >= target and ltp > 0:
                    pe_list.append({
                        'strike': strike,
                        'premium': ltp,
                        'key': key,
                        'diff': ltp - target
                    })

        ce_best = min(ce_list, key=lambda x: x['diff']) if ce_list else None
        pe_best = min(pe_list, key=lambda x: x['diff']) if pe_list else None

        return ce_best, pe_best

    def select_strikes(self):
        """Select strikes using live premiums"""
        print(f"[{self.now()}] 🚀 Starting LIVE PREMIUM SELECTION...")
        
        # Get expiry
        expiry = self.get_expiry()
        if not expiry:
            print(f"[{self.now()}] ❌ Could not get expiry")
            sys.exit(1)

        # Fetch option chain
        chain = self.fetch_chain(expiry)
        if not chain:
            print(f"[{self.now()}] ❌ Could not fetch option chain")
            sys.exit(1)

        # Find strikes >= ₹100
        print(f"[{self.now()}] 🔍 Scanning ≥ ₹100 ...")
        ce, pe = self.find_strikes_ge_target(chain, 100)

        if not ce or not pe:
            print(f"[{self.now()}] 🔍 No ≥100 → trying ≥80")
            ce, pe = self.find_strikes_ge_target(chain, 80)

        if not ce or not pe:
            print(f"[{self.now()}] ❌ No suitable strikes found")
            sys.exit(1)

        print(f"[{self.now()}] ✅ CE: {ce['strike']} ({ce['premium']:.2f}), PE: {pe['strike']} ({pe['premium']:.2f})")
        
        return ce['key'], ce['key'], pe['key'], pe['key']

    def process_ohlc_candles(self, inst_type, ohlc_list):
        """Process OHLC candles from feed and print when completed"""
        aggregator = self.candle_aggregators[inst_type]
        
        # Filter for 1-minute candles and sort by timestamp
        i1_candles = [c for c in ohlc_list if c.get('interval') == 'I1']
        i1_candles.sort(key=lambda c: int(c.get('ts', 0)), reverse=True)
        
        # Process up to 2 most recent candles
        for candle_data in i1_candles[:2]:
            ts_ms = int(candle_data.get('ts', 0))
            candle_ts = datetime.fromtimestamp(ts_ms / 1000, IST)
            
            is_new = aggregator.update_from_ohlc(
                timestamp=candle_ts,
                open_price=float(candle_data.get('open', 0)),
                high_price=float(candle_data.get('high', 0)),
                low_price=float(candle_data.get('low', 0)),
                close_price=float(candle_data.get('close', 0))
            )
            
            if is_new:
                # Print the completed candle OHLC
                print(f"[{self.now()}] 🕒 NEW CANDLE: {candle_ts.strftime('%Y-%m-%d %H:%M:%S%z')}")
                print(f"[{self.now()}] 📊 {inst_type} OHLC: O={candle_data.get('open', 0):.2f} "
                      f"H={candle_data.get('high', 0):.2f} L={candle_data.get('low', 0):.2f} "
                      f"C={candle_data.get('close', 0):.2f}")

    def on_message(self, message):
        """WebSocket message handler"""
        try:
            # Handle marketInfo messages (metadata)
            if isinstance(message, dict) and 'marketInfo' in message:
                return
            
            # ==================================================================================
            # DICT FEED HANDLER (SDK 2.17.0+ auto-decodes protobuf to dict)
            # ==================================================================================
            if isinstance(message, dict) and 'feeds' in message:
                feeds = message['feeds']
                
                for instrument_key, feed_data in feeds.items():
                    # Identify instrument
                    if instrument_key == self.CE_KEY:
                        inst_type = 'CE'
                    elif instrument_key == self.PE_KEY:
                        inst_type = 'PE'
                    else:
                        continue
                    
                    # Extract OHLC
                    ohlc_list = []
                    
                    if isinstance(feed_data, dict):
                        # Path 1: fullFeed → marketFF → marketOHLC (FULL mode)
                        if 'fullFeed' in feed_data:
                            full_feed = feed_data['fullFeed']
                            if isinstance(full_feed, dict) and 'marketFF' in full_feed:
                                market_ff = full_feed['marketFF']
                                if isinstance(market_ff, dict) and 'marketOHLC' in market_ff:
                                    market_ohlc = market_ff['marketOHLC']
                                    if isinstance(market_ohlc, dict) and 'ohlc' in market_ohlc:
                                        ohlc_list = market_ohlc['ohlc']
                        
                        # Path 2: ltpc directly (LTPC-only mode) - no OHLC here
                        
                    # Process OHLC candles if available
                    if ohlc_list:
                        self.process_ohlc_candles(inst_type, ohlc_list)
                
                return
            
            # Handle other dict messages silently
            if isinstance(message, dict):
                return
            
            # ==================================================================================
            # PROTOBUF BINARY HANDLER (Fallback for older SDK versions)
            # ==================================================================================
            if isinstance(message, bytes):
                try:
                    from upstox.MarketDataFeedV3_pb2 import FeedResponse
                    feed_response = FeedResponse()
                    feed_response.ParseFromString(message)
                    
                    # Skip if not live feed
                    if not feed_response.feeds:
                        return
                    
                    # Process feeds from protobuf
                    for instrument_key, feed_data in feed_response.feeds.items():
                        # Identify instrument
                        if instrument_key == self.CE_KEY:
                            inst_type = 'CE'
                        elif instrument_key == self.PE_KEY:
                            inst_type = 'PE'
                        else:
                            continue
                        
                        # Extract OHLC from protobuf structure
                        ohlc_list = []
                        
                        # Try fullFeed path
                        if feed_data.HasField('fullFeed'):
                            full_feed = feed_data.fullFeed
                            if full_feed.HasField('marketFF'):
                                market_ff = full_feed.marketFF
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
                        
                        # Process OHLC
                        if ohlc_list:
                            self.process_ohlc_candles(inst_type, ohlc_list)
                    
                    return
                    
                except Exception as e:
                    print(f"[{self.now()}] ❌ Protobuf decode error: {e}")
                    return
                
        except Exception as e:
            print(f"[{self.now()}] ❌ Error processing message: {e}")

    def on_open(self):
        """Called when WebSocket opens"""
        print(f"[{self.now()}] ✅ WebSocket connected")
        time.sleep(2)
        
        # Subscribe to option strikes
        keys_to_subscribe = [self.CE_KEY, self.PE_KEY]
        
        try:
            self.streamer.subscribe(keys_to_subscribe, "full")
            print(f"[{self.now()}] 📡 Subscribed to instruments")
        except Exception as e:
            print(f"[{self.now()}] ❌ Subscription error: {e}")

    def on_error(self, error):
        print(f"[{self.now()}] ❌ WebSocket error: {error}")

    def on_close(self, *args):
        print(f"[{self.now()}] ⚠️ WebSocket closed")
        self.running = False

    def run(self):
        """Main run loop"""
        if not self.is_market_open():
            print(f"[{self.now()}] ⏰ Market is closed. Please run during market hours (09:15-15:30)")
            return

        configuration = upstox_client.Configuration()
        configuration.access_token = ACCESS_TOKEN
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.streamer = upstox_client.MarketDataStreamerV3(
                    upstox_client.ApiClient(configuration)
                )
                
                # Register callbacks
                self.streamer.on("open", self.on_open)
                self.streamer.on("message", self.on_message)
                self.streamer.on("error", self.on_error)
                self.streamer.on("close", self.on_close)
                
                print(f"[{self.now()}] 🔌 Connecting to market data...")
                self.streamer.connect()
                
                print(f"[{self.now()}] 📊 OHLC Monitor running. Press Ctrl+C to stop.")
                
                while self.running:
                    time.sleep(1)
                return
                
            except Exception as e:
                print(f"[{self.now()}] ❌ Connection failed: {e}")
                if attempt < max_retries - 1:
                    print(f"[{self.now()}] 🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(f"[{self.now()}] ❌ Max retries reached - Exiting")
                    sys.exit(1)

if __name__ == "__main__":
    monitor = OHLCMonitor()
    monitor.run()