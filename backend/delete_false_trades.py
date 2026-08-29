import csv
import os
import sys
import tempfile
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import DB_PATH, get_conn, init_db

ARCHIVE_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "archive", "logs"
)

CUTOFF_TIME = "11:00:00"


def delete_from_db():
    init_db()
    conn = get_conn()
    cursor = conn.execute(
        "DELETE FROM trades WHERE substr(entry_time, 12) > ?",
        (CUTOFF_TIME,)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"[DB] Deleted {deleted} trades from {DB_PATH}")
    return deleted


def scan_csvs(directory):
    results = []
    if not os.path.isdir(directory):
        return results
    for entry in os.listdir(directory):
        fpath = os.path.join(directory, entry)
        if entry.endswith(".csv"):
            results.append(fpath)
        elif os.path.isdir(fpath):
            results.extend(scan_csvs(fpath))
    return results


def time_str_after_11am(time_field):
    time_field = (time_field or "").strip()
    dt_part = time_field.split(".")[0]
    if " " in dt_part:
        t = dt_part.split(" ")[1]
    else:
        t = dt_part
    return t > CUTOFF_TIME


def delete_from_csvs():
    total_removed = 0
    for filepath in sorted(scan_csvs(ARCHIVE_LOGS_DIR)):
        removed = _process_csv(filepath)
        if removed:
            print(f"  [CSV] Removed {removed} trades from {os.path.basename(filepath)}")
        total_removed += removed
    return total_removed


def _process_csv(filepath):
    with open(filepath, "r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    kept = []
    removed = 0
    i = 0
    while i < len(rows):
        row = rows[i]
        row_type = (row.get("type") or "").strip().lower()

        if row_type == "entry":
            entry_time = row.get("time", "")
            if time_str_after_11am(entry_time):
                removed += 1
                i += 1
                if i < len(rows):
                    next_type = (rows[i].get("type") or "").strip().lower()
                    if next_type == "exit":
                        i += 1
                continue
            kept.append(row)
        else:
            kept.append(row)
        i += 1

    if removed == 0:
        return 0

    fd, tmp_path = tempfile.mkstemp(suffix=".csv", dir=os.path.dirname(filepath))
    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(kept)
        shutil.move(tmp_path, filepath)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return removed


if __name__ == "__main__":
    print(f"Deleting trades entered after {CUTOFF_TIME}...\n")

    db_count = delete_from_db()
    csv_count = delete_from_csvs()

    print(f"\nDone. Removed {db_count} trades from DB, {csv_count} from CSVs.")
