"""Taste Lab APIs. Recipe cards come from the PostgreSQL catalog."""

from __future__ import annotations

import importlib.util
import json
import re
from app.auth import SESSION_COOKIE, session_info
from app.db.database import PgConnection
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.db.database import ROOT
from app.deps import DbDep
from app.domain.diet_filter import clean_filters, fold_profiles
from app.domain.recipe_photos import usable_photo

TASTE_SERVER = ROOT / "tastelab" / "server.py"
SKIP = {"incomplete", "side", "sauce", "dressing", "meal_component"}
ARCHIVE_ID = re.compile(r"/(\d+)/?$")
# The random id a guest's browser keeps for Taste Lab (crypto.randomUUID or similar).
ANON_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
# Shared stand-in photos. usable_photo can still return one; don't put it on the wrong dish.
GENERIC_PHOTOS = frozenset({
    "food/pasta-tomato.jpg",
    "food/pasta-veg.png",
    "food/salad-garden.png",
    "food/salad-chicken.png",
    "food/chicken-pilaf.png",
    "food/chicken-roast.jpg",
    "food/steak-wedges.png",
    "food/steak-plate.png",
})

router = APIRouter()
_mod = None


def taste():
    global _mod
    if _mod is None:
        spec = importlib.util.spec_from_file_location("taste_lab_server", TASTE_SERVER)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {TASTE_SERVER}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.init_db()
        _mod = mod
    return _mod


def archive_id(row) -> str:
    url = (row["source_url"] or "").split("?")[0].rstrip("/")
    m = ARCHIVE_ID.search(url)
    if m:
        return m.group(1)
    slug = str(row["slug"] or "")
    if slug.isdigit():
        return slug
    return str(row["id"])


def catalog_from_db(db: PgConnection) -> list[dict]:
    keep = taste().group_ids()
    tags_by: dict[int, set[str]] = defaultdict(set)
    for t in db.execute("SELECT recipe_id, tag FROM recipe_tags"):
        tags_by[int(t["recipe_id"])].add(t["tag"])
    ings_by: dict[int, list[str]] = defaultdict(list)
    for x in db.execute(
        """SELECT ri.recipe_id, i.canonical_name
           FROM recipe_ingredients ri
           JOIN ingredients i ON i.id = ri.ingredient_id
           ORDER BY ri.recipe_id, ri.sort"""
    ):
        ings_by[int(x["recipe_id"])].append(x["canonical_name"])
    out = []
    for r in db.execute(
        """SELECT id, name, slug, servings, cooking_minutes, photo_path, source_url
           FROM recipes WHERE household_id IS NULL"""
    ):
        rid = int(r["id"])
        tags = tags_by[rid]
        if tags & SKIP and "full_meal" not in tags and "main_dish" not in tags:
            continue
        ings = ings_by[rid]
        if not ings:
            continue
        archive = archive_id(r)
        photo = usable_photo(r["photo_path"] or "", rid)
        if photo and not photo.startswith("/"):
            photo = f"/{photo}"
        # Shared stand-in photos (a garden salad, a steak plate…) aren't the dish.
        # The Recipes tab already hides these; showing them here put a salad on a frittata.
        if not photo or photo.lstrip("/") in GENERIC_PHOTOS:
            continue
        mins = r["cooking_minutes"]
        out.append(
            {
                "id": archive,
                "recipe_id": rid,
                "name": r["name"],
                "mins": int(mins) if mins is not None else None,
                "servings": r["servings"],
                "photo": photo,
                "calories": None,
                "protein": None,
                "ingredients": ings,
            }
        )
    return out


@router.get("/catalog")
def catalog(request: Request, db: PgConnection = DbDep):
    rows = catalog_from_db(db)
    # Signed in: leave out meals the household gave a 👎 on their plan.
    row = session_info(db, request.cookies.get(SESSION_COOKIE))
    if row and row["household_id"]:
        down = {
            int(r["recipe_id"])
            for r in db.execute(
                "SELECT recipe_id FROM household_meal_ratings WHERE household_id = ? AND rating < 0",
                (row["household_id"],),
            )
        }
        rows = [r for r in rows if r["recipe_id"] not in down]
    return {"recipes": rows, "count": len(rows)}


@router.get("/sessions")
def sessions():
    rows = taste().list_sessions()
    return {"sessions": rows, "count": len(rows)}


@router.post("/sessions")
async def save_session(request: Request, db: PgConnection = DbDep):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, {"error": "bad_json", "detail": "object"})
    row = session_info(db, request.cookies.get(SESSION_COOKIE))
    if row:
        body["account_id"] = str(row["user_id"])
    sid = taste().save_event(body)
    return {"ok": True, "id": sid}


def public_taste(snapshots: list[dict], *, signed_in: bool, filters: dict | None = None) -> dict:
    """What Taste Lab should show this person. Same vote rules as suggestions.

    With `filters` (the household's Settings → Filters) the profile is those filters, so Taste
    Lab and Settings edit one thing. Without it, the latest Taste Lab profile is shown.
    """
    if not signed_in and not snapshots:
        return {"signed_in": False, "profile": None, "likes": 0, "passes": 0, "votes": []}
    from app.domain.taste_rank import learn

    taste = learn(snapshots, [])
    votes = [{"recipe_id": rid, "liked": False} for rid in sorted(taste.passed)]
    votes.extend({"recipe_id": rid, "liked": True} for rid in sorted(taste.liked))
    votes.extend({"recipe_id": rid, "liked": True, "plan": True} for rid in sorted(taste.plan_liked))
    if not signed_in:
        # A guest's own earlier answers (same browser), so Taste Lab doesn't ask again (#27).
        # No profile: guests' filters stay in the page.
        return {
            "signed_in": False,
            "profile": None,
            "likes": len(taste.liked) + len(taste.plan_liked),
            "passes": len(taste.passed),
            "votes": votes,
        }
    profile = {"diets": ["omnivore"], "allergens": [], "dislikes": []}
    if filters is not None:
        clean = clean_filters(filters)
        profile = {"diets": clean["diets"], "allergens": clean["allergens"], "dislikes": clean["avoids"]}
    else:
        for prof in lab_profiles(snapshots)[-1:]:
            diets = [str(item).strip().lower() for item in (prof.get("diets") or []) if str(item).strip()]
            profile = {
                "diets": diets or ["omnivore"],
                "allergens": [str(item).strip().lower() for item in (prof.get("allergens") or []) if str(item).strip()],
                "dislikes": [str(item).strip().lower() for item in (prof.get("dislikes") or []) if str(item).strip()],
            }
    return {
        "signed_in": True,
        "profile": profile,
        "likes": len(taste.liked) + len(taste.plan_liked),
        "passes": len(taste.passed),
        "votes": votes,
    }


def lab_profiles(snapshots: list[dict]) -> list[dict]:
    """Each account's latest Taste Lab profile, oldest account first."""
    latest: dict[str, dict] = {}
    for index, snap in enumerate(snapshots):
        if isinstance(snap, dict) and isinstance(snap.get("profile"), dict):
            key = str(snap.get("account_id") or snap.get("id") or index)
            latest.pop(key, None)
            latest[key] = snap["profile"]
    return list(latest.values())


def household_filters(db: PgConnection, household_id: int) -> dict:
    """Settings → Filters for this household: the only diet/allergy/avoid filters there are.

    Taste Lab used to keep its own copy. The first read folds those old profiles in (once, so an
    allergy set only in Taste Lab keeps working) and from then on both screens edit this.
    """
    row = db.execute("SELECT prefs_json FROM households WHERE id = ?", (household_id,)).fetchone()
    prefs = json.loads((row["prefs_json"] if row else None) or "{}")
    if not isinstance(prefs, dict):
        prefs = {}
    filters = prefs.get("filters") if isinstance(prefs.get("filters"), dict) else {}
    if filters.get("lab_folded"):
        return clean_filters(filters)
    accounts = [str(r["id"]) for r in db.execute("SELECT id FROM users WHERE household_id = ?", (household_id,))]
    folded = fold_profiles(filters, lab_profiles(snapshots_for_accounts(accounts)))
    folded["lab_folded"] = True
    if row is not None:
        prefs["filters"] = folded
        db.execute("UPDATE households SET prefs_json = ? WHERE id = ?", (json.dumps(prefs), household_id))
        db.commit()
    return folded


@router.get("/taste")
def my_taste(request: Request, db: PgConnection = DbDep):
    row = session_info(db, request.cookies.get(SESSION_COOKIE))
    if not row:
        anon = (request.query_params.get("anon") or "").strip()
        return public_taste(snapshots_for_anon(anon) if ANON_ID.fullmatch(anon) else [], signed_in=False)
    filters = household_filters(db, int(row["household_id"])) if row["household_id"] else None
    return public_taste(snapshots_for_accounts([str(row["user_id"])]), signed_in=True, filters=filters)


def snapshots_for_anon(anon_id: str) -> list[dict]:
    """A guest's own snapshots, by the random id their browser keeps. Only people not linked
    to an account: once someone signs in, their answers come with the account instead."""
    with taste().db() as con:
        rows = con.execute(
            """SELECT e.body
               FROM taste_events e
               JOIN taste_sessions s ON s.id = e.session_id
               JOIN taste_people p ON p.id = s.person_id
               WHERE e.kind = 'snapshot' AND p.anon_id = ? AND p.account_id IS NULL
               ORDER BY e.id""",
            (anon_id,),
        ).fetchall()
    out = []
    for row in rows:
        raw = row["body"]
        body = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(body, dict):
            saved = dict(body)
            saved["account_id"] = f"anon:{anon_id}"
            out.append(saved)
    return out


def snapshots_for_accounts(account_ids: list[str]) -> list[dict]:
    """Latest-to-oldest snapshot bodies for signed-in accounts, oldest first."""
    if not account_ids:
        return []
    marks = ", ".join("?" for _ in account_ids)
    with taste().db() as con:
        rows = con.execute(
            f"""SELECT e.body, p.account_id
                FROM taste_events e
                JOIN taste_sessions s ON s.id = e.session_id
                JOIN taste_people p ON p.id = s.person_id
                WHERE e.kind = 'snapshot' AND p.account_id IN ({marks})
                ORDER BY e.id""",
            account_ids,
        ).fetchall()
    out = []
    for row in rows:
        raw = row["body"]
        body = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(body, dict):
            continue
        saved = dict(body)
        saved["account_id"] = row["account_id"]
        out.append(saved)
    return out
