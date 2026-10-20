"""NSE trading-day calendar, per circular NSE/CMTR/71775 dated 12 Dec 2025
(trading holidays for calendar year 2026). Dates that fell on a Saturday or
Sunday are absorbed by the weekend check, and Muhurat Trading (Diwali Laxmi
Pujan, Sun 08 Nov 2026) is a special evening session — treated as a holiday
for the normal start guard.
"""

from datetime import date

NSE_HOLIDAYS_2026 = {
    date(2026, 1, 26): "Republic Day",
    date(2026, 3, 3): "Holi",
    date(2026, 3, 26): "Shri Ram Navami",
    date(2026, 3, 31): "Shri Mahavir Jayanti",
    date(2026, 4, 3): "Good Friday",
    date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2026, 5, 1): "Maharashtra Day",
    date(2026, 5, 28): "Bakri Id",
    date(2026, 6, 26): "Muharram",
    date(2026, 9, 14): "Ganesh Chaturthi",
    date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 10, 20): "Dussehra",
    date(2026, 11, 10): "Diwali-Balipratipada",
    date(2026, 11, 24): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2026, 12, 25): "Christmas",
}


def holiday_name(d=None):
    """Name of the market closure on this date, or None when it is a trading day."""
    d = d or date.today()
    if d.weekday() >= 5:
        return "Weekend"
    return NSE_HOLIDAYS_2026.get(d)


def is_trading_day(d=None):
    d = d or date.today()
    return holiday_name(d) is None
