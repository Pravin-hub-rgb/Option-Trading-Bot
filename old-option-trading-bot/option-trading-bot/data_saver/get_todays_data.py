# --- get_todays_data.py (Updated for Two Closest Premiums ≥100, Morning Only) ---

import upstox_client
from datetime import datetime, timedelta, date, time, timezone
import csv
import os
import json
import pandas as pd
from io import StringIO
from config import (
    API_KEY,
    ACCESS_TOKEN,
    NIFTY_INDEX_KEY,
    API_VERSION,
    MORNING_ATM_CHECK_TIME,
    PRICE_INDEX_MORNING
)
from upstox_client.rest import ApiException

# --- Strategy Configuration ---
MIN_PREMIUM = 100  # Minimum premium threshold
NUM_OPTIONS_TO_SELECT = 2  # Select 2 closest premiums above threshold

# --- Firebase Setup (Not needed for local execution, but included for environment compatibility) ---
appId = "default-app-id"
firebaseConfig = {}

# --- Time Window Definitions ---
FULL_DAY_START = '09:15'
FULL_DAY_END = '15:30'
MORNING_SHORT_WINDOW = (FULL_DAY_START, '12:00')  # Updated to 12:00


def setup_api_client():
    """Initializes the API client using the access token."""
    if not ACCESS_TOKEN or ACCESS_TOKEN.startswith("YOUR_"):
        raise ValueError("ACCESS_TOKEN ko config.py mein set karna padega! Please set ACCESS_TOKEN correctly.")
    configuration = upstox_client.Configuration()
    configuration.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(configuration)
    historical_api = upstox_client.HistoryApi(api_client)
    options_api = upstox_client.OptionsApi(api_client)
    return historical_api, options_api

def is_today_post_close():
    """Check if current time is after market close (3:30 PM IST) on a weekday."""
    now = datetime.now()
    if now.weekday() >= 5:  # Weekend
        return False
    market_close = time(15, 30)
    return now.time() > market_close

