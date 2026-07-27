# ========== UPSTOX CREDENTIALS ==========
API_KEY = "e6b14cad-cea4-4062-a244-bb885316c93b"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI0SENZTkYiLCJqdGkiOiI2OTgyYjg3NTMyMjg1MDBkOTNjY2ZjMzkiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc3MDE3NDU4MSwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzcwMjQyNDAwfQ.Lpf3FzIaRs2KZtOnoldkuQ7E8O-eHEFkTlqhoLD5nMo"

# ========== TIMING ==========
STRIKE_SELECTION_START = "09:09:00"
STRIKE_SELECTION_END = "09:14:30"
CONNECTION_START = "09:14:30"      # Start connecting to WebSocket
STRATEGY_START = "09:15:00"        # Begin strategy execution
ENTRY_WINDOW_END = "15:00:00"      # No new entries after this
MARKET_START = "09:15"              # Market open (kept for compatibility)
MARKET_END = "15:30"                # Market close

# ========== STRIKE SELECTION ==========
TARGET_PREMIUM_MIN = 90             # ₹90
TARGET_PREMIUM_MAX = 110            # ₹110
TARGET_PREMIUM_IDEAL = 100          # Ideal ₹100
ATM_OFFSET_RANGE = 5                # Check ATM ± 5 strikes (11 total)
STRIKE_STEP = 50                    # NIFTY strikes are 50 points apart

# ========== GAP-ADJUSTED STRIKE SHIFT (NEW!) ==========
# These thresholds determine how many strikes to shift based on gap size
GAP_SHIFT_THRESHOLDS = {
    'extreme_up': 300,         # Gap ≥ +300 → Shift +6 strikes (+300 points)
    'large_up': 200,           # Gap ≥ +200 → Shift +4 strikes (+200 points)
    'medium_up_high': 150,     # Gap ≥ +150 → Shift +3 strikes (+150 points)
    'medium_up_low': 100,      # Gap ≥ +100 → Shift +2 strikes (+100 points)
    'small_up': 60,            # Gap ≥ +60  → Shift +1 strike  (+50 points)
    'small_down': -60,         # Gap ≤ -60  → Shift -1 strike  (-50 points)
    'medium_down_high': -100,  # Gap ≤ -100 → Shift -2 strikes (-100 points)
    'medium_down_low': -150,   # Gap ≤ -150 → Shift -3 strikes (-150 points)
    'large_down': -200,        # Gap ≤ -200 → Shift -4 strikes (-200 points)
    'extreme_down': -300       # Gap ≤ -300 → Shift -6 strikes (-300 points)
}

# Fallback premium range for extreme gap days (>300 points)
EXTREME_GAP_THRESHOLD = 300        # Consider gap "extreme" if |gap| > 300
FALLBACK_PREMIUM_MIN = 70          # Widen to ₹70 if extreme gap
FALLBACK_PREMIUM_MAX = 130         # Widen to ₹130 if extreme gap

# ========== STRATEGY PARAMETERS ==========
MAX_WAIT_CANDLES = 2                # Timeout after 2 candles without breakout
ALLOW_REFERENCE_SHIFT = True        # Shift to newer red candle if appears

# ========== RISK MANAGEMENT ==========
INITIAL_SL_POINTS = 5               # Initial stop loss: entry - 5 points
TRAILING_TRIGGER = 5                # Move to cost-to-cost after +5 profit
TRAILING_STEP = 5                   # Then trail by 5 points for each +5 milestone

# ========== TRADE LIMITS (PER SIDE - CE and PE independent) ==========
STOP_AFTER_FIRST_WIN = True         # Stop trading that side after first win
MAX_TRADES_PER_SIDE = 2             # Max 2 trades per side if first loses

# ========== LOGGING ==========
LOG_LEVEL = "VERBOSE"               # VERBOSE or MINIMAL
LOG_EVERY_TICK = False              # Log every tick (for debugging, usually False)
LOG_CANDLE_UPDATES = True           # Log when candles close

# ========== DISCONNECTION HANDLING ==========
RECONNECT_ATTEMPTS = 3              # Number of reconnection attempts
RECONNECT_DELAY_SECONDS = 5         # Delay between reconnection attempts
ALERT_ON_DISCONNECT = True          # Print loud alerts on disconnect

# ========== CANDLE CONVENTION ==========
CANDLE_TIMESTAMP_STYLE = "next_minute"  # Industry standard: 9:15-9:16 candle labeled as 9:16