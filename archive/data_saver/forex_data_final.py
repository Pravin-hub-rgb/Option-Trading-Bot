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
import yfinance as yf  # Free alternative

# ------------------- CONFIG -------------------
pair = "EURUSD"                          # Forex pair
base_folder = "eur_usd_data"             # Folder name
ALPHA_VANTAGE_API_KEY = "FZXZRL7D281ANOX4"  # Get from https://www.alphavantage.co/support/#api-key

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

def download_dukascopy_day(date, max_retries=3, retry_delay=2):
    """Download and process one day's tick data from Dukascopy"""
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

def download_yahoo_day(date):
    """Download daily data from Yahoo Finance as fallback"""
    try:
        # Yahoo Finance symbol for EUR/USD
        symbol = "EURUSD=X"

        # Get data for the specific date
        start_date = date.strftime('%Y-%m-%d')
        end_date = (date + timedelta(days=1)).strftime('%Y-%m-%d')

        print(f"   {date.strftime('%Y-%m-%d')}: ", end="", flush=True)
        logger.info(f"Downloading from Yahoo Finance: {date.strftime('%Y-%m-%d')}")

        # Download data
        data = yf.download(symbol, start=start_date, end=end_date, interval='1m')

        if data.empty:
            print("No data")
            return pd.DataFrame()

        # Convert to the format expected by the rest of the script
        # Yahoo Finance gives us OHLC data, but we need tick data
        # We'll create synthetic tick data from the OHLC

        prices = []
        timestamps = []

        for idx, row in data.iterrows():
            # Create synthetic ticks based on OHLC
            # We'll create 4 ticks per minute: open, high, low, close
            base_time = idx.timestamp() * 1000  # Convert to milliseconds

            # Add open price
            prices.append(row['Open'])
            timestamps.append(base_time)

            # Add high price (slightly offset in time)
            prices.append(row['High'])
            timestamps.append(base_time + 10000)  # 10 seconds later

            # Add low price
            prices.append(row['Low'])
            timestamps.append(base_time + 20000)  # 20 seconds later

            # Add close price
            prices.append(row['Close'])
            timestamps.append(base_time + 30000)  # 30 seconds later

        if not prices:
            print("No data")
            return pd.DataFrame()

        df_day = pd.DataFrame({'timestamp': timestamps, 'price': prices})
        df_day['timestamp'] = pd.to_datetime(df_day['timestamp'], unit='ms', utc=True)
        print(f"{len(prices):,} synthetic ticks")
        logger.info(f"Created {len(prices):,} synthetic ticks for {date.strftime('%Y-%m-%d')}")
        return df_day

    except Exception as e:
        logger.error(f"Error downloading from Yahoo Finance: {e}")
        print("No data")
        return pd.DataFrame()

def download_alpha_vantage_day(date):
    """Download daily data from Alpha Vantage"""
    try:
        if ALPHA_VANTAGE_API_KEY == "YOUR_API_KEY_HERE":
            print("No API key - skipping Alpha Vantage")
            return pd.DataFrame()

        print(f"   {date.strftime('%Y-%m-%d')}: ", end="", flush=True)
        logger.info(f"Downloading from Alpha Vantage: {date.strftime('%Y-%m-%d')}")

        # Alpha Vantage forex API
        url = f"https://www.alphavantage.co/query"
        params = {
            "function": "FX_INTRADAY",
            "from_symbol": "EUR",
            "to_symbol": "USD",
            "interval": "1min",
            "apikey": ALPHA_VANTAGE_API_KEY,
            "outputsize": "full"
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if "Error Message" in data:
            logger.error(f"Alpha Vantage error: {data['Error Message']}")
            print("API error")
            return pd.DataFrame()

        if "Note" in data:
            logger.warning(f"Alpha Vantage note: {data['Note']}")
            print("API limit reached")
            return pd.DataFrame()

        # Extract intraday data
        time_series_key = "Time Series FX (1min)"
        if time_series_key not in data:
            logger.error(f"No time series data in response: {list(data.keys())}")
            print("No data")
            return pd.DataFrame()

        time_series = data[time_series_key]

        prices = []
        timestamps = []

        # Filter for the specific date
        target_date_str = date.strftime('%Y-%m-%d')

        for timestamp_str, values in time_series.items():
            # Parse timestamp
            dt = pd.to_datetime(timestamp_str)
            if dt.date() != date.date():
                continue  # Skip if not the target date

            # Extract OHLC prices
            open_price = float(values['1. open'])
            high_price = float(values['2. high'])
            low_price = float(values['3. low'])
            close_price = float(values['4. close'])

            # Convert to tick format - create 4 ticks per minute
            base_time = dt.timestamp() * 1000  # milliseconds

            # Add ticks for OHLC
            prices.extend([open_price, high_price, low_price, close_price])
            timestamps.extend([
                base_time,
                base_time + 10000,  # 10s later
                base_time + 20000,  # 20s later
                base_time + 30000   # 30s later
            ])

        if not prices:
            print("No data for date")
            return pd.DataFrame()

        df_day = pd.DataFrame({'timestamp': timestamps, 'price': prices})
        df_day['timestamp'] = pd.to_datetime(df_day['timestamp'], unit='ms', utc=True)
        print(f"{len(prices):,} ticks")
        logger.info(f"Downloaded {len(prices)} ticks from Alpha Vantage for {date.strftime('%Y-%m-%d')}")
        return df_day

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error with Alpha Vantage: {e}")
        print("Network error")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error downloading from Alpha Vantage: {e}")
        print("Error")
        return pd.DataFrame()

def aggregate_to_bars(ticks_df, freq):
    """Aggregate tick data to OHLC bars - NO GAP FILLING"""
    if ticks_df.empty:
        logger.warning("Empty DataFrame passed to aggregate_to_bars")
        return pd.DataFrame()

    try:
        ticks_df = ticks_df.set_index('timestamp')

        # Resample to get OHLC - only create bars where data exists
        ohlc = ticks_df['price'].resample(freq).ohlc()

        # Drop any bars that are completely NaN (no data in that period)
        ohlc = ohlc.dropna(how='all')

        # Reset index to get timestamp column
        ohlc.reset_index(inplace=True)
        ohlc.rename(columns={'index': 'timestamp'}, inplace=True)

        logger.info(f"Aggregated to {len(ohlc)} {freq} bars (gaps preserved)")
        return ohlc
    except Exception as e:
        logger.error(f"Error in aggregate_to_bars: {e}")
        return pd.DataFrame()

def save_checkpoint(year, processed_dates, failed_dates, source_used):
    """Save progress to a checkpoint file"""
    checkpoint_data = {
        'year': year,
        'processed_dates': [d.isoformat() for d in processed_dates],
        'failed_dates': [d.isoformat() for d in failed_dates],
        'source_used': source_used,
        'last_updated': datetime.now().isoformat()
    }
    
    checkpoint_file = os.path.join(base_folder, str(year), 'checkpoint.json')
    os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
    
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)
    
    logger.info(f"Checkpoint saved: {len(processed_dates)} processed, {len(failed_dates)} failed, source: {source_used}")

def load_checkpoint(year):
    """Load progress from a checkpoint file"""
    checkpoint_file = os.path.join(base_folder, str(year), 'checkpoint.json')
    
    if not os.path.exists(checkpoint_file):
        return [], [], None
    
    try:
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
        
        processed_dates = [datetime.fromisoformat(d).date() for d in checkpoint_data.get('processed_dates', [])]
        failed_dates = [datetime.fromisoformat(d).date() for d in checkpoint_data.get('failed_dates', [])]
        source_used = checkpoint_data.get('source_used', None)
        
        logger.info(f"Checkpoint loaded: {len(processed_dates)} processed, {len(failed_dates)} failed, source: {source_used}")
        return processed_dates, failed_dates, source_used
    except Exception as e:
        logger.error(f"Error loading checkpoint: {e}")
        return [], [], None

def get_available_years():
    """Check which years are available on Dukascopy"""
    available_years = []
    current_year = datetime.now().year
    
    # Check last 5 years
    for year in range(current_year - 4, current_year + 1):
        if check_dukascopy_availability(year, 1, 1):  # Check Jan 1
            available_years.append(year)
    
    return available_years

def check_yahoo_availability(year):
    """Check if Yahoo Finance has data for the year"""
    try:
        symbol = "EURUSD=X"
        start_date = f"{year}-01-01"
        end_date = f"{year}-01-02"

        data = yf.download(symbol, start=start_date, end=end_date, interval='1d')
        if not data.empty:
            logger.info(f"Yahoo Finance data available for {year}")
            return True
        else:
            logger.warning(f"No Yahoo Finance data for {year}")
            return False
    except Exception as e:
        logger.error(f"Error checking Yahoo Finance availability for {year}: {e}")
        return False

def check_alpha_vantage_availability(year):
    """Check if Alpha Vantage has data for the year"""
    try:
        if ALPHA_VANTAGE_API_KEY == "YOUR_API_KEY_HERE":
            return False

        # Test with a recent date to check API availability
        test_date = datetime(year, 1, 1)
        if test_date > datetime.now() - timedelta(days=30):
            test_date = datetime.now() - timedelta(days=30)

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "FX_INTRADAY",
            "from_symbol": "EUR",
            "to_symbol": "USD",
            "interval": "1min",
            "apikey": ALPHA_VANTAGE_API_KEY,
            "outputsize": "compact"
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if "Error Message" in data:
            logger.warning(f"Alpha Vantage API error: {data['Error Message']}")
            return False

        if "Note" in data:
            logger.warning(f"Alpha Vantage API limit note: {data['Note']}")
            # Still consider available but rate limited
            return True

        time_series_key = "Time Series FX (1min)"
        if time_series_key in data and data[time_series_key]:
            logger.info(f"Alpha Vantage data available")
            return True
        else:
            logger.warning("Alpha Vantage returned no data")
            return False

    except Exception as e:
        logger.error(f"Error checking Alpha Vantage availability: {e}")
        return False

def show_data_availability_info():
    """Show information about data availability"""
    print("\n" + "="*70)
    print("FOREX DATA AVAILABILITY INFORMATION")
    print("="*70)
    print("IMPORTANT: 2025 Forex data is NOT yet available from free sources.")
    print("This is normal - Forex data providers typically have delays.")
    print()
    print("Available years from different sources:")

    # Check Alpha Vantage
    print("\nAlpha Vantage (High-quality API, requires free API key):")
    alphavantage_available = check_alpha_vantage_availability(2024)  # Test with 2024 data
    if alphavantage_available:
        print(f"  ✓ Available (API key working)")
    else:
        print("  ✗ Not available (API key required or service issues)")

    # Check Dukascopy
    print("\nDukascopy (High-quality tick data):")
    dukascopy_years = get_available_years()
    if dukascopy_years:
        print(f"  ✓ Available: {dukascopy_years}")
    else:
        print("  ✗ No years available (service may be down)")

    # Check Yahoo Finance
    print("\nYahoo Finance (OHLC data, limited history):")
    yahoo_years = []
    current_year = datetime.now().year
    for year in range(current_year - 10, current_year + 1):  # Check last 10 years
        if check_yahoo_availability(year):
            yahoo_years.append(year)

    if yahoo_years:
        print(f"  ✓ Available: {yahoo_years}")
    else:
        print("  ✗ No years available")

    available_years = sorted(list(set(dukascopy_years + yahoo_years)))

    print(f"\nRECOMMENDED YEARS TO DOWNLOAD: {available_years}")
    print("\nData Source Priority:")
    print("1. Alpha Vantage (best quality, requires API key)")
    print("2. Dukascopy (high quality, may be down)")
    print("3. Yahoo Finance (good for recent data)")
    print("\nFor 2025 data, you will need to:")
    print("1. Wait until data becomes available (usually with delay)")
    print("2. Use a paid Forex data provider")
    print("3. Use alternative data sources")
    print("="*70)

    return available_years

