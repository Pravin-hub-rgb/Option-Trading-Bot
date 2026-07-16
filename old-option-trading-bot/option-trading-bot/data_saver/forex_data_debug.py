import os
import pandas as pd
import requests
import lzma
import struct
from datetime import datetime, timedelta
import time
import numpy as np
import logging
import sys
import json
from pathlib import Path

# ------------------- CONFIG -------------------
pair = "EURUSD"                          # Forex pair
base_folder = "eur_usd_data"             # Folder name
ALPHA_VANTAGE_API_KEY = "FZXZRL7D281ANOX4"  # Get from https://www.alphavantage.co/support/#api-key
# ---------------------------------------------

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('forex_debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_dukascopy_availability(year, month, day):
    """Check if Dukascopy has data available for a specific date"""
    try:
        year_str = f"{year:04d}"
        month_str = f"{month-1:02d}"  # Dukascopy uses 0-based month
        day_str = f"{day:02d}"
        
        # Try to access the first hour of the day
        url = f"https://datafeed.dukascopy.com/datafeed/{pair}/{year_str}/{month_str}/{day_str}/0h_ticks.bi5"
        
        response = requests.head(url, timeout=10)
        if response.status_code == 200:
            logger.info(f"Data available for {year}-{month:02d}-{day:02d}")
            return True
        else:
            logger.warning(f"No data available for {year}-{month:02d}-{day:02d} (status: {response.status_code})")
            return False
    except Exception as e:
        logger.error(f"Error checking availability for {year}-{month:02d}-{day:02d}: {e}")
        return False

def download_and_process_day(date, max_retries=3, retry_delay=2):
    """Download and process one day's tick data with improved error handling"""
    year_str = f"{date.year:04d}"
    month_str = f"{date.month-1:02d}"  # Dukascopy uses 0-based month
    day_str = f"{date.day:02d}"
    
    prices = []
    timestamps = []
    
    print(f"   {date.strftime('%Y-%m-%d')}: ", end="", flush=True)
    logger.info(f"Processing date: {date.strftime('%Y-%m-%d')}")
    
    for hour in range(24):
        url = f"https://datafeed.dukascopy.com/datafeed/{pair}/{year_str}/{month_str}/{day_str}/{hour}h_ticks.bi5"
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Downloading hour {hour} for {date.strftime('%Y-%m-%d')} (attempt {attempt + 1})")
                resp = requests.get(url, timeout=30)
                
                if resp.status_code == 200:
                    # Successfully downloaded
                    break
                elif resp.status_code == 404:
                    logger.debug(f"No data for hour {hour} on {date.strftime('%Y-%m-%d')}")
                    break  # No data for this hour, move to next
                else:
                    logger.warning(f"HTTP {resp.status_code} for hour {hour} on {date.strftime('%Y-%m-%d')}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Failed to download hour {hour} after {max_retries} attempts")
                        break
                        
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for hour {hour} on {date.strftime('%Y-%m-%d')} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    logger.error(f"Timeout for hour {hour} after {max_retries} attempts")
                    break
                    
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error for hour {hour} on {date.strftime('%Y-%m-%d')}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Unexpected error for hour {hour} on {date.strftime('%Y-%m-%d')}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    break
        
        if resp.status_code != 200:
            continue
            
        try:
            # Decompress LZMA
            decompressed = lzma.decompress(resp.content)
            
            # Unpack: delta_ms (int32), ask (uint32), bid (uint32), ask_vol (float32), bid_vol (float32)
            fmt = '>iIIf f'  # Big-endian: signed int, 2 unsigned int, 2 float
            chunk_size = struct.calcsize(fmt)
            
            base_time = int(date.timestamp() * 1000) + hour * 3600000  # ms
            prev_time = base_time
            
            ticks_count = 0
            for i in range(0, len(decompressed), chunk_size):
                chunk = decompressed[i:i+chunk_size]
                if len(chunk) < chunk_size:
                    break
                delta_ms, ask_int, bid_int, ask_v, bid_v = struct.unpack(fmt, chunk)
                
                current_time = prev_time + delta_ms
                prev_time = current_time
                
                price = (ask_int + bid_int) / 2 / 100000.0  # EURUSD has 5 decimals
                
                timestamps.append(current_time)
                prices.append(price)
                ticks_count += 1
                
            logger.debug(f"Processed {ticks_count} ticks for hour {hour}")
                
        except lzma.LZMAError as e:
            logger.error(f"LZMA decompression error for hour {hour}: {e}")
            continue
        except struct.error as e:
            logger.error(f"Struct unpack error for hour {hour}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error processing hour {hour}: {e}")
            continue
    
    if not prices:
        print("No data")
        logger.info(f"No data found for {date.strftime('%Y-%m-%d')}")
        return pd.DataFrame()
    
    df_day = pd.DataFrame({'timestamp': timestamps, 'price': prices})
    df_day['timestamp'] = pd.to_datetime(df_day['timestamp'], unit='ms', utc=True)
    print(f"{len(prices):,} ticks")
    logger.info(f"Successfully processed {len(prices):,} ticks for {date.strftime('%Y-%m-%d')}")
    return df_day

def aggregate_to_bars(ticks_df, freq):
    """Aggregate tick data to OHLC bars with improved error handling"""
    if ticks_df.empty:
        logger.warning("Empty DataFrame passed to aggregate_to_bars")
        return pd.DataFrame()

    try:
        ticks_df = ticks_df.set_index('timestamp')

        # Create complete time index from min to max timestamp with the specified frequency
        start_time = ticks_df.index.min()
        end_time = ticks_df.index.max()
        complete_index = pd.date_range(start=start_time, end=end_time, freq=freq)

        # Resample to get OHLC
        ohlc = ticks_df['price'].resample(freq).ohlc()

        # Reindex to complete time range to fill gaps
        ohlc = ohlc.reindex(complete_index)

        # Forward fill open/high/low/close for missing bars
        ohlc = ohlc.ffill().dropna()  # or bfill if preferred
        ohlc.reset_index(inplace=True)
        ohlc.rename(columns={'index': 'timestamp'}, inplace=True)
        logger.info(f"Aggregated to {len(ohlc)} {freq} bars")
        return ohlc
    except Exception as e:
        logger.error(f"Error in aggregate_to_bars: {e}")
        return pd.DataFrame()

def save_checkpoint(year, processed_dates, failed_dates):
    """Save progress to a checkpoint file"""
    checkpoint_data = {
        'year': year,
        'processed_dates': [d.isoformat() for d in processed_dates],
        'failed_dates': [d.isoformat() for d in failed_dates],
        'last_updated': datetime.now().isoformat()
    }
    
    checkpoint_file = os.path.join(base_folder, str(year), 'checkpoint.json')
    os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
    
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)
    
    logger.info(f"Checkpoint saved: {len(processed_dates)} processed, {len(failed_dates)} failed")

