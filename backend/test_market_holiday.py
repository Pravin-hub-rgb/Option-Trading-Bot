"""Market-holiday guard, motivated by Tue 20 Oct 2026 (Dussehra): the user
hit Start, the bot sat silent for hours and nothing explained WHY. No ticks
ever arrived, and the old watchdog only fires when ticks STOP.

Covers: the calendar, bot_manager's start-time refusal, and - the gap the
user called out - the scheduler saying so when zero ticks arrive at all.
"""

import settings_db
from datetime import date, datetime

import pytz
import requests

IST = pytz.timezone("Asia/Kolkata")

from nse_holidays import NSE_HOLIDAYS_2026, holiday_name, is_trading_day

failures = []


def check(label, cond):
    if cond:
        print(f"  ok   {label}")
    else:
        failures.append(label)
        print(f"  FAIL {label}")


# -- 1. Calendar -------------------------------------------------------------
check("20 Oct 2026 is Dussehra", holiday_name(date(2026, 10, 20)) == "Dussehra")
check("20 Oct 2026 is not a trading day", not is_trading_day(date(2026, 10, 20)))
check("21 Oct 2026 is a trading day", is_trading_day(date(2026, 10, 21)))
check("10 Nov 2026 is Diwali-Balipratipada",
      holiday_name(date(2026, 11, 10)) == "Diwali-Balipratipada")
check("24 Oct 2026 (Sat) is Weekend", holiday_name(date(2026, 10, 24)) == "Weekend")
check("25 Oct 2026 (Sun) is Weekend", holiday_name(date(2026, 10, 25)) == "Weekend")
check("15 holidays in the 2026 circular", len(NSE_HOLIDAYS_2026) == 15)
check("26 Jan 2026 is Republic Day", holiday_name(date(2026, 1, 26)) == "Republic Day")
check("25 Dec 2026 is Christmas", holiday_name(date(2026, 12, 25)) == "Christmas")

# -- 2. bot_manager.start() refuses on a holiday, before spawning threads ----
import bot_manager as bm


class HolidayNoon(datetime):
    @classmethod
    def now(cls, tz=None):
        aware = datetime(2026, 10, 20, 10, 0, 0, tzinfo=IST)
        return aware if tz else aware.replace(tzinfo=None)


class FakeResponse:
    status_code = 200


requests.get = lambda *a, **k: FakeResponse()
settings_db.get_setting = lambda key: "fake-token"

saved_datetime, saved_holiday = bm.datetime, bm.holiday_name
try:
    mgr = bm.BotManager(live_feed_server=None)
    bm.datetime, bm.holiday_name = HolidayNoon, lambda d: "Dussehra"
    result = mgr.start()
    msg = result.get("message", "")
    check("start() refuses with error status", result.get("status") == "error")
    check("refusal names the holiday", "market holiday (Dussehra)" in msg)
    check("refusal says no ticks will come", "no ticks will come" in msg)
    check("start() spawns no thread on refusal", mgr.bot_thread is None)
    check("start() leaves running=False on refusal", mgr.running is False)
finally:
    bm.datetime, bm.holiday_name = saved_datetime, saved_holiday

# -- 3. Zero-ticks watchdog: announces, and auto-stops on a holiday ----------
import scheduler as sch
import nse_holidays
from scheduler import TradingScheduler


class StalledClock(datetime):
    """now(IST) is 10:10 on 20 Oct 2026 - a holiday."""
    @classmethod
    def now(cls, tz=None):
        aware = datetime(2026, 10, 20, 10, 10, 0, tzinfo=IST)
        return aware if tz else aware.replace(tzinfo=None)


saved_holiday_fn = nse_holidays.holiday_name
saved_sch_datetime = sch.datetime

try:
    def make_scheduler(started_at, holiday_today):
        class StubStreamer:
            def run(self):
                pass

            def close(self):
                pass

        s = TradingScheduler(lambda *a, **k: StubStreamer())
        s.messages = []
        s.log = s.messages.append
        s._stream_started_at = started_at
        s._no_ticks_last = None
        saved_for_this_case = nse_holidays.holiday_name
        nse_holidays.holiday_name = (lambda d: holiday_today) if holiday_today else (lambda d: None)
        return s

    sch.datetime = StalledClock

    s_quiet = make_scheduler(datetime(2026, 10, 20, 10, 9, 0, tzinfo=IST), None)
    check("under 3 min stalled -> quiet", s_quiet._report_no_ticks() is False
          and s_quiet.messages == [])

    s_stop = make_scheduler(datetime(2026, 10, 20, 10, 0, 0, tzinfo=IST), "Dussehra")
    check("holiday + no ticks in 10 min -> stop requested",
          s_stop._report_no_ticks() is True)
    joined = " | ".join(s_stop.messages)
    check("announcement names Dussehra", "Dussehra" in joined)
    check("announcement says no ticks", "No ticks" in joined)

    s_wait = make_scheduler(datetime(2026, 10, 20, 10, 0, 0, tzinfo=IST), None)
    check("stalled on a trading day -> keep waiting",
          s_wait._report_no_ticks() is False)
    check("stall announced once", any(
        "No ticks received in 10 min" in m for m in s_wait.messages))

    check("repeat inside 10-min window throttled", len(s_wait.messages) == 1
          and s_wait._report_no_ticks() is False
          and len(s_wait.messages) == 1)
finally:
    nse_holidays.holiday_name = saved_holiday_fn
    sch.datetime = saved_sch_datetime

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED: {failures}")
    raise SystemExit(1)

print("ALL CHECKS PASSED")
