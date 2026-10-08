from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request

from app.auth import SESSION_COOKIE, household_for_token, is_admin_email, session_info
from app.db.database import connect

GUEST_HOUSEHOLD_ID = 1


def auth_required() -> bool:
    raw = os.environ.get("AUTH_REQUIRED")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes"}


def get_db(request: Request):
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def get_household(request: Request, conn=Depends(get_db)) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    household_id = household_for_token(conn, token)
    if household_id is not None:
        return household_id
    if token or auth_required():
        raise HTTPException(401, {"error": "auth", "detail": "not_authenticated"})
    return GUEST_HOUSEHOLD_ID


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
