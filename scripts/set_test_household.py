"""Mark the household of an account as a test household, or back to a real one.

A test household works normally and counts in performance logs and stats, but its food data is
left out of anything that learns across households (see app/insights.py). The server adds the
is_test column when it starts, so run this after the change has deployed.

    python scripts/set_test_household.py tester@example.com          # mark as test
    python scripts/set_test_household.py tester@example.com --real   # back to a real household
    railway ssh -s dinnerdesk -- 'cd /app && .venv/bin/python scripts/set_test_household.py tester@example.com'
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import connect, transaction  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--real"]
    if len(args) != 1:
        raise SystemExit("usage: python scripts/set_test_household.py EMAIL [--real]")
    is_test = 0 if "--real" in sys.argv[1:] else 1
    conn = connect()
    try:
        row = conn.execute(
            """SELECT h.id, h.name, (SELECT COUNT(*) FROM users m WHERE m.household_id = h.id) AS members
               FROM users u JOIN households h ON h.id = u.household_id
               WHERE lower(u.email) = lower(?)""",
            (args[0].strip(),),
        ).fetchone()
        if not row:
            raise SystemExit(f"No account for {args[0]}")
        with transaction(conn):
            conn.execute("UPDATE households SET is_test = ? WHERE id = ?", (is_test, row["id"]))
        kind = "a test household" if is_test else "a real household"
        print(f"Household {row['id']} ({row['name']}, {row['members']} member(s)) is now {kind}.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
