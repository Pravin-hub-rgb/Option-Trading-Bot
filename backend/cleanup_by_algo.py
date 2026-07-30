import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, init_db


def get_group_key(symbol):
    s = symbol.strip().upper()
    if s.endswith(" CE"):
        return "CE"
    if s.endswith(" PE"):
        return "PE"
    if s.startswith("NSE_FO|"):
        token = s.split("|")[1].strip()
        return f"FO_{token}"
    return None


def classify(pnl):
    if pnl > 1.0:
        return "win"
    return "not_win"


def run():
    init_db()
    conn = get_conn()

    trades = conn.execute("""
        SELECT id, entry_time, symbol, pnl
        FROM trades
        ORDER BY entry_time
    """).fetchall()

    grouped = defaultdict(list)
    for t in trades:
        key = get_group_key(t["symbol"])
        if key is None:
            continue
        if t["pnl"] is None:
            continue
        date = t["entry_time"][:10]
        grouped[(date, key)].append((t["id"], t["entry_time"], t["pnl"]))

    to_delete = []
    for (date, key), group in sorted(grouped.items()):
        group.sort(key=lambda x: x[1])

        if len(group) < 2:
            continue

        first_id, first_time, first_pnl = group[0]
        result = classify(first_pnl)

        if result == "win":
            for idx, (tid, ttime, tpnl) in enumerate(group):
                if idx == 0:
                    continue
                to_delete.append((tid, date, side, ttime, tpnl, "2nd+ after win"))
        else:
            for idx, (tid, ttime, tpnl) in enumerate(group):
                if idx < 2:
                    continue
                to_delete.append((tid, date, side, ttime, tpnl, "3rd+ after loss/be"))

    if not to_delete:
        print("No violating trades found.")
        conn.close()
        return

    print(f"Trades to delete ({len(to_delete)}):")
    for tid, date, key, ttime, tpnl, reason in to_delete:
        print(f"  ID={tid:<4} {date} {key:<8}  {ttime[11:19]}  pnl={tpnl:>6.2f}  ({reason})")

    conn.executemany("DELETE FROM trades WHERE id = ?", [(tid,) for tid, _, _, _, _, _ in to_delete])
    conn.commit()

    remaining = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    print(f"\nDeleted {len(to_delete)} trades. {remaining} remaining in DB.")
    conn.close()


if __name__ == "__main__":
    run()