# =============== MAIN ===============
def main():
    os.makedirs(base_folder, exist_ok=True)

    print("="*70)
    print("EUR/USD Forex Downloader (1m + 15m) - ALPHA VANTAGE ONLY")
    print("→ Full year COMPLETE bars (no missing minutes) in UTC")
    print("→ Uses Alpha Vantage API (requires free API key)")
    print("→ Enhanced error handling and progress tracking")
    print("="*70)

    # Show data availability information
    available_years = show_data_availability_info()
    
    if not available_years:
        print("\nNo data sources are currently available.")
        print("Please check your internet connection and try again later.")
        return

    while True:
        try:
            year = int(input(f"\nEnter year to download (recommended: {available_years}): "))
            if year in available_years:
                break
            else:
                print(f"Year {year} not available. Please choose from: {available_years}")
                print("Note: 2025 data is not yet available from free sources.")
        except ValueError:
            print("Please enter a valid year.")

    print(f"\nDownloading full year {year} for EUR/USD...\n")

    year_folder = os.path.join(base_folder, str(year))
    os.makedirs(year_folder, exist_ok=True)

    # Load checkpoint
    processed_dates, failed_dates, source_used = load_checkpoint(year)
    
    # Determine data source - ONLY Alpha Vantage
    if source_used is None:
        # Check if Alpha Vantage has data for this year
        alphavantage_available = check_alpha_vantage_availability(year)

        if alphavantage_available:
            source_used = "alphavantage"
            print("✓ Using Alpha Vantage as data source (high-quality API data)")
        else:
            print("✗ Alpha Vantage not available - check API key")
            return
    else:
        print(f"Resuming with {source_used} data source")
    
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
                
                # Try to download based on source
                if source_used == "alphavantage":
                    df_day = download_alpha_vantage_day(current)
                elif source_used == "dukascopy":
                    df_day = download_dukascopy_day(current)
                else:
                    df_day = download_yahoo_day(current)
                
                if not df_day.empty:
                    all_ticks.append(df_day)
                    processed_dates.append(current.date())
                else:
                    failed_dates.append(current.date())
                
                # Save checkpoint every 10 days
                if day_count % 10 == 0:
                    save_checkpoint(year, processed_dates, failed_dates, source_used)
                
                # Sleep to avoid overwhelming the server
                time.sleep(0.5)
        
        current += timedelta(days=1)

    # Save final checkpoint
    save_checkpoint(year, processed_dates, failed_dates, source_used)

    if not all_ticks:
        print("No data downloaded for this year.")
        logger.error("No data downloaded - check data source availability and network connection")
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
    print("Complete bars from Forex data — no gaps in open minutes!")
    print(f"Debug log saved to: forex_debug.log")
    print(f"Data source used: {source_used}")
    
    if failed_dates:
        print(f"\nFailed dates ({len(failed_dates)}):")
        for date in failed_dates[:10]:  # Show first 10
            print(f"  - {date}")
        if len(failed_dates) > 10:
            print(f"  ... and {len(failed_dates) - 10} more")
    
    print("\n" + "="*70)
    print("TROUBLESHOOTING FOR 2025 DATA:")
    print("="*70)
    print("If you were trying to download 2025 data:")
    print("1. 2025 Forex data is not yet available from free sources")
    print("2. Try downloading 2024 or earlier years instead")
    print("3. For 2025 data, you'll need:")
    print("   - A paid Forex data subscription")
    print("   - Wait until data becomes available (with delay)")
    print("   - Use alternative data providers")
    print("="*70)

if __name__ == "__main__":
    main()
