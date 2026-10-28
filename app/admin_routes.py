"""Admin review pages: plain HTML with the data filled in on the server. Admins only.

Each page in app/admin_pages has `/*DATA*/null` where its data goes. Notes and decisions made on
a page save in that browser, and the page's Export button downloads them.
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app import auth
from app.assets import catalog_dir
from app.db.database import PgConnection, now
from app.deps import AdminDep, DbDep
from app.domain.recipe_photos import usable_photo
from app.mailer import mail_ready, reset_link, send_reset_email, send_verify_email, verify_link

router = APIRouter()
PAGES = Path(__file__).resolve().parent / "admin_pages"
VOCABULARY = Path(__file__).resolve().parent / "domain" / "recipe_tag_vocabulary.json"

# Same wording the app shows (web/src/pages/Prep.jsx PREP_REASONS).
PREP_REASONS = {
    "day_of": "Better done day-of",
    "kept_badly": "Didn't keep well",
    "too_small": "Too small to bother",
    "prep_differently": "Prep it differently",
    "not_prep": "Not a prep step",
    "missing": "Missing prep step",
}


def _page(name: str, data: dict) -> HTMLResponse:
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    html = (PAGES / f"{name}.html").read_text().replace("/*DATA*/null", payload)
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


def _has_account_sql(alias: str) -> str:
    return f"EXISTS (SELECT 1 FROM users u WHERE u.household_id = {alias}.household_id)"


def _variant_review() -> dict:
    # No similar-recipe scan on the server yet, so there's nothing to review.
    return {"groups": [], "source": {"groups": []}}


def _prep_feedback(db: PgConnection) -> dict:
    votes = [
        {
            "id": f"{r['household_id']}:{r['recipe_id']}:{r['step_key']}",
            "prep_task": None,
            "recipe_steps": None,
            "up": r["rating"] > 0,
            "missing": r["reason"] == "missing",
            "task": r["category"] or "(no task)",
            "step": r["step_text"] or "",
            "recipe": r["recipe_name"] or f"recipe {r['recipe_id']}",
            "recipe_url": f"/recipes/{r['recipe_id']}",
            "household": f"{r['household_name'] or 'household'} (#{r['household_id']})",
            "guest": not r["has_account"],
            "reason": PREP_REASONS.get(r["reason"] or "", r["reason"] or ""),
            "note": (r["note"] or "").strip(),
            "suggested_by_app": bool(r["auto"]),
            "date": str(r["updated_at"] or "")[:10],
        }
        for r in db.execute(
            f"""SELECT f.*, r.name AS recipe_name, h.name AS household_name, {_has_account_sql("f")} AS has_account
                FROM prep_step_feedback f JOIN recipes r ON r.id = f.recipe_id
                LEFT JOIN households h ON h.id = f.household_id ORDER BY f.updated_at DESC"""
        )
    ]
    return {"votes": votes, "source": "live", "review": {}}


def _plan_reports(db: PgConnection) -> dict:
    reports = [
        {"id": r["id"], "household_id": r["household_id"], "household_name": r["household_name"],
         "guest": not r["has_account"], "plan_id": r["plan_id"], "note": r["note"],
         "created_at": str(r["created_at"]), "snapshot": json.loads(r["snapshot_json"] or "{}")}
        for r in db.execute(
            f"""SELECT p.*, h.name AS household_name, {_has_account_sql("p")} AS has_account
                FROM plan_reports p LEFT JOIN households h ON h.id = p.household_id ORDER BY p.created_at DESC"""
        )
    ]
    return {"reports": reports, "source": "live", "site": "", "review": {}}


def _recipe_reports(db: PgConnection) -> dict:
    reports = [
        {"id": r["id"], "household_id": r["household_id"], "household_name": r["household_name"],
         "guest": not r["has_account"], "recipe_id": r["recipe_id"], "recipe_name": r["recipe_name"],
         "reason": r["reason"], "note": r["note"], "created_at": str(r["created_at"]),
         "snapshot": json.loads(r["snapshot_json"] or "{}")}
        for r in db.execute(
            f"""SELECT p.*, h.name AS household_name, rc.name AS recipe_name, {_has_account_sql("p")} AS has_account
                FROM recipe_reports p LEFT JOIN households h ON h.id = p.household_id
                LEFT JOIN recipes rc ON rc.id = p.recipe_id ORDER BY p.created_at DESC"""
        )
    ]
    return {"reports": reports, "source": "live", "site": "", "review": {}}


def _recipe_tags(db: PgConnection) -> dict:
    tags: dict[int, list[str]] = {}
    for r in db.execute("SELECT recipe_id, tag FROM recipe_tags ORDER BY tag"):
        tags.setdefault(r["recipe_id"], []).append(r["tag"])
    recipes, ids = [], {}
    for r in db.execute(
        "SELECT id, slug, name, cooking_minutes, photo_path, parent_recipe_id, provenance_json"
        " FROM recipes WHERE household_id IS NULL ORDER BY name"
    ):
        if json.loads(r["provenance_json"] or "{}").get("retired"):
            continue
        ids[r["slug"]] = r["id"]
        photo = usable_photo(r["photo_path"], r["id"], r["parent_recipe_id"])
        recipes.append({"id": r["id"], "slug": r["slug"], "name": r["name"], "minutes": r["cooking_minutes"],
                        "photo": photo if not photo or photo.startswith(("/", "http")) else f"/{photo}",
                        "tags": tags.get(r["id"], [])})
    # Proposed dimensional tags aren't in the database yet. The AI sweep writes them next to the
    # catalog, keyed by slug since catalog ids differ between databases.
    path = catalog_dir() / "recipe_tag_suggestions.json"
    proposed = json.loads(path.read_text())["suggestions"] if path.is_file() else []
    suggestions = [{**s, "recipe_id": ids[s["slug"]]} for s in proposed if s["slug"] in ids]
    vocabulary = json.loads(VOCABULARY.read_text())["dimensions"]
    return {"recipes": recipes, "suggestions": suggestions, "vocabulary": vocabulary, "source": "live"}


def _users(db: PgConnection) -> dict:
    sessions: dict[int, list] = {}
    for r in db.execute("SELECT token, user_id, created_at, expires_at, device FROM sessions ORDER BY created_at DESC"):
        sessions.setdefault(r["user_id"], []).append({"id": auth.session_id(r["token"]), "created_at": r["created_at"],
                                                      "expires_at": r["expires_at"], "device": r["device"]})
    taste: dict[str, int] = {}
    if db.execute("SELECT to_regclass('taste_people') IS NOT NULL AS present").fetchone()["present"]:
        for r in db.execute("""SELECT p.account_id, COUNT(s.id) AS n FROM taste_people p
                               JOIN taste_sessions s ON s.person_id = p.id
                               WHERE p.account_id IS NOT NULL GROUP BY p.account_id"""):
            taste[r["account_id"]] = r["n"]
    users = [
        {"id": r["id"], "login": r["email"], "has_email": auth.has_email(r["email"]),
         "recovery_email": r["recovery_email"], "verified_at": r["email_verified_at"],
         "household_id": r["household_id"], "household_name": r["household_name"], "role": r["household_role"],
         "failed_attempts": r["failed_attempts"], "locked_until": r["locked_until"], "created_at": r["created_at"],
         # Accounts from before last seen was kept fall back to their newest sign-in.
         "last_seen": r["last_seen_at"] or max((x["created_at"] for x in sessions.get(r["id"], [])), default=None),
         "admin": auth.is_admin_email(r["email"]), "sessions": sessions.get(r["id"], []),
         "taste_sessions": taste.get(str(r["id"]), 0)}
        for r in db.execute("""SELECT u.*, h.name AS household_name FROM users u
                               JOIN households h ON h.id = u.household_id ORDER BY u.id""")
    ]
    return {"users": users, "now": now(), "mail": mail_ready()}


# Admin wording for errors; app/auth_routes.py ERROR_MESSAGES speaks to the account's owner.
USER_ERRORS = {
    "invalid_email": "Enter a valid email address.",
    "invalid_username": "Usernames are 3 to 30 letters, numbers, dots, dashes or underscores. "
                        "Only username accounts have a recovery email.",
    "password_too_short": "Password must be at least 8 characters.",
    "email_taken": "Another account already uses that email or username.",
    "not_found": "No such account or household.",
    "already_member": "They're already in that household.",
    "successor_required": "They own a household others are in. Make someone else its owner first.",
    "invalid_role": "Choose owner, admin or member.",
    "too_many": "Already sent 3 this hour. Try again later.",
}


def _email(make, send) -> None:
    """Make a one-time link and email it. Email being down, or too many this hour, says so."""
    if not mail_ready():
        raise HTTPException(503, {"error": "mail", "detail": "mail_unavailable",
                                  "message": "Email isn't set up on this server (RESEND_API_KEY, MAIL_FROM, PUBLIC_URL)."})
    made = make()
    if not made:
        raise auth.AuthError("too_many")
    to, token = made
    try:
        send(to, token)
    except Exception:
        raise HTTPException(503, {"error": "mail", "detail": "mail_unavailable", "message": "The email didn't send."})


@router.post("/admin/users/{user_id}/{action}")
def user_action(user_id: int, action: str, body: dict, _admin=AdminDep, db: PgConnection = DbDep):
    """One change to one account, from the Users page."""
    actions = {
        "password": lambda: auth.admin_set_password(db, user_id, str(body.get("password") or "")),
        "unlock": lambda: auth.admin_unlock(db, user_id),
        "send-reset": lambda: _email(lambda: auth.admin_send_reset(db, user_id),
                                     lambda to, token: send_reset_email(to, reset_link(token))),
        "resend-confirmation": lambda: _email(lambda: auth.admin_resend_confirmation(db, user_id),
                                              lambda to, token: send_verify_email(to, verify_link(token))),
        "login": lambda: auth.admin_set_login(db, user_id, str(body.get("login") or "")),
        "recovery-email": lambda: auth.admin_set_recovery_email(db, user_id, str(body.get("email") or "")),
        "end-sessions": lambda: auth.admin_end_sessions(db, user_id, body.get("session")),
        "reset-taste": lambda: auth.admin_reset_taste(db, user_id),
        "household": lambda: auth.admin_move_user(
            db, user_id, None if body.get("household_id") in (None, "") else int(body["household_id"])),
        "role": lambda: auth.admin_set_role(db, user_id, str(body.get("role") or "")),
    }
    if action not in actions:
        raise HTTPException(404, {"error": "not_found", "detail": "admin action"})
    try:
        actions[action]()
    except auth.AuthError as e:
        db.rollback()
        raise HTTPException(400, {"error": "auth", "detail": e.detail,
                                  "message": USER_ERRORS.get(e.detail, "Something went wrong.")})
    except ValueError:
        db.rollback()
        raise HTTPException(400, {"error": "auth", "detail": "not_found", "message": USER_ERRORS["not_found"]})
    return {"ok": True}


@router.get("/admin/{name}", response_class=HTMLResponse)
def admin_page(name: str, _admin=AdminDep, db: PgConnection = DbDep):
    if name == "variant-review":
        return _page("variant_review", _variant_review())
    if name == "prep-feedback":
        return _page("prep_feedback", _prep_feedback(db))
    if name == "plan-reports":
        return _page("plan_reports", _plan_reports(db))
    if name == "recipe-reports":
        return _page("recipe_reports", _recipe_reports(db))
    if name == "recipe-tags":
        return _page("recipe_tags", _recipe_tags(db))
    if name == "users":
        return _page("users", _users(db))
    raise HTTPException(404, {"error": "not_found", "detail": "admin page"})
