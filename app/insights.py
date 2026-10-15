"""Which households' food data may teach Dinnerdesk about how real households eat.

A test household (households.is_test) uses the app like anyone else: its own suggestions,
plans, lists and prep work normally, and its requests count in performance logs and stats.
But its recipes, ingredients, shopping, plans, 👍/👎, prep feedback and Taste Lab swipes are
someone trying things out, not real eating habits. Anything that learns across households
(popularity, "households like yours", shared patterns, reports on what people eat) must use
these so test households never shape what other households see.
"""

from __future__ import annotations

from app.db.database import PgConnection


def real_households_sql(column: str = "household_id") -> str:
    """A WHERE condition keeping rows whose household is real, for cross-household queries."""
    return f"{column} IN (SELECT id FROM households WHERE is_test = 0)"


def is_test_household(db: PgConnection, household_id: int) -> bool:
    row = db.execute("SELECT is_test FROM households WHERE id = ?", (household_id,)).fetchone()
    return bool(row and row["is_test"])