def load_checkpoint(year):
    """Load progress from a checkpoint file"""
    checkpoint_file = os.path.join(base_folder, str(year), 'checkpoint.json')
    
    if not os.path.exists(checkpoint_file):
        return [], []
    
    try:
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
        
        processed_dates = [datetime.fromisoformat(d).date() for d in checkpoint_data.get('processed_dates', [])]
        failed_dates = [datetime.fromisoformat(d).date() for d in checkpoint_data.get('failed_dates', [])]
        
        logger.info(f"Checkpoint loaded: {len(processed_dates)} processed, {len(failed_dates)} failed")
        return processed_dates, failed_dates
    except Exception as e:
        logger.error(f"Error loading checkpoint: {e}")
        return [], []

def get_available_years():
    """Check which years are available on Dukascopy"""
    available_years = []
    current_year = datetime.now().year
    
    # Check last 5 years
    for year in range(current_year - 4, current_year + 1):
        if check_dukascopy_availability(year, 1, 1):  # Check Jan 1
            available_years.append(year)
    
    return available_years

# =============== MAIN ===============
def main():
    os.makedirs(base_folder, exist_ok=True)

    print("="*70)
    print("EUR/USD Forex Downloader (1m + 15m) from Dukascopy - DEBUG VERSION")
    print("→ Full year COMPLETE bars (no missing minutes) in UTC")
    print("→ Enhanced error handling and progress tracking")
    print("="*70)

    # Check available years
    print("\nChecking available years on Dukascopy...")
    available_years = get_available_years()
    print(f"Available years: {available_years}")
    
    if not available_years:
        print("No years available on Dukascopy. Please try a different data source.")
        return

    while True:
        try:
            year = int(input(f"Enter year (available: {available_years}): "))
            if year in available_years:
                break
            else:
                print(f"Year {year} not available. Please choose from: {available_years}")
        except ValueError:
            print("Please enter a valid year.")

    print(f"\nDownloading full year {year} for EUR/USD...\n")

    year_folder = os.path.join(base_folder, str(year))
    os.makedirs(year_folder, exist_ok=True)

    # Load checkpoint
    processed_dates, failed_dates = load_checkpoint(year)
    
    start_date = datetime(year, 1, 1)
    end_date = datetime(year + 1, 1, 1)
    current = start_date
    all_ticks = []
    
    # Skip already processed dates
    if processed_dates:
        current = max(processed_dates) + timedelta(days=1)
        print(f"Resuming from {current.strftime('%Y-%m-%d')}")

    total_days = (end_date - start_date).days
    processed_count = len(processed_dates)
    
    print(f"Total days to process: {total_days}")
    print(f"Already processed: {len(processed_dates)}")
    print(f"Remaining: {total_days - len(processed_dates)}")
    print()

    day_count = 0
    start_time = time.time()

    while current < end_date:
        if current.weekday() < 5:  # Skip weekends
            if current.date() not in processed_dates and current.date() not in failed_dates:
                day_count += 1
                progress = (processed_count + day_count) / total_days * 100
                elapsed = time.time() - start_time
                if day_count > 1:
                    avg_time_per_day = elapsed / (day_count - 1)
                    remaining_days = total_days - len(processed_dates) - day_count + 1
                    estimated_remaining = remaining_days * avg_time_per_day
                    print(f"Progress: {progress:.1f}% | ETA: {timedelta(seconds=int(estimated_remaining))}")
                
                df_day = download_and_process_day(current)
                if not df_day.empty:
                    all_ticks.append(df_day)
                    processed_dates.append(current.date())
                else:
                    failed_dates.append(current.date())
                
                # Save checkpoint every 10 days
                if day_count % 10 == 0:
                    save_checkpoint(year, processed_dates, failed_dates)
                
                # Sleep to avoid overwhelming the server
                time.sleep(0.5)
        
        current += timedelta(days=1)

    # Save final checkpoint
    save_checkpoint(year, processed_dates, failed_dates)

    if not all_ticks:
        print("No data downloaded for this year.")
        logger.error("No data downloaded - check Dukascopy availability and network connection")
    else:
        print(f"\nProcessing {len(all_ticks)} days of data...")
        ticks_year = pd.concat(all_ticks).sort_values('timestamp').reset_index(drop=True)
        
        # 1min bars (complete)
        print("Creating 1-minute bars...")
        df_1min = aggregate_to_bars(ticks_year.copy(), '1min')

        if not df_1min.empty:
            df_1min_final = df_1min.copy()
            df_1min_final['x'] = 0
            df_1min_final['y'] = 0
            df_1min_final = df_1min_final[['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']]

            file_1m = os.path.join(year_folder, f"{pair}_1m.csv")
            df_1min_final.to_csv(file_1m, index=False, header=True,
                                 date_format='%Y-%m-%d %H:%M:%S', float_format='%.5f')
            size_1m = os.path.getsize(file_1m) / (1024*1024)
            print(f"\n   Saved {pair}_1m.csv → {len(df_1min_final):,} COMPLETE bars ({size_1m:.2f} MB)")
            logger.info(f"1m bars saved: {len(df_1min_final):,} bars, {size_1m:.2f} MB")
        else:
            print("No 1-minute bars created")
            logger.warning("No 1-minute bars created")

        # 15min bars
        print("Creating 15-minute bars...")
        df_15min = aggregate_to_bars(ticks_year.copy(), '15min')
        
        if not df_15min.empty:
            df_15min_final = df_15min.copy()
            df_15min_final['x'] = 0
            df_15min_final['y'] = 0
            df_15min_final = df_15min_final[['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']]
            
            file_15m = os.path.join(year_folder, f"{pair}_15m.csv")
            df_15min_final.to_csv(file_15m, index=False, header=True,
                                  date_format='%Y-%m-%d %H:%M:%S', float_format='%.5f')
            size_15m = os.path.getsize(file_15m) / (1024*1024)
            print(f"   Saved {pair}_15m.csv → {len(df_15min_final):,} COMPLETE bars ({size_15m:.2f} MB)")
            logger.info(f"15m bars saved: {len(df_15min_final):,} bars, {size_15m:.2f} MB")
        else:
            print("No 15-minute bars created")
            logger.warning("No 15-minute bars created")

    print("\nALL DONE! 🚀")
    print(f"Check folder: {year_folder}")
    print("Complete bars from Dukascopy ticks — no gaps in open minutes!")
    print(f"Debug log saved to: forex_debug.log")
    
    if failed_dates:
        print(f"\nFailed dates ({len(failed_dates)}):")
        for date in failed_dates[:10]:  # Show first 10
            print(f"  - {date}")
        if len(failed_dates) > 10:
            print(f"  ... and {len(failed_dates) - 10} more")

if __name__ == "__main__":
    main()
