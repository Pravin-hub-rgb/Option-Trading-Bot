# upstox_tick_test.py - Measure Upstox WebSocket tick speed
import upstox_client
from config import ACCESS_TOKEN
from datetime import datetime
import pytz
import time
import signal
import sys

IST = pytz.timezone('Asia/Kolkata')

print("=" * 70)
print("UPSTOX WEBSOCKET TICK SPEED TEST")
print("=" * 70)

# Load option keys
try:
    with open("option_keys.txt") as f:
        keys = dict(line.strip().split("=") for line in f)
    
    CE_KEY = keys["CE_SYMBOL"]
    CE_SYMBOL = keys["CE_KEY"]
    PE_KEY = keys["PE_SYMBOL"]
    PE_SYMBOL = keys["PE_KEY"]
    
    print(f"\nTesting with:")
    print(f"  CE: {CE_SYMBOL} ({CE_KEY})")
    print(f"  PE: {PE_SYMBOL} ({PE_KEY})")
    
except Exception as e:
    print(f"ERROR loading option_keys.txt: {e}")
    sys.exit(1)

# Test configuration
TEST_DURATION = 30  # seconds
running = True

# Tick counters
tick_stats = {
    'CE': {'count': 0, 'first_tick_time': None, 'last_tick_time': None, 'last_price': None},
    'PE': {'count': 0, 'first_tick_time': None, 'last_tick_time': None, 'last_price': None}
}
total_ticks = 0
test_start_time = None

def signal_handler(sig, frame):
    global running
    print("\n\n⚠ Test interrupted by user")
    running = False

signal.signal(signal.SIGINT, signal_handler)

def now():
    return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

def on_message(message):
    global total_ticks, test_start_time
    
    try:
        # Start timer on first message
        if test_start_time is None:
            test_start_time = time.time()
        
        # Handle dict feeds (SDK 2.17.0+)
        if isinstance(message, dict) and 'feeds' in message:
            feeds = message['feeds']
            
            for instrument_key, feed_data in feeds.items():
                # Identify instrument
                if instrument_key == CE_KEY:
                    inst_type = 'CE'
                elif instrument_key == PE_KEY:
                    inst_type = 'PE'
                else:
                    continue
                
                # Extract LTP
                ltp = None
                
                if isinstance(feed_data, dict):
                    # Path 1: fullFeed → marketFF → ltpc
                    if 'fullFeed' in feed_data:
                        full_feed = feed_data['fullFeed']
                        if isinstance(full_feed, dict) and 'marketFF' in full_feed:
                            market_ff = full_feed['marketFF']
                            if isinstance(market_ff, dict) and 'ltpc' in market_ff:
                                ltpc_data = market_ff['ltpc']
                                if isinstance(ltpc_data, dict):
                                    ltp = ltpc_data.get('ltp')
                    
                    # Path 2: ltpc directly
                    elif 'ltpc' in feed_data:
                        ltpc_data = feed_data['ltpc']
                        if isinstance(ltpc_data, dict):
                            ltp = ltpc_data.get('ltp')
                
                if ltp is None:
                    continue
                
                ltp = float(ltp)
                current_time = time.time()
                
                # Update stats
                tick_stats[inst_type]['count'] += 1
                tick_stats[inst_type]['last_price'] = ltp
                tick_stats[inst_type]['last_tick_time'] = current_time
                
                if tick_stats[inst_type]['first_tick_time'] is None:
                    tick_stats[inst_type]['first_tick_time'] = current_time
                
                total_ticks += 1
                
                # Print first 5 ticks to show it's working
                if total_ticks <= 5:
                    print(f"TICK {total_ticks}: [{inst_type}] LTP = {ltp}")
        
        # Handle protobuf binary feeds
        elif isinstance(message, bytes):
            try:
                from upstox.MarketDataFeedV3_pb2 import FeedResponse
                feed_response = FeedResponse()
                feed_response.ParseFromString(message)
                
                if not feed_response.feeds:
                    return
                
                for instrument_key, feed_data in feed_response.feeds.items():
                    # Identify instrument
                    if instrument_key == CE_KEY:
                        inst_type = 'CE'
                    elif instrument_key == PE_KEY:
                        inst_type = 'PE'
                    else:
                        continue
                    
                    ltp = None
                    
                    # Try fullFeed path
                    if feed_data.HasField('fullFeed'):
                        full_feed = feed_data.fullFeed
                        if full_feed.HasField('marketFF'):
                            market_ff = full_feed.marketFF
                            if market_ff.HasField('ltpc'):
                                ltpc = market_ff.ltpc
                                ltp = float(ltpc.ltp)
                    
                    # Try ltpc-only path
                    elif feed_data.HasField('ltpc'):
                        ltpc = feed_data.ltpc
                        ltp = float(ltpc.ltp)
                    
                    if ltp is None:
                        continue
                    
                    current_time = time.time()
                    
                    # Update stats
                    tick_stats[inst_type]['count'] += 1
                    tick_stats[inst_type]['last_price'] = ltp
                    tick_stats[inst_type]['last_tick_time'] = current_time
                    
                    if tick_stats[inst_type]['first_tick_time'] is None:
                        tick_stats[inst_type]['first_tick_time'] = current_time
                    
                    total_ticks += 1
                    
                    # Print first 5 ticks
                    if total_ticks <= 5:
                        print(f"TICK {total_ticks}: [{inst_type}] LTP = {ltp}")
            
            except Exception as e:
                pass  # Skip protobuf errors silently
    
    except Exception as e:
        pass  # Skip processing errors silently

