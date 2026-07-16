# --- get_todays_data.py (Full Day Data Collection) ---

import upstox_client
from datetime import datetime, timedelta, date, time, timezone
import csv
import os
import json
from config import (
    API_KEY,
    ACCESS_TOKEN,
    NIFTY_INDEX_KEY,
    API_VERSION,
    MORNING_ATM_CHECK_TIME,
    EVENING_ATM_CHECK_TIME,
    PRICE_INDEX_MORNING,
    PRICE_INDEX_EVENING
)
from upstox_client.rest import ApiException

# --- Strategy Configuration ---
TARGET_PREMIUM = 100
MAX_PREMIUM_DIFFERENCE = 100

# --- Full Day Configuration ---
FULL_DAY_START_TIME = '09:15'
FULL_DAY_END_TIME = '15:30'

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
    Fetches Nifty Index 1-min data. Used for logging/reference only in fixed-premium strategy.
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

def get_closest_premium_instrument_keys(historical_api, options_api, target_date_str, expiry_date_str, check_time_str, price_index):
    """
    Finds the CE and PE instrument keys whose premium is closest to TARGET_PREMIUM (e.g., 100)
    at the specified time (check_time_str).
    """
    print(f"\n- Options with premium closest to {TARGET_PREMIUM} dhund rahe hain ({check_time_str}, price index {price_index})...")
    
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
            return None, None
            
        best_ce = {'key': None, 'symbol': None, 'strike': None, 'diff': float('inf'), 'premium': None}
        best_pe = {'key': None, 'symbol': None, 'strike': None, 'diff': float('inf'), 'premium': None}
        
        for contract in response.data:
            strike = contract.strike_price
            
            # CE Check
            if contract.call_options and contract.call_options.instrument_key:
                ce_key = contract.call_options.instrument_key
                ce_premium = get_option_premium_at_time(
                    historical_api, ce_key, target_date_str, check_time_str, price_index
                )
                if ce_premium is not None:
                    ce_diff = abs(ce_premium - TARGET_PREMIUM)
                    if ce_diff < best_ce['diff'] and ce_premium > 1:
                        best_ce['key'] = ce_key
                        best_ce['strike'] = strike
                        best_ce['diff'] = ce_diff
                        best_ce['premium'] = ce_premium
                        best_ce['symbol'] = f"NIFTY{year_short}{month}{day:02d}C{int(strike)}"
            
            # PE Check
            if contract.put_options and contract.put_options.instrument_key:
                pe_key = contract.put_options.instrument_key
                pe_premium = get_option_premium_at_time(
                    historical_api, pe_key, target_date_str, check_time_str, price_index
                )
                if pe_premium is not None:
                    pe_diff = abs(pe_premium - TARGET_PREMIUM)
                    if pe_diff < best_pe['diff'] and pe_premium > 1:
                        best_pe['key'] = pe_key
                        best_pe['strike'] = strike
                        best_pe['diff'] = pe_diff
                        best_pe['premium'] = pe_premium
                        best_pe['symbol'] = f"NIFTY{year_short}{month}{day:02d}P{int(strike)}"
        
        # Final result printing
        ce_tuple, pe_tuple = None, None
        if best_ce['key']:
            ce_tuple = (best_ce['key'], best_ce['symbol'])
            print(f" ✅ Best CE: Strike {int(best_ce['strike'])} (Premium: {best_ce['premium']:.2f}, Diff: {best_ce['diff']:.2f})")
        else:
            print(" ❌ Closest CE premium (~100) nahi mila (Skipping selection).")
            
        if best_pe['key']:
            pe_tuple = (best_pe['key'], best_pe['symbol'])
            print(f" ✅ Best PE: Strike {int(best_pe['strike'])} (Premium: {best_pe['premium']:.2f}, Diff: {best_pe['diff']:.2f})")
        else:
            print(" ❌ Closest PE premium (~100) nahi mila (Skipping selection).")
            
        return ce_tuple, pe_tuple
        
    except ApiException as e:
        error_details = json.loads(e.body) if e.body else str(e)
        print(f" ❌ Option Chain/Premium fetch karte time API Error: {error_details}")
        return None, None
    except Exception as e:
        print(f" ❌ Key lookup ke time unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def filter_candles_by_time(candles, start_time: str, end_time: str, date_str: str):
    """
    Filters candles to only include those within the start_time and end_time on the given date.
    Times in 'HH:MM' format.
    """
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
        if start_dt <= candle_dt <= end_dt:
            filtered.append(candle)
    
    return filtered

def fetch_and_save_ohlc_data(historical_api, instrument_tuple, target_date_str, session_tag, time_window):
    """
    Fetches historical/intraday candle data, filters to time window, and saves to CSV.
    time_window: tuple (start_time 'HH:MM', end_time 'HH:MM') e.g., ('09:15', '15:30')
    """
    if not instrument_tuple:
        return
        
    instrument_key, symbol = instrument_tuple
    start_time, end_time = time_window
    today_str = datetime.now().strftime("%Y-%m-%d")
    use_intraday = (target_date_str == today_str) and is_today_post_close()
    api_method = "Intraday" if use_intraday else "Historical"
    
    print(f"\n- {symbol} ({session_tag} - {start_time}-{end_time}) ke liye 1-minute data fetch ho raha hai... (Using {api_method} API)")
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
        # Filter to time window
        filtered_candles = filter_candles_by_time(all_candles, start_time, end_time, target_date_str)
        
        if not filtered_candles:
            print(f" ❌ {symbol} ke liye {start_time}-{end_time} window mein koi candle nahi mila.")
            return
        
        header = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']
        csv_data = filtered_candles
        
        actual_date_str = csv_data[0][0].split('T')[0]
        actual_date = datetime.strptime(actual_date_str, "%Y-%m-%d")
        folder_name = actual_date.strftime("%d %b %Y")
        base_dir = "data"
        full_path = os.path.join(base_dir, folder_name)
        
        os.makedirs(full_path, exist_ok=True)
        safe_start = start_time.replace(':', '_')
        safe_end = end_time.replace(':', '_')
        filename = f"{session_tag.upper()}_{symbol}_{actual_date_str}_{safe_start}-{safe_end}.csv"
        filepath = os.path.join(full_path, filename)
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(csv_data)
        print(f" ✅ Success! {symbol} ke liye {len(csv_data)} candles ({start_time}-{end_time}) {filepath} mein save ho gayi.")
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
    """Determines actual trading date, preferring Intraday for today."""
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
    """Main function to run the full day data collector based on closest premium."""
    
    today = datetime.now()
    today_date_str = today.strftime("%Y-%m-%d")
    current_time = today.time()
    
    print(f"--- Full Day Fixed-Premium Data Collector (Run Time: {today_date_str} {current_time.strftime('%H:%M')}) ---")
    
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
    
    # --- Strike Selection at 9:15 AM (OPEN) ---
    print(f"\n\n=============== Strike Selection at {MORNING_ATM_CHECK_TIME} (OPEN) - {actual_trading_date} ===============")
    
    morning_spot, _ = get_nifty_spot_at_time(
        historical_api, actual_trading_date, MORNING_ATM_CHECK_TIME, PRICE_INDEX_MORNING
    )
    if morning_spot:
        print(f" ℹ️ Nifty Spot Price at {MORNING_ATM_CHECK_TIME} (for reference): {morning_spot:.2f}")

    ce_tuple, pe_tuple = get_closest_premium_instrument_keys(
        historical_api, options_api, actual_trading_date, expiry_date_str, MORNING_ATM_CHECK_TIME, PRICE_INDEX_MORNING
    )
    
    # --- Fetch FULL DAY data (9:15 to 3:30) ---
    full_day_window = (FULL_DAY_START_TIME, FULL_DAY_END_TIME)
    print(f"\n\n=============== Full Day Data Collection ({FULL_DAY_START_TIME} - {FULL_DAY_END_TIME}) ===============")
    fetch_and_save_ohlc_data(historical_api, ce_tuple, actual_trading_date, "ce_fullday", full_day_window)
    fetch_and_save_ohlc_data(historical_api, pe_tuple, actual_trading_date, "pe_fullday", full_day_window)
    
    print("\n\n=============================================")
    print(f"Full Day Data Collection complete ({actual_trading_date}).")
    print(f"2 Files created: 1 CE + 1 PE")
    print(f"Strikes selected based on {MORNING_ATM_CHECK_TIME} premium (~{TARGET_PREMIUM})")
    print(f"Data time window: {FULL_DAY_START_TIME} - {FULL_DAY_END_TIME}")
    print(f"Files saved in 'data/' directory.")
    print("=============================================")

if __name__ == "__main__":
    main()