def get_nifty_spot_at_time(historical_api, date_str, check_time_str: str, price_index: int):
    """
    Fetches Nifty Index 1-min data. Used for logging/reference only.
    Returns: (spot_price, actual_trading_date)
    """
    price_type = "Open" if price_index == 1 else "Close"
    check_time = datetime.strptime(check_time_str, "%H:%M").time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    use_intraday = (date_str == today_str) and is_today_post_close()
    
    api_method = "Intraday" if use_intraday else "Historical"
    print(f"\n- Nifty Index spot price fetch ho raha hai ({price_type} Price) at {check_time_str}... (Using {api_method} API)")
    
    try:
        if use_intraday:
            response = historical_api.get_intra_day_candle_data(
                instrument_key=NIFTY_INDEX_KEY,
                interval="1minute",
                api_version=API_VERSION
            )
        else:
            response = historical_api.get_historical_candle_data(
                instrument_key=NIFTY_INDEX_KEY,
                interval="1minute",
                to_date=date_str,
                api_version=API_VERSION
            )
        
        if not response.data or not response.data.candles:
            return None, date_str
        
        candles = response.data.candles
        
        # Check for date correction
        first_candle_date = candles[0][0].split('T')[0]
        if first_candle_date != date_str:
            date_str = first_candle_date
        
        # Try multiple timestamp formats
        target_timestamp_1 = f"{date_str}T{check_time_str}:00"
        target_timestamp_2 = f"{date_str}T{check_time_str}:00.000"
        for candle in candles:
            timestamp = candle[0]
            if timestamp.startswith(target_timestamp_1) or timestamp.startswith(target_timestamp_2):
                spot_price = candle[price_index]
                print(f" ✅ Nifty Spot Price ({price_type}) at {check_time_str} was: {spot_price}")
                return spot_price, date_str
        
        print(f" ⚠️ {check_time_str} ke exact time ke liye Nifty candle data nahi mila.")
        return None, date_str
    except ApiException as e:
        error_details = json.loads(e.body) if e.body else str(e)
        print(f" ❌ Nifty Index fetch karte time API Error: {error_details}")
        return None, date_str
    except Exception as e:
        print(f" ❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return None, date_str

def get_option_premium_at_time(historical_api, instrument_key, date_str, check_time_str, price_index):
    """
    Fetches the premium (Open/Close price) of a specific option instrument at the given time.
    """
    if not instrument_key:
        return None
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    use_intraday = (date_str == today_str) and is_today_post_close()
    
    try:
        if use_intraday:
            response = historical_api.get_intra_day_candle_data(
                instrument_key=instrument_key,
                interval="1minute",
                api_version=API_VERSION
            )
        else:
            response = historical_api.get_historical_candle_data(
                instrument_key=instrument_key,
                interval="1minute",
                to_date=date_str,
                api_version=API_VERSION
            )
            
        if not response.data or not response.data.candles:
            return None
        
        # Try finding the exact timestamp candle
        target_timestamp_1 = f"{date_str}T{check_time_str}:00"
        target_timestamp_2 = f"{date_str}T{check_time_str}:00.000"
        
        for candle in response.data.candles:
            timestamp = candle[0]
            if timestamp.startswith(target_timestamp_1) or timestamp.startswith(target_timestamp_2):
                return candle[price_index]
                
        return None
        
    except ApiException:
        return None
    except Exception:
        return None

def get_two_closest_premiums_above_threshold(historical_api, options_api, target_date_str, expiry_date_str, check_time_str, price_index):
    """
    Finds TWO CE and TWO PE options with the closest premiums above MIN_PREMIUM threshold.
    Returns: (list of 2 CE tuples, list of 2 PE tuples)
    Each tuple: (instrument_key, symbol, strike, premium)
    """
    print(f"\n- Options with premium ≥ {MIN_PREMIUM} dhund rahe hain ({check_time_str}, price index {price_index})...")
    print(f"  (Selecting {NUM_OPTIONS_TO_SELECT} closest premiums above threshold for CE and PE)")
    
    # Month names for trading symbol format
    month_names = {
        1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
        7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'
    }
    expiry_dt = datetime.strptime(expiry_date_str, "%Y-%m-%d")
    day = expiry_dt.day
    month = month_names[expiry_dt.month]
    year_short = str(expiry_dt.year)[2:]

    try:
        response = options_api.get_put_call_option_chain(
            instrument_key=NIFTY_INDEX_KEY,
            expiry_date=expiry_date_str
        )
        if not response.data:
            print(" ❌ Option chain data retrieve nahi hua.")
            return [], []
            
        ce_candidates = []
        pe_candidates = []
        
        for contract in response.data:
            strike = contract.strike_price
            
            # CE Check
            if contract.call_options and contract.call_options.instrument_key:
                ce_key = contract.call_options.instrument_key
                ce_premium = get_option_premium_at_time(
                    historical_api, ce_key, target_date_str, check_time_str, price_index
                )
                if ce_premium is not None and ce_premium >= MIN_PREMIUM:
                    ce_symbol = f"NIFTY{year_short}{month}{day:02d}C{int(strike)}"
                    ce_candidates.append({
                        'key': ce_key,
                        'symbol': ce_symbol,
                        'strike': strike,
                        'premium': ce_premium
                    })
            
            # PE Check
            if contract.put_options and contract.put_options.instrument_key:
                pe_key = contract.put_options.instrument_key
                pe_premium = get_option_premium_at_time(
                    historical_api, pe_key, target_date_str, check_time_str, price_index
                )
                if pe_premium is not None and pe_premium >= MIN_PREMIUM:
                    pe_symbol = f"NIFTY{year_short}{month}{day:02d}P{int(strike)}"
                    pe_candidates.append({
                        'key': pe_key,
                        'symbol': pe_symbol,
                        'strike': strike,
                        'premium': pe_premium
                    })
        
        # Sort by premium (ascending) and take the first NUM_OPTIONS_TO_SELECT
        ce_candidates.sort(key=lambda x: x['premium'])
        pe_candidates.sort(key=lambda x: x['premium'])
        
        selected_ce = ce_candidates[:NUM_OPTIONS_TO_SELECT]
        selected_pe = pe_candidates[:NUM_OPTIONS_TO_SELECT]
        
        # Print results
        print(f"\n ✅ Selected {len(selected_ce)} CE options:")
        for i, ce in enumerate(selected_ce, 1):
            print(f"    {i}. Strike {int(ce['strike'])} | Premium: {ce['premium']:.2f}")
        
        print(f"\n ✅ Selected {len(selected_pe)} PE options:")
        for i, pe in enumerate(selected_pe, 1):
            print(f"    {i}. Strike {int(pe['strike'])} | Premium: {pe['premium']:.2f}")
        
        # Convert to tuple format
        ce_tuples = [(ce['key'], ce['symbol']) for ce in selected_ce]
        pe_tuples = [(pe['key'], pe['symbol']) for pe in selected_pe]
        
        return ce_tuples, pe_tuples
        
    except ApiException as e:
        error_details = json.loads(e.body) if e.body else str(e)
        print(f" ❌ Option Chain/Premium fetch karte time API Error: {error_details}")
        return [], []
    except Exception as e:
        print(f" ❌ Key lookup ke time unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return [], []

def filter_candles_by_time(candles, start_time: str, end_time: str, date_str: str):
    """
    Filters candles to only include those within the start_time and end_time on the given date.
    Times in 'HH:MM' format.
    """
    from datetime import datetime
    filtered = []
    ist_offset = timedelta(hours=5, minutes=30)
    ist_tz = timezone(ist_offset)
    
    start_dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=ist_tz)
    end_dt = datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=ist_tz)
    
    for candle in candles:
        ts_str = candle[0]
        if '+05:30' in ts_str:
            candle_dt = datetime.fromisoformat(ts_str)
        else:
            candle_dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00') if 'Z' in ts_str else ts_str)
            if not candle_dt.tzinfo:
                candle_dt = candle_dt.replace(tzinfo=ist_tz)

        if candle_dt.strftime("%Y-%m-%d") != date_str:
            continue
            
        if start_dt <= candle_dt <= end_dt:
            filtered.append(candle)
    
    return filtered


