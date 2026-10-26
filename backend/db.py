import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL,
            exit_time TEXT,
            exit_price REAL,
            exit_reason TEXT,
            pnl REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_time ON trades(entry_time)")
    _migrate_trades(conn)
    conn.commit()
    conn.close()


# Columns added after the first release. Kept additive so old rows stay valid
# (they simply keep NULL until new trades are recorded).
MIGRATION_COLUMNS = [
    ("mfe_points", "REAL"),        # max favourable excursion, in points
    ("mae_points", "REAL"),        # max adverse excursion, in points
    ("sl_rungs_locked", "INTEGER"),  # how many times the trailing SL moved
    # Path detail. MFE alone cannot say whether a runner dipped back below the
    # dip back below the first rung on its way up, which decides whether the
    # hypothetical rule would have cost this trade points.
    ("ticks_seen", "INTEGER"),
    ("peak_tick", "INTEGER"),
    ("bank_touched", "INTEGER"),
    ("first_bank_tick", "INTEGER"),
    ("dips_below_bank", "INTEGER"),
    # The actual per-tick price series, as a JSON array of numbers. The
    # aggregates above answer "did it dip?" but a chart needs the real path to
    # show where the hypothetical stop would have fired. ~200-400 ticks per trade
    # is a couple of KB, which SQLite handles without complaint.
    ("tick_path", "TEXT"),
    # What the strike selector picked, and when. Without this the only record
    # of it was a console line, so once the terminal closed there was no way to
    # tell an option that was genuinely near Rs100 at selection from one that
    # was pushed there by the market moving before the entry filled.
    ("sel_premium", "REAL"),   # premium of THIS option at selection time
    ("sel_tier", "INTEGER"),   # which basket won: 100 / 80 / 50
    ("sel_at", "TEXT"),        # selection timestamp, for drift vs entry_time
    # Which first-rung arithmetic governed this trade, as configured when the
    # entry was logged: 1 = the old charges-only bank, 5 = the bank-first
    # rung. NULL on rows logged before the switch, so "legacy book" rather
    # than a wrong number is the honest label for them.
    ("bank_rung", "INTEGER"),
]


def _migrate_trades(conn):
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(trades)")}
    for name, coltype in MIGRATION_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE trades ADD COLUMN {name} {coltype}")
            print(f"[DB] Migrated trades: added column '{name}'")
