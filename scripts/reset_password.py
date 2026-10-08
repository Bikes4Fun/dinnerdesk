"""Set a new password for an account, for when it's forgotten (no email reset yet).

Uses the same database as the server: PostgreSQL configured by DATABASE_URL.
Keeps the account's household, plans, pantry and recipes. Clears any lockout and signs the account
out everywhere.

    python scripts/reset_password.py you@example.com
    railway run python scripts/reset_password.py you@example.com    # production on Railway
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password  # noqa: E402
from app.db.database import connect, transaction  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/reset_password.py EMAIL")
    email = sys.argv[1].strip().lower()
    conn = connect()
    where = "PostgreSQL (DATABASE_URL)"
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        found = [r["email"] for r in conn.execute("SELECT email FROM users ORDER BY id").fetchall()]
        raise SystemExit(f"No account for {email} in {where}. Accounts: {', '.join(found) or 'none'}")

    password = getpass.getpass("New password (8+ characters): ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    if getpass.getpass("Type it again: ") != password:
        raise SystemExit("Passwords didn't match.")

    with transaction(conn):
        conn.execute(
            "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (hash_password(password), row["id"]),
        )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
    conn.close()
    print(f"Password updated for {email} in {where}. Sign in with the new password.")


if __name__ == "__main__":
    main()
