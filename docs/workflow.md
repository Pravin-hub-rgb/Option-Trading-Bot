# Bot Workflow — Time-Based Flow

## Constants

```
NIFTY_STRIKE_INTERVAL = 50        # Nifty strikes are 50 pts apart
PRESCAN_STRIKE_RANGE  = 25        # +/-25 strikes = +/-1250 pts from spot
PRESCAN_RANGE_PTS     = 1250      # 25 x 50
```

## Path A — Normal Market Open (bot starts before 09:20)

```
09:14:30 --- get_spot()
               NSE_INDEX|Nifty 50 via /v2/market-quote/ltp
               Pre-market session (09:00-09:15) has live indicative value
               Returns the correct "today's open" price

             get_prescan_keys()
               -> get_expiry()        -> today's expiry (same day if expiry day)
               -> fetch_chain(expiry) -> REST /v2/option/chain
               -> filter +/-1250 pts of spot
               -> returns ~100 instrument keys
                  (25 CE ITM + 25 CE OTM + 25 PE ITM + 25 PE OTM)

             start_streaming(prescan_keys=~100 keys)
               -> DataStreamer created in PRESCAN MODE
               -> WebSocket connects
               -> subscribes to all ~100 keys with "full" mode
               -> CandleAggregator created for each key
               -> No components, no strategies, no position managers yet
               -> Only OHLC data is collected (ticks ignored)

09:15:00 --- Market Opens
               Option ticks + OHLC start flowing
               on_message() routes feeds:
                  ~100 prescan keys -> _update_prescan_ohlc() -> prescan aggregators
                  Selected keys (none yet) -> skipped
               Candle data accumulates in prescan aggregators from true 09:15:00

09:15:40 --- fetch_live_strikes()     -> ORIGINAL code (unchanged)
               Fetches chain again
               Reads market_data.ltp from chain response (market is live, data is fresh)
               Filters +/-500 pts of spot
               Filters premium >= 100 -> fallback 80 -> 50
               Picks closest to 100 for CE and PE
               Returns {ce_key, pe_key, ce_strike, pe_strike, ce_premium, pe_premium}

             finalize_selection(ce_key, pe_key, ce_strike, pe_strike)
               -> Pops CandleAggregator for ce_key from _prescan_aggregators
               -> Pops CandleAggregator for pe_key from _prescan_aggregators
               -> Each gets a listener attached (for broadcasting)
               -> Each gets wrapped in a full component:
                  . candle_aggregator  <- SAME OBJECT, has 0-40s of pre-collected OHLC
                  . strategy           <- RedCandleHighBreak (fresh)
                  . position_manager   <- PositionManager (fresh)
                  . trade_logger       <- TradeLogger (fresh)
               -> Remaining ~98 aggregators discarded
               -> _prescan_keys = None (reconnect subscribes only to 2 keys)
               -> streamer.unsubscribe(remaining) drops the 98 non-selected keys
               -> Components are LIVE -> trading begins with full candle history

09:15:40+ -- Strategy Running
               on_message() now routes:
                  CE_KEY -> process_ohlc_candles('CE') + process_tick('CE')
                  PE_KEY -> process_ohlc_candles('PE') + process_tick('PE')
                  All other keys -> skipped
               Stale tick watchdog checks every 30s
               Runs until market_end (15:30)
```

## Path B — Mid-Session Restart (bot starts after 09:20)

```
Bot Starts -> fetch_live_strikes()
               Selects strikes
               start_streaming(ce_key, pe_key)
               -> DataStreamer created NORMALLY (no prescan)
               -> Components created fresh (empty candle history)
               -> First OHLC may be incomplete (mid-candle)
               -> Strategy starts when first OHLC arrives
```

## Key Design Points

| Concept | Why |
|---------|------|
| Pre-subscribe at 09:14:30 | WebSocket needs to be subscribed before 09:15:00 so OHLC from opening auction is captured. Without this, first 30-40s of candle data is missed. |
| +/-25 strikes (+/-1250 pts) | Nifty gaps rarely >800-1000 pts. 100-premium strikes sit 4-12 strikes OTM. +/-25 covers worst gap days while keeping keys ~100. |
| Selection uses ORIGINAL market_data.ltp | At 09:15:40 market is live. Chain's market_data.ltp is fresh. No batch REST LTP needed. |
| Same aggregator object injected | The CandleAggregator that collected OHLC from 09:15:00 is the SAME object placed into the component. No data loss. |
| Unsubscribe after finalize | Drops ~98 non-selected keys from WebSocket feed. Reconnect subscribes only to 2 selected keys. |
| _prescan_keys = None | If WebSocket reconnects after finalize, on_open subscribes only to CE_KEY + PE_KEY. |
| Path B fallback | If prescan keys fail (API error), or finalize fails, system falls back to Path B. |