def resample_and_save_data(csv_data, symbol, target_date_str, folder_path, session_tag, short_window):
    """
    Saves the original 1-min data and then resamples/saves 2-min and 3-min data 
    for the specific short_window AND for the full day.
    """
    
    header = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']
    df = pd.DataFrame(csv_data, columns=header)
    
    df['timestamp'] = df['timestamp'].str.replace('T', ' ').str.replace('.000Z', '')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    FULL_DAY_WINDOW = (FULL_DAY_START, FULL_DAY_END)
    TIME_FREQUENCIES = {'1min': '1T', '2min': '2T', '3min': '3T'}

    for window_type, current_window in [('short', short_window), ('full', FULL_DAY_WINDOW)]:
        
        start_time, end_time = current_window
        
        prefix = session_tag.upper()
        if window_type == 'full':
            prefix = f"FULLDAY_{prefix}"
        
        safe_start = start_time.replace(':', '_')
        safe_end = end_time.replace(':', '_')
        
        for name, freq in TIME_FREQUENCIES.items():
            
            if name == '1min':
                df_resampled = df.copy()
            else:
                ohlcv_dict = {
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'oi': 'last'
                }
                df_resampled = df.resample(freq, label='right', closed='right').agg(ohlcv_dict)
            
            df_filtered = df_resampled.between_time(start_time, end_time)
            
            if df_filtered.empty:
                print(f" ❌ {symbol} ke liye {prefix} {name} data filter ke baad empty hai.")
                continue
                
            filename = f"{prefix}_{symbol}_{target_date_str}_{safe_start}-{safe_end}_{name}.csv"
            filepath = os.path.join(folder_path, filename)

            df_filtered.to_csv(filepath, header=True, index=True)
            print(f" ✅ Success! {symbol} ke liye {len(df_filtered)} {prefix} {name} candles {filepath} mein save ho gayi.")


def fetch_and_save_ohlc_data(historical_api, instrument_tuple, target_date_str, session_tag, short_window):
    """
    Fetches historical/intraday 1-minute candle data for the full day (9:15-3:30)
    and passes it to the resampler for all timeframes/durations.
    """
    if not instrument_tuple:
        return
        
    instrument_key, symbol = instrument_tuple
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    use_intraday = (target_date_str == today_str) and is_today_post_close()
    api_method = "Intraday" if use_intraday else "Historical"
    
    print(f"\n- {symbol} ({session_tag}) ke liye 1-minute Full Day data fetch ho raha hai... (Using {api_method} API)")
    try:
        if use_intraday:
            response = historical_api.get_intra_day_candle_data(
                instrument_key=instrument_key,
                interval="1minute",
                api_version=API_VERSION
            )
        else:
            response = historical_api.get_historical_candle_data(
                instrument_key=instrument_key,
                interval="1minute",
                to_date=target_date_str,
                api_version=API_VERSION
            )
        
        if not response.data or not response.data.candles:
            print(f" ❌ {symbol} ke liye koi candle data nahi mila.")
            return
        
        all_candles = response.data.candles
        filtered_candles = filter_candles_by_time(all_candles, FULL_DAY_START, FULL_DAY_END, target_date_str)
        
        if not filtered_candles:
            print(f" ❌ {symbol} ke liye {FULL_DAY_START}-{FULL_DAY_END} window mein koi candle nahi mila.")
            return
            
        actual_date_str = filtered_candles[0][0].split('T')[0]
        
        actual_date = datetime.strptime(actual_date_str, "%Y-%m-%d")
        folder_name = actual_date.strftime("%d %b %Y")
        base_dir = "data"
        full_path = os.path.join(base_dir, folder_name)
        os.makedirs(full_path, exist_ok=True)

        resample_and_save_data(filtered_candles, symbol, actual_date_str, full_path, session_tag, short_window)
        
    except ApiException as e:
        error_details = json.loads(e.body) if e.body else str(e)
        print(f" ❌ {symbol} ke liye Upstox API Error: {error_details}")
    except Exception as e:
        print(f" ❌ Ek unexpected error ho gaya: {e}")
        import traceback
        traceback.print_exc()

def get_next_expiry_date():
    """Finds the next valid weekly Nifty expiry date (Thursday pre-Sep 2025, Tuesday after)."""
    today = date.today()
    cutoff_date = date(2025, 8, 29)
    
    if today <= cutoff_date:
        expiry_weekday = 3
        rule_str = "Thursday"
    else:
        expiry_weekday = 1
        rule_str = "Tuesday"
    
    days_to_expiry = (expiry_weekday - today.weekday() + 7) % 7
    
    if today.weekday() == expiry_weekday:
        if datetime.now().time() < time(15, 30):
            days_to_expiry = 0
        else:
            days_to_expiry = 7
    
    expiry_date = today + timedelta(days=days_to_expiry)
    expiry_date_str = expiry_date.strftime("%Y-%m-%d")
    print(f"\n- Expiry date set ho gayi: {expiry_date_str} (Rule: {rule_str})")
    return expiry_date_str

def get_actual_trading_date(historical_api, requested_date_str):
    """
    Determines actual trading date, preferring Intraday for today.
    """
    print(f"\n- Actual trading date determine kar rahe hain...")
    print(f" Requested date: {requested_date_str}")
    today_str = datetime.now().strftime("%Y-%m-%d")
    use_intraday = (requested_date_str == today_str) and is_today_post_close()
    
    try:
        if use_intraday:
            response = historical_api.get_intra_day_candle_data(
                instrument_key=NIFTY_INDEX_KEY,
                interval="1minute",
                api_version=API_VERSION
            )
        else:
            response = historical_api.get_historical_candle_data(
                instrument_key=NIFTY_INDEX_KEY,
                interval="1minute",
                to_date=requested_date_str,
                api_version=API_VERSION
            )
        
        if response.data and response.data.candles:
            first_candle_date = response.data.candles[0][0].split('T')[0]
            if first_candle_date != requested_date_str:
                print(f" ⚠️ Date correction: API ne {first_candle_date} ka data diya")
                print(f" ✅ Actual trading date: {first_candle_date}")
                return first_candle_date
            else:
                print(f" ✅ Trading date confirmed: {requested_date_str}")
                return requested_date_str
        else:
            print(f" ⚠️ No data received, using requested date: {requested_date_str}")
            return requested_date_str
            
    except Exception as e:
        print(f" ❌ Error determining trading date: {e}")
        print(f" 🔄 Using requested date: {requested_date_str}")
        return requested_date_str

