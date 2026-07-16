# ========== UPSTOX CREDENTIALS ==========
API_KEY = "e6b14cad-cea4-4062-a244-bb885316c93b"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI0SENZTkYiLCJqdGkiOiI2YTU4NTA0MGQzOTRlYTE4OTNjNjUwZTMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc4NDE3MjYwOCwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzg0MjM5MjAwfQ.rP7vEket8hJgMZ7g6DGetiRHNoMr7sv3RSVVkco5Awg"

# ========== TIMING ==========
MARKET_START = "09:15"              # Market open
MARKET_END = "15:30"                # Market close
STRATEGY_START = "09:15"            # Begin strategy execution
ENTRY_WINDOW_END = "15:00"          # No new entries after this

# ========== LIVE PREMIUM SELECTION TIMING ==========
MARKET_OPEN_DELAY = 40  # Seconds after market open for live premium selection

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

#taskkill /f /im python.exe

# ========== LIVE PREMIUM SELECTION TIMING ========== 
MARKET_OPEN_DELAY = 40  # Seconds after market open for live premium selection
