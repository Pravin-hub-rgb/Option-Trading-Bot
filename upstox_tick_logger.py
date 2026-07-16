# upstox_tick_logger.py - Log every tick with timestamps for analysis
import upstox_client
from config import ACCESS_TOKEN
from datetime import datetime
import pytz
import time
import signal
import sys
import csv

IST = pytz.timezone('Asia/Kolkata')

print("=" * 70)
print("UPSTOX TICK LOGGER - DETAILED TIMESTAMP ANALYSIS")
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

running = True

# Create CSV log file
log_filename = f"tick_analysis_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}.csv"
log_file = open(log_filename, 'w', newline='')
csv_writer = csv.writer(log_file)
csv_writer.writerow([
    'Tick#', 'Instrument', 'LTP', 'Receive_Time', 'Exchange_Time', 
    'Time_Diff_ms', 'Gap_From_Last_ms'
])

# Tick tracking
tick_count = 0
last_tick_time = {'CE': None, 'PE': None}
tick_stats = {
    'CE': {'count': 0, 'total_gap': 0, 'max_gap': 0, 'min_gap': float('inf')},
    'PE': {'count': 0, 'total_gap': 0, 'max_gap': 0, 'min_gap': float('inf')}
}

def signal_handler(sig, frame):
    global running
    print("\n\n🛑 Stopping logger...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

def now():
    return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

def on_message(message):
    global tick_count
    
    try:
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
                
                # Extract LTP and timestamp
                ltp = None
                exchange_time = None
                
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
                                    ltt = ltpc_data.get('ltt', 0)
                                    if ltt:
                                        exchange_time = datetime.fromtimestamp(int(ltt) / 1000, IST)
                    
                    # Path 2: ltpc directly
                    elif 'ltpc' in feed_data:
                        ltpc_data = feed_data['ltpc']
                        if isinstance(ltpc_data, dict):
                            ltp = ltpc_data.get('ltp')
                            ltt = ltpc_data.get('ltt', 0)
                            if ltt:
                                exchange_time = datetime.fromtimestamp(int(ltt) / 1000, IST)
                
                if ltp is None:
                    continue
                
                ltp = float(ltp)
                receive_time = datetime.now(IST)
                
                # Calculate time differences
                time_diff_ms = None
                if exchange_time:
                    time_diff_ms = (receive_time - exchange_time).total_seconds() * 1000
                
                gap_from_last_ms = None
                if last_tick_time[inst_type]:
                    gap_from_last_ms = (receive_time - last_tick_time[inst_type]).total_seconds() * 1000
                    
                    # Update stats
                    tick_stats[inst_type]['total_gap'] += gap_from_last_ms
                    tick_stats[inst_type]['max_gap'] = max(tick_stats[inst_type]['max_gap'], gap_from_last_ms)
                    tick_stats[inst_type]['min_gap'] = min(tick_stats[inst_type]['min_gap'], gap_from_last_ms)
                
                last_tick_time[inst_type] = receive_time
                tick_stats[inst_type]['count'] += 1
                tick_count += 1
                
                # Log to CSV
                csv_writer.writerow([
                    tick_count,
                    inst_type,
                    ltp,
                    receive_time.strftime('%H:%M:%S.%f')[:-3],
                    exchange_time.strftime('%H:%M:%S.%f')[:-3] if exchange_time else 'N/A',
                    f"{time_diff_ms:.2f}" if time_diff_ms else 'N/A',
                    f"{gap_from_last_ms:.2f}" if gap_from_last_ms else 'N/A'
                ])
                
                # Print every tick to console (first 20, then every 50th)
                if tick_count <= 20 or tick_count % 50 == 0:
                    print(f"[{receive_time.strftime('%H:%M:%S.%f')[:-3]}] "
                          f"TICK {tick_count}: [{inst_type}] LTP={ltp:.2f} | "
                          f"Gap={f'{gap_from_last_ms:.0f}ms' if gap_from_last_ms else 'FIRST'} | "
                          f"Latency={f'{time_diff_ms:.0f}ms' if time_diff_ms else 'N/A'}")
        
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
                    exchange_time = None
                    
                    # Try fullFeed path
                    if feed_data.HasField('fullFeed'):
                        full_feed = feed_data.fullFeed
                        if full_feed.HasField('marketFF'):
                            market_ff = full_feed.marketFF
                            if market_ff.HasField('ltpc'):
                                ltpc = market_ff.ltpc
                                ltp = float(ltpc.ltp)
                                if ltpc.ltt:
                                    exchange_time = datetime.fromtimestamp(ltpc.ltt / 1000, IST)
                    
                    # Try ltpc-only path
                    elif feed_data.HasField('ltpc'):
                        ltpc = feed_data.ltpc
                        ltp = float(ltpc.ltp)
                        if ltpc.ltt:
                            exchange_time = datetime.fromtimestamp(ltpc.ltt / 1000, IST)
                    
                    if ltp is None:
                        continue
                    
                    receive_time = datetime.now(IST)
                    
                    # Calculate time differences
                    time_diff_ms = None
                    if exchange_time:
                        time_diff_ms = (receive_time - exchange_time).total_seconds() * 1000
                    
                    gap_from_last_ms = None
                    if last_tick_time[inst_type]:
                        gap_from_last_ms = (receive_time - last_tick_time[inst_type]).total_seconds() * 1000
                        
                        # Update stats
                        tick_stats[inst_type]['total_gap'] += gap_from_last_ms
                        tick_stats[inst_type]['max_gap'] = max(tick_stats[inst_type]['max_gap'], gap_from_last_ms)
                        tick_stats[inst_type]['min_gap'] = min(tick_stats[inst_type]['min_gap'], gap_from_last_ms)
                    
                    last_tick_time[inst_type] = receive_time
                    tick_stats[inst_type]['count'] += 1
                    tick_count += 1
                    
                    # Log to CSV
                    csv_writer.writerow([
                        tick_count,
                        inst_type,
                        ltp,
                        receive_time.strftime('%H:%M:%S.%f')[:-3],
                        exchange_time.strftime('%H:%M:%S.%f')[:-3] if exchange_time else 'N/A',
                        f"{time_diff_ms:.2f}" if time_diff_ms else 'N/A',
                        f"{gap_from_last_ms:.2f}" if gap_from_last_ms else 'N/A'
                    ])
                    
                    # Print to console
                    if tick_count <= 20 or tick_count % 50 == 0:
                        print(f"[{receive_time.strftime('%H:%M:%S.%f')[:-3]}] "
                              f"TICK {tick_count}: [{inst_type}] LTP={ltp:.2f} | "
                              f"Gap={f'{gap_from_last_ms:.0f}ms' if gap_from_last_ms else 'FIRST'} | "
                              f"Latency={f'{time_diff_ms:.0f}ms' if time_diff_ms else 'N/A'}")
            
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
        print(f"\n{'='*70}")
        print("LOGGING ALL TICKS - Press Ctrl+C to stop and see analysis")
        print(f"{'='*70}\n")
    except Exception as e:
        print(f"[{now()}] ✗ Subscription error: {e}")

def on_error(error):
    print(f"[{now()}] ✗ WebSocket error: {error}")

def on_close(*args):
    global running
    print(f"\n[{now()}] ⚠ WebSocket closed")
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

# Keep running until user stops
try:
    while running:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\n🛑 Stopped by user")

# Disconnect
try:
    streamer.disconnect()
except:
    pass

# Close log file
log_file.close()

# Print analysis
print("\n" + "=" * 70)
print("TICK ANALYSIS COMPLETE")
print("=" * 70)

print(f"\n📊 Total Ticks Logged: {tick_count}")
print(f"💾 Detailed log saved to: {log_filename}")

print("\n" + "-" * 70)
print(f"{'Instrument':<12} {'Ticks':<10} {'Avg Gap':<15} {'Min Gap':<15} {'Max Gap'}")
print("-" * 70)

for inst_type in ['CE', 'PE']:
    stats = tick_stats[inst_type]
    if stats['count'] > 1:
        avg_gap = stats['total_gap'] / (stats['count'] - 1)
        print(f"{inst_type:<12} {stats['count']:<10} "
              f"{avg_gap:<15.2f} {stats['min_gap']:<15.2f} {stats['max_gap']:.2f} ms")

print("\n" + "=" * 70)
print("KEY INSIGHTS:")
print("=" * 70)

for inst_type in ['CE', 'PE']:
    stats = tick_stats[inst_type]
    if stats['count'] > 1:
        avg_gap = stats['total_gap'] / (stats['count'] - 1)
        ticks_per_sec = 1000 / avg_gap if avg_gap > 0 else 0
        
        print(f"\n{inst_type}:")
        print(f"  Average tick rate: {ticks_per_sec:.2f} ticks/second")
        print(f"  Average gap: {avg_gap:.2f} ms")
        print(f"  Fastest tick: {stats['min_gap']:.2f} ms")
        print(f"  Slowest tick: {stats['max_gap']:.2f} ms")
        
        if avg_gap < 200:
            print(f"  ✓ GOOD speed (< 200ms average)")
        elif avg_gap < 500:
            print(f"  ⚠ MODERATE speed (200-500ms)")
        else:
            print(f"  ✗ SLOW speed (> 500ms)")

print(f"\n📁 Open {log_filename} in Excel for detailed timestamp analysis")
print("=" * 70)