def main():
    """Main function to run the morning-only data collector with two closest premiums ≥100."""
    
    today = datetime.now()
    today_date_str = today.strftime("%Y-%m-%d")
    current_time = today.time()
    
    print(f"--- Morning Two-Premium Data Collector (Min Premium: {MIN_PREMIUM}) ---")
    print(f"Run Time: {today_date_str} {current_time.strftime('%H:%M')}")
    
    if today.weekday() >= 5:
        print(f"\n⚠️⚠️⚠️ WARNING: Aaj {today.strftime('%A')} hai! Market band hai. ⚠️⚠️⚠️")
        print("Weekend pe koi trading data nahi milega.\n")
    
    if current_time < time(15, 45) and today.weekday() < 5:
        print("⚠️ Warning: Data settle hone ke baad (3:45 PM IST ke baad) is script ko chalana best hai.")
        print("Demonstration ke liye continue kar rahe hain.\n")
    
    try:
        historical_api, options_api = setup_api_client()
    except ValueError as e:
        print(e)
        return
    
    expiry_date_str = get_next_expiry_date()
    actual_trading_date = get_actual_trading_date(historical_api, today_date_str)
    
    morning_window = MORNING_SHORT_WINDOW
    
    # --- Morning Two-Premium Selection (9:15 OPEN) ---
    print(f"\n\n=============== Morning Two-Premium Collection ({MORNING_ATM_CHECK_TIME} OPEN) - {actual_trading_date} ===============")
    
    morning_spot, _ = get_nifty_spot_at_time(
        historical_api, actual_trading_date, MORNING_ATM_CHECK_TIME, PRICE_INDEX_MORNING
    )
    if morning_spot:
        print(f" ℹ️ Nifty Spot Price at {MORNING_ATM_CHECK_TIME} (for reference): {morning_spot:.2f}")

    # Get TWO closest CE and TWO closest PE options with premium ≥ MIN_PREMIUM
    ce_tuples, pe_tuples = get_two_closest_premiums_above_threshold(
        historical_api, options_api, actual_trading_date, expiry_date_str, 
        MORNING_ATM_CHECK_TIME, PRICE_INDEX_MORNING
    )
    
    # Fetch data for all selected options
    print(f"\n\n--- Fetching data for selected options ---")
    
    for i, ce_tuple in enumerate(ce_tuples, 1):
        fetch_and_save_ohlc_data(
            historical_api, ce_tuple, actual_trading_date, 
            f"morning_ce{i}", morning_window
        )
    
    for i, pe_tuple in enumerate(pe_tuples, 1):
        fetch_and_save_ohlc_data(
            historical_api, pe_tuple, actual_trading_date, 
            f"morning_pe{i}", morning_window
        )
    
    total_files = (len(ce_tuples) + len(pe_tuples)) * 2 * 3  # options × windows × timeframes
    
    print("\n\n=============================================")
    print(f"Morning Two-Premium Data Collection complete ({actual_trading_date}).")
    print(f"Total {total_files} files saved in 'data/' directory.")
    print(f"- {len(ce_tuples)} CE options × 2 windows × 3 timeframes = {len(ce_tuples)*6} files")
    print(f"- {len(pe_tuples)} PE options × 2 windows × 3 timeframes = {len(pe_tuples)*6} files")
    print("=============================================")

if __name__ == "__main__":
    main()