def on_open():
    print(f"\n[{now()}] ✓ WebSocket connected")
    time.sleep(1)
    
    try:
        streamer.subscribe([CE_KEY, PE_KEY], "full")
        print(f"[{now()}] 📡 Subscribed to instruments in FULL mode")
        print(f"\nListening for {TEST_DURATION} seconds...")
        print("(First 5 ticks will be displayed)\n")
    except Exception as e:
        print(f"[{now()}] ✗ Subscription error: {e}")

def on_error(error):
    print(f"[{now()}] ✗ WebSocket error: {error}")

def on_close(*args):
    global running
    print(f"[{now()}] ⚠ WebSocket closed")
    running = False

# Setup WebSocket
configuration = upstox_client.Configuration()
configuration.access_token = ACCESS_TOKEN

streamer = upstox_client.MarketDataStreamerV3(
    upstox_client.ApiClient(configuration)
)

# Register callbacks
streamer.on("open", on_open)
streamer.on("message", on_message)
streamer.on("error", on_error)
streamer.on("close", on_close)

print(f"\n[{now()}] 🔌 Connecting to Upstox WebSocket...")
streamer.connect()

# Wait for test duration
start = time.time()
try:
    while running and (time.time() - start) < TEST_DURATION:
        time.sleep(0.1)
except KeyboardInterrupt:
    pass

# Disconnect
try:
    streamer.disconnect()
except:
    pass

# Calculate results
test_end_time = time.time()
elapsed = test_end_time - (test_start_time if test_start_time else start)

print("\n" + "=" * 70)
print("TEST COMPLETE - RESULTS")
print("=" * 70)

print(f"\nTotal Test Duration: {elapsed:.2f} seconds")
print(f"Total Ticks Received: {total_ticks}")

if total_ticks > 0:
    overall_rate = total_ticks / elapsed if elapsed > 0 else 0
    print(f"Overall Tick Rate: {overall_rate:.2f} ticks/second")
    
    print("\n" + "-" * 70)
    print(f"{'Instrument':<15} {'Ticks':<10} {'Rate (t/s)':<15} {'Last Price'}")
    print("-" * 70)
    
    for inst_type in ['CE', 'PE']:
        stats = tick_stats[inst_type]
        if stats['count'] > 0:
            inst_elapsed = (stats['last_tick_time'] - stats['first_tick_time']) if stats['first_tick_time'] else elapsed
            rate = stats['count'] / inst_elapsed if inst_elapsed > 0 else 0
            print(f"{inst_type:<15} {stats['count']:<10} {rate:<15.2f} {stats['last_price']}")
    
    print("\n" + "=" * 70)
    print("PERFORMANCE RATING:")
    print("=" * 70)
    
    if overall_rate >= 20:
        print("✓ EXCELLENT - Perfect for scalping (20+ ticks/sec)")
    elif overall_rate >= 10:
        print("✓ GOOD - Suitable for scalping (10-20 ticks/sec)")
    elif overall_rate >= 5:
        print("⚠ MODERATE - Marginal for scalping (5-10 ticks/sec)")
    else:
        print("✗ SLOW - Not suitable for scalping (< 5 ticks/sec)")
    
    print(f"\n📊 Upstox Tick Rate: {overall_rate:.2f} ticks/second")

else:
    print("\n✗ NO TICKS RECEIVED")
    print("\nPossible issues:")
    print("- Market is closed")
    print("- Invalid instrument keys")
    print("- Token expired")
    print("- Connection issues")

print("\n" + "=" * 70)