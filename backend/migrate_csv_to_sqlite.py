import csv
import os
import sqlite3
from db import DB_PATH, init_db

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def scan_csvs(directory):
    results = []
    if not os.path.isdir(directory):
        return results
    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if fname.endswith(".csv"):
            results.append(fpath)
        elif os.path.isdir(fpath):
            results.extend(scan_csvs(fpath))
    return results


def parse_and_migrate():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    existing = cursor.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    if existing > 0:
        print(f"Database already has {existing} trades. Skipping migration.")
        conn.close()
        return

    total_trades = 0
    for filepath in sorted(scan_csvs(LOGS_DIR)):
        try:
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                entry = None
                for row in reader:
                    row_type = row.get("type", "").strip()
                    if row_type == "entry":
                        entry = {
                            "symbol": row.get("symbol", ""),
                            "entry_time": row.get("time", ""),
                            "entry_price": _safe_float(row.get("price")),
                            "stop_loss": _safe_float(row.get("stop_loss")),
                        }
                    elif row_type == "exit" and entry:
                        cursor.execute("""
                            INSERT INTO trades (symbol, entry_time, entry_price, stop_loss,
                                                exit_time, exit_price, exit_reason, pnl)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            entry["symbol"],
                            entry["entry_time"],
                            entry["entry_price"],
                            entry["stop_loss"],
                            row.get("time", ""),
                            _safe_float(row.get("price")),
                            row.get("exit_reason", ""),
                            _safe_float(row.get("pnl")),
                        ))
                        total_trades += 1
                        entry = None
        except Exception as e:
            print(f"Error processing {filepath}: {e}")

    conn.commit()
    conn.close()
    print(f"Migrated {total_trades} trades to {DB_PATH}")


def _safe_float(val):
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


if __name__ == "__main__":
    parse_and_migrate()
