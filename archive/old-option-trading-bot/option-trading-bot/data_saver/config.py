# --- config.py ---
# Central place for all API keys, tokens, and strategy constants.

# --- API Credentials and Setup (UPDATED) ---
# NOTE: Replace these placeholders with your actual Upstox details.
API_KEY = "e6b14cad-cea4-4062-a244-bb885316c93b"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI0SENZTkYiLCJqdGkiOiI2OTNiODg2NTcxNzY2OTNkNjFhNDI0MGYiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2NTUwOTIyMSwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY1NTc2ODAwfQ.Dm1Wy48vEq-Qpe3WdxlqN9VcitDSLiNTa22C18FQpNw"

NIFTY_INDEX_KEY = "NSE_INDEX|Nifty 50" # Upstox instrument key for Nifty 50 Spot
API_VERSION = "2.0"

# --- Strategy Configuration (UPDATED) ---
TARGET_PREMIUM = 100
# Morning Session ATM Check (9:16 AM Open Price - to use the first complete candle)
MORNING_ATM_CHECK_TIME = '09:16'
# Evening Session ATM Check (3:25 PM Close Price - for stable EOD data)
EVENING_ATM_CHECK_TIME = '15:25'

# Index for OHLCV array: 0=Timestamp, 1=Open, 2=High, 3=Low, 4=Close, 5=Volume, 6=OI
# We use Open price (1) for morning selection and Close price (4) for evening selection.
PRICE_INDEX_MORNING = 1
PRICE_INDEX_EVENING = 4 

# --- Time Window Definitions ---
FULL_DAY_START = '09:15'
FULL_DAY_END = '15:30'
MORNING_SHORT_WINDOW = (FULL_DAY_START, '10:00')
EVENING_SHORT_WINDOW = ('15:00', FULL_DAY_END)
BASE_OUTPUT_DIR = "Nifty_Data_Collector" # Main folder for all output files