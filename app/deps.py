from __future__ import annotations

import os
import hashlib
import secrets

from fastapi import Depends, HTTPException, Request, Response

from app.auth import SESSION_COOKIE, household_for_token, is_admin_email, session_info
from app.db.database import connect, now

GUEST_COOKIE = "dd_guest"


def auth_required() -> bool:
    # Normal app features always support guests, including on hosted deployments.
    return False


def guest_household(conn, token: str | None) -> int | None:
    if not token:
        return None
    row = conn.execute("SELECT household_id FROM guest_sessions WHERE token_hash = ?",
                       (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    return int(row["household_id"]) if row else None


def get_db(request: Request):
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def get_household(request: Request, response: Response, conn=Depends(get_db)) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    household_id = household_for_token(conn, token)
    if household_id is not None:
        return household_id
    household_id = guest_household(conn, request.cookies.get(GUEST_COOKIE))
    if household_id is None:
        guest_token = secrets.token_urlsafe(32)
        household_id = conn.execute(
            "INSERT INTO households (name, prefs_json, created_at) VALUES ('My kitchen', '{}', ?)",
            (now(),)).lastrowid
        conn.execute("INSERT INTO guest_sessions (token_hash, household_id, created_at) VALUES (?, ?, ?)",
                     (hashlib.sha256(guest_token.encode()).hexdigest(), household_id, now()))
        conn.commit()
        secure = os.environ.get("COOKIE_SECURE", "1" if os.environ.get("RAILWAY_ENVIRONMENT") else "0") == "1"
        response.set_cookie(GUEST_COOKIE, guest_token, httponly=True, secure=secure,
                            samesite="lax", max_age=365 * 24 * 3600, path="/")
    if token:
        response.delete_cookie(SESSION_COOKIE, path="/")
    return household_id


def get_current_user(request: Request, conn=Depends(get_db)) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    row = session_info(conn, token)
    if row is None:
        raise HTTPException(401, {"error": "auth", "detail": "not_authenticated"})
    return row["user_id"]


def require_admin(request: Request, conn=Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    row = session_info(conn, token)
    if row is None or not is_admin_email(row["email"]):
        raise HTTPException(403, {"error": "forbidden", "detail": "admin"})
    return row


DbDep = Depends(get_db)
HhDep = Depends(get_household)
UserDep = Depends(get_current_user)
AdminDep = Depends(require_admin)
