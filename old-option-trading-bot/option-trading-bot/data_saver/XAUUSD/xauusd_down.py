import requests
import lzma
import struct
from datetime import datetime, timedelta
import calendar
import pandas as pd
import os

# Constants
SYMBOL = 'XAUUSD'
DIVIDER = 1000.0
BASE_URL = f'https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{{year}}/{{month:02d}}/{{day:02d}}/{{hour:02d}}h_ticks.bi5'
TICK_STRUCT = '>IIIff'  # delta_ms (uint), ask (uint), bid (uint), ask_vol (float), bid_vol (float)
STRUCT_SIZE = struct.calcsize(TICK_STRUCT)
CURRENT_DATE = datetime(2025, 12, 30)  # Current date as per today

# Script directory for outputs
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def download_and_parse_hour(year, month, day, hour):
    url = BASE_URL.format(year=year, month=month-1, day=day-1, hour=hour)
    print(f"  Hour {hour:02d}: ", end='')
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print("no file (skipped)")
            return None
        
        compressed_data = response.content
        if len(compressed_data) < 100:  # Too small = likely empty
            print("empty file (skipped)")
            return None
        
        raw_data = lzma.decompress(compressed_data)
        
        if len(raw_data) % STRUCT_SIZE != 0:
            print("corrupt data (skipped)")
            return None
        
        ticks = []
        hour_start = datetime(year, month, day, hour)
        delta_base = 0
        for i in range(0, len(raw_data), STRUCT_SIZE):
            delta_ms, ask_int, bid_int, ask_vol, bid_vol = struct.unpack(TICK_STRUCT, raw_data[i:i+STRUCT_SIZE])
            delta_base += delta_ms
            ts = hour_start + timedelta(milliseconds=delta_base)
            mid_price = ((ask_int + bid_int) / 2.0) / DIVIDER
            ticks.append((ts, mid_price))
        
        print(f"{len(ticks)} ticks")
        return ticks
    
    except lzma.LZMAError:
        print("decompression error (skipped)")
        return None
    except struct.error:
        print("struct unpack error (skipped)")
        return None
    except Exception as e:
        print(f"error ({str(e)[:30]})")
        return None

def process_day(year, month, day, timeframe, csv_file):
    process_date = datetime(year, month, day)
    if process_date.date() > CURRENT_DATE.date():
        return  # Skip future
    
    daily_ticks = []
    for hour in range(24):
        ticks = download_and_parse_hour(year, month, day, hour)
        if ticks:
            daily_ticks.extend(ticks)
    
    if not daily_ticks:
        print("  No ticks this day")
        return
    
    df = pd.DataFrame(daily_ticks, columns=['timestamp', 'price'])
    df.set_index('timestamp', inplace=True)
    ohlc = df['price'].resample(timeframe).ohlc()
    
    if ohlc.empty:
        return
    
    ohlc['x'] = 0
    ohlc['y'] = 0
    ohlc.reset_index(inplace=True)
    ohlc['timestamp'] = ohlc['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    ohlc = ohlc[['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']]
    ohlc[['open', 'high', 'low', 'close']] = ohlc[['open', 'high', 'low', 'close']].round(3)
    
    header = not os.path.exists(csv_file)
    ohlc.to_csv(csv_file, mode='a', header=header, index=False, float_format='%.3f')
    print(f"  → {len(ohlc)} {timeframe} bars appended")

def main():
    print("="*80)
    print("XAUUSD Tick → OHLC Downloader (1min + 15min) - FIXED & ROBUST")
    print("UTC | Mid prices | Precise 3 decimals | x=0 y=0")
    print("Folder in script directory")
    print("="*80)
    
    year = int(input("Enter year (e.g., 2025): "))
    month_input = input("Enter month (1-12) or 'all' for full year: ").strip().lower()
    
    year_folder = os.path.join(SCRIPT_DIR, str(year))
    os.makedirs(year_folder, exist_ok=True)
    
    file_1m = os.path.join(year_folder, f'XAUUSD_1m_{year}.csv')
    file_15m = os.path.join(year_folder, f'XAUUSD_15m_{year}.csv')
    
    months = range(1, 13) if month_input == 'all' else [int(month_input)]
    
    for month in months:
        print(f"\n=== MONTH {month:02d}/{year} ===")
        _, days = calendar.monthrange(year, month)
        for day in range(1, days + 1):
            print(f"Day {day:02d}:")
            process_day(year, month, day, '1min', file_1m)
            process_day(year, month, day, '15min', file_15m)
    
    print("\nFINISHED! Check folder:", year_folder)

if __name__ == '__main__':
    main()