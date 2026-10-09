from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import SESSION_COOKIE, SESSION_TTL_DAYS, AuthError, is_admin_email, session_info
from app.auth import accept_invite as do_accept_invite
from app.auth import change_password as do_change_password
from app.auth import finish_password_reset, start_password_reset
from app.auth import create_invite as do_create_invite
from app.auth import delete_account as do_delete_account
from app.auth import invite_info as do_invite_info
from app.auth import list_members as do_list_members
from app.auth import login as do_login
from app.auth import logout as do_logout
from app.auth import logout_everywhere as do_logout_everywhere
from app.auth import remove_member as do_remove_member
from app.auth import signup as do_signup
from app.deps import auth_required, DbDep, HhDep, UserDep
from app.mailer import reset_link, send_reset_email

router = APIRouter()

_default_secure = "1" if os.environ.get("RAILWAY_ENVIRONMENT") else "0"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", _default_secure) == "1"

ERROR_MESSAGES = {
    "invalid_email": "Enter a valid email address.",
    "password_too_short": "Password must be at least 8 characters.",
    "email_taken": "An account with that email already exists.",
    "invalid_credentials": "That email or password didn't work.",
    "account_locked": "Too many failed attempts. Try again in a few minutes.",
    "not_authenticated": "Please sign in again.",
    "invite_invalid": "This invite link isn't valid.",
    "invite_used": "This invite has already been used.",
    "invite_expired": "This invite has expired -- ask for a new one.",
    "last_member": "You can't remove the last member of a household.",
    "not_found": "That member wasn't found.",
    "reset_invalid": "This reset link isn't valid or was already used. Ask for a new one.",
    "reset_expired": "This reset link has expired. Ask for a new one.",
    "wrong_password": "That password isn't right.",
}


class ForgotPasswordBody(BaseModel):
    email: str


class ResetPasswordBody(BaseModel):
    token: str
    password: str


class SignupBody(BaseModel):
    email: str
    password: str
    household_name: str = "My household"


class LoginBody(BaseModel):
    email: str
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class DeleteAccountBody(BaseModel):
    password: str


class AcceptInviteBody(BaseModel):
    token: str
    email: str
    password: str


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        path="/",
    )


def _auth_error(e: AuthError, status: int) -> HTTPException:
    return HTTPException(
        status,
        {
            "error": "auth",
            "detail": e.detail,
            "message": ERROR_MESSAGES.get(e.detail, "Something went wrong."),
        },
    )


@router.post("/auth/signup")
def signup(body: SignupBody, response: Response, conn=DbDep):
    try:
        token = do_signup(conn, body.email, body.password, body.household_name)
    except AuthError as e:
        raise _auth_error(e, 400)
    _set_session_cookie(response, token)
    return {"ok": True}


@router.post("/auth/login")
def login(body: LoginBody, response: Response, conn=DbDep):
    try:
        token = do_login(conn, body.email, body.password)
    except AuthError as e:
        status = 423 if e.detail == "account_locked" else 401
        raise _auth_error(e, status)
    _set_session_cookie(response, token)
    return {"ok": True}


@router.post("/auth/logout")
def logout(request: Request, response: Response, conn=DbDep):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        do_logout(conn, token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.post("/auth/logout-everywhere")
def logout_everywhere(response: Response, conn=DbDep, user_id=UserDep):
    do_logout_everywhere(conn, user_id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


<<<<<<< HEAD
@router.get("/support")
def support():
    """Public contact details for the /support page. Set SUPPORT_EMAIL on the server."""
    return {"email": (os.environ.get("SUPPORT_EMAIL") or "").strip()}
=======
@router.post("/auth/delete-account")
def delete_account(body: DeleteAccountBody, response: Response, conn=DbDep, user_id=UserDep):
    """Delete the signed-in account (#65). Asks for the password again so a borrowed, unlocked
    phone can't do it. Signs out everywhere: every session belonged to the deleted account."""
    try:
        household_deleted = do_delete_account(conn, user_id, body.password)
    except AuthError as e:
        raise _auth_error(e, 400)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True, "household_deleted": household_deleted}
>>>>>>> origin/fix/65-account-deletion


@router.get("/auth/status")
def status(request: Request, conn=DbDep):
    token = request.cookies.get(SESSION_COOKIE)
    row = session_info(conn, token)
    email = row["email"] if row else None
    return {
        "required": auth_required(),
        "authenticated": row is not None,
        "email": email,
        "admin": is_admin_email(email),
    }


@router.get("/auth/me")
def me(request: Request, conn=DbDep):
    token = request.cookies.get(SESSION_COOKIE)
    row = session_info(conn, token)
    if row is None:
        raise HTTPException(401, {"error": "auth", "detail": "not_authenticated"})
    return {
        "household_id": row["household_id"],
        "email": row["email"],
        "admin": is_admin_email(row["email"]),
    }


@router.post("/auth/change-password")
def change_password(body: ChangePasswordBody, response: Response, conn=DbDep, user_id=UserDep):
    try:
        do_change_password(conn, user_id, body.current_password, body.new_password)
    except AuthError as e:
        raise _auth_error(e, 400)
    row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    token = do_login(conn, row["email"], body.new_password)
    _set_session_cookie(response, token)
    return {"ok": True}


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordBody, conn=DbDep):
    # Same answer whether or not the email has an account.
    email = (body.email or "").strip().lower()
    token = start_password_reset(conn, email)
    if token:
        send_reset_email(email, reset_link(token))
    return {"ok": True}


@router.post("/auth/reset-password")
def reset_password(body: ResetPasswordBody, response: Response, conn=DbDep):
    try:
        token = finish_password_reset(conn, body.token, body.password)
    except AuthError as e:
        raise _auth_error(e, 400)
    _set_session_cookie(response, token)
    return {"ok": True}


@router.post("/household/invites")
def create_invite(conn=DbDep, household_id=HhDep, user_id=UserDep):
    token = do_create_invite(conn, household_id, user_id)
    return {"token": token, "expires_in_days": 7}


@router.get("/household/invites/{token}")
def preview_invite(token: str, conn=DbDep):
    try:
        row = do_invite_info(conn, token)
    except AuthError as e:
        raise _auth_error(e, 404 if e.detail == "invite_invalid" else 410)
    return {"household_name": row["household_name"]}


@router.post("/household/accept-invite")
def accept_invite(body: AcceptInviteBody, response: Response, conn=DbDep):
    try:
        token = do_accept_invite(conn, body.token, body.email, body.password)
    except AuthError as e:
        raise _auth_error(e, 400)
    _set_session_cookie(response, token)
    return {"ok": True}


@router.get("/household/members")
def members(conn=DbDep, household_id=HhDep):
    rows = do_list_members(conn, household_id)
    return {
        "members": [
            {"id": r["id"], "email": r["email"], "joined_at": r["created_at"]} for r in rows
        ]
    }


@router.delete("/household/members/{target_user_id}")
def remove_member(target_user_id: int, conn=DbDep, household_id=HhDep, user_id=UserDep):
    if target_user_id == user_id:
        raise HTTPException(
            400,
            {
                "error": "auth",
                "detail": "cant_remove_self",
                "message": "Use 'Sign out' to leave, not remove.",
            },
        )
    try:
        do_remove_member(conn, household_id, target_user_id)
    except AuthError as e:
        raise _auth_error(e, 400)
    return {"ok": True}
