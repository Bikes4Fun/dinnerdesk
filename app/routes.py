"""HTTP routes. Household comes from deps, never from the client."""

from __future__ import annotations

import contextvars
import functools
import hashlib
import inspect
import json
import logging
import os
import re
import threading
from collections import OrderedDict
import time
from app.db.database import PgConnection
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app.db.catalog import public_recipe_sql
from app.perf import Laps
from app.db.seed import pantry_catalog
from app.db.database import ROOT, connect, now, transaction
from app.assets import catalog_dir, feedback_dir
from app.auth import SESSION_COOKIE, session_info
from app.deps import AdminDep, DbDep, HhDep, OptionalAdminDep
from fractions import Fraction

from app.domain.photo_uploads import save_photo, save_screenshot, save_photo_bytes
from app.domain.ingredient_photos import photo_path as ingredient_photo_path
from app.domain.recipe_import import RecipeImportError, fetch_image, import_recipe
from app.domain.recipe_photos import archive_id_of, photo_is_ai, photo_is_borrowed, usable_photo
from app.domain.grocery import coerce_qty_name, combine_quantities, merge_grocery, scale_quantity
from app.domain.ingredient_review import (
    collect_flagged_recipes,
    resolve_group_audit,
    review_groups,
    save_flagged_recipes,
    save_group_answer,
    save_group_audit,
    save_group_notes,
)
from app.domain.ingredients import aisle_for, pantry_key
from app.domain.pantry_catalog import in_grocery_catalog, item_key, preferred_grocery_name
from app.domain.prep import prep_from_slots, step_key, step_sentences
from app.domain.diet_filter import allowed as diet_allowed, blocks_for, matched_words, merge_filters
from app.domain.pool import Pool, build_pool, filters_key
from app.domain.search import filter_item_matches, hard_tokens, search_grocery_names, tokens as search_tokens
from app.domain.suggest import norm_pantry
from app.domain.taste_rank import learn, pick_meals, promote, reasons_summary, suggestion_note, suggestion_penalties
from app.taste_lab import SKIP as TASTE_SKIP
from app.taste_lab import archive_id, household_filters, snapshots_for_accounts
from app.models import (
    PrepMissingPut,
    PlanReportCreate,
    RecipeReportCreate,
    FeedbackCreate,
    FeedbackStatusPut,
    PrepTaskFeedbackPut,
    PlanCreate,
    SuggestionResize,
    SuggestionSwap,
    PlacementPut,
    DevNotesPut,
    FavoritePut,
    GroceryLineCreate,
    GroceryPatch,
    HouseholdPut,
    IngredientReviewAnswer,
    IngredientReviewAudit,
    IngredientReviewAuditResolution,
    IngredientReviewNotes,
    OverrideIn,
    OverridesPut,
    PantryItemUpsert,
    PantryPatch,
    PantryPut,
    PrepPatch,
    PrepStepPatch,
    PrepStepFeedbackPut,
    RatingPut,
    RecipeCreate,
    RecipeImport,
    RecipePatch,
    SlotPatch,
    SlotsPut,
    SubmissionCreate,
)

_log = logging.getLogger(__name__)

router = APIRouter()


def _aliases(db: PgConnection) -> dict[str, str]:
    out = {}
    for row in db.execute("SELECT canonical_name, aliases_json FROM ingredients"):
        out[row["canonical_name"]] = row["canonical_name"]
        try:
            for a in json.loads(row["aliases_json"] or "[]"):
                out[pantry_key(a)] = row["canonical_name"]
        except json.JSONDecodeError:
            raise
    return out


def _overrides(db: PgConnection, household_id: int) -> dict[str, str]:
    return {
        r["from_name"]: r["to_name"]
        for r in db.execute(
            "SELECT from_name, to_name FROM household_overrides WHERE household_id = ?",
            (household_id,),
        )
        if r["from_name"] and r["to_name"]
    }


def _grocery_name_pool(db: PgConnection, household_id: int) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for raw, _zone in pantry_catalog():
        name = preferred_grocery_name(raw) or pantry_key(raw)
        if not name:
            continue
        key = item_key(name)
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _get_or_create_ingredient(db: PgConnection, name: str) -> int:
    key = pantry_key(name)
    row = db.execute(
        "SELECT id FROM ingredients WHERE canonical_name = ?", (key,)
    ).fetchone()
    if row:
        return row["id"]
    cur = db.execute(
        "INSERT INTO ingredients (canonical_name, aliases_json, aisle) VALUES (?, '[]', ?)",
        (key, aisle_for(key)),
    )
    return int(cur.lastrowid)


def _set_recipe_ingredients(db: PgConnection, recipe_id: int, ingredients: list) -> None:
    db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    for i, ing in enumerate(ingredients):
        name = ing.get("name") if isinstance(ing, dict) else str(ing)
        qty = ing.get("quantity", "") if isinstance(ing, dict) else ""
        qty, name = coerce_qty_name(qty, name or "")
        if not name:
            continue
        name = preferred_grocery_name(name) or pantry_key(name)
        iid = _get_or_create_ingredient(db, name)
        db.execute(
            """INSERT INTO recipe_ingredients
               (recipe_id, ingredient_id, quantity, unit, note, sort)
               VALUES (?, ?, ?, '', '', ?)""",
            (recipe_id, iid, qty or "", i),
        )


def _recipe_edit(db: PgConnection, household_id: int, recipe_id: int):
    return db.execute(
        """SELECT * FROM household_recipe_edits
           WHERE household_id = ? AND recipe_id = ?""",
        (household_id, recipe_id),
    ).fetchone()


def _hidden_recipe_ids(db: PgConnection, household_id: int) -> set[int]:
    return {
        r["recipe_id"]
        for r in db.execute(
            "SELECT recipe_id FROM household_hidden_recipes WHERE household_id = ?",
            (household_id,),
        )
    }


def _norm_edit_ings(raw) -> list[dict]:
    out = []
    for ing in raw or []:
        if isinstance(ing, str):
            name, qty = ing, ""
        else:
            name = (ing.get("name") or "").strip()
            qty = ing.get("quantity") or ""
        qty, name = coerce_qty_name(qty, name)
        name = preferred_grocery_name(name) or pantry_key(name)
        if name:
            out.append({"name": name, "quantity": qty, "ingredient_id": None})
    return out


def _apply_recipe_edit(
    db: PgConnection,
    out: dict,
    household_id: int,
    hidden: set[int] | None = None,
) -> dict:
    rid = out["id"]
    edit = _recipe_edit(db, household_id, rid)
    out["edited"] = bool(edit)
    hid = hidden if hidden is not None else _hidden_recipe_ids(db, household_id)
    out["hidden"] = rid in hid
    if not edit:
        return out
    if edit["name"]:
        out["name"] = edit["name"]
    if edit["servings"] is not None:
        out["servings"] = edit["servings"]
    if "cooking_minutes" in edit.keys():
        out["cooking_minutes"] = edit["cooking_minutes"]
    try:
        instructions = json.loads(edit["instructions_json"] or "[]")
    except json.JSONDecodeError:
        raise
    if instructions is not None:
        out["instructions"] = instructions
    try:
        cookware = json.loads(edit["cookware_json"] or "[]")
    except json.JSONDecodeError:
        raise
    if cookware:
        out["cookware"] = cookware
    try:
        ings = json.loads(edit["ingredients_json"] or "[]")
    except json.JSONDecodeError:
        raise
    if ings is not None:
        if out.get("ingredients") and out["ingredients"] and isinstance(out["ingredients"][0], str):
            out["ingredients"] = [i.get("name") or "" for i in ings if i.get("name")]
        else:
            out["ingredients"] = _norm_edit_ings(ings)
    return out


def _upsert_recipe_edit(
    db: PgConnection,
    household_id: int,
    recipe_id: int,
    body: RecipePatch,
    base: dict,
) -> None:
    name = body.name.strip() if body.name is not None else base["name"]
    servings = body.servings if body.servings is not None else base["servings"]
    if "cooking_minutes" in body.model_fields_set:
        minutes = body.cooking_minutes
    else:
        minutes = base.get("cooking_minutes")
    instructions = body.instructions if body.instructions is not None else (base.get("instructions") or [])
    cookware = body.cookware if body.cookware is not None else (base.get("cookware") or [])
    if body.ingredients is not None:
        ings = _norm_edit_ings(body.ingredients)
    else:
        ings = _norm_edit_ings(base.get("ingredients") or [])
    db.execute(
        """INSERT INTO household_recipe_edits (
            household_id, recipe_id, name, servings, cooking_minutes,
            instructions_json, cookware_json, ingredients_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(household_id, recipe_id) DO UPDATE SET
            name = excluded.name,
            servings = excluded.servings,
            cooking_minutes = excluded.cooking_minutes,
            instructions_json = excluded.instructions_json,
            cookware_json = excluded.cookware_json,
            ingredients_json = excluded.ingredients_json,
            updated_at = excluded.updated_at""",
        (
            household_id,
            recipe_id,
            name,
            servings,
            minutes,
            json.dumps(instructions),
            json.dumps(cookware),
            json.dumps(ings),
            now(),
        ),
    )


def _recipe_visible(row, household_id: int) -> bool:
    hid = row["household_id"]
    return hid is None or hid == household_id


def _recipe_tags(db: PgConnection, recipe_id: int) -> list[str]:
    return [
        r["tag"]
        for r in db.execute(
            "SELECT tag FROM recipe_tags WHERE recipe_id = ? ORDER BY tag",
            (recipe_id,),
        )
    ]


def _favorite_ids(db: PgConnection, household_id: int) -> set[int]:
    return {
        r["recipe_id"]
        for r in db.execute(
            "SELECT recipe_id FROM household_favorites WHERE household_id = ?",
            (household_id,),
        )
    }


def _try_ids(db: PgConnection, household_id: int) -> set[int]:
    return {
        r["recipe_id"]
        for r in db.execute(
            "SELECT recipe_id FROM household_try_later WHERE household_id = ?",
            (household_id,),
        )
    }


def _is_to_try(db: PgConnection, household_id: int, recipe_id: int) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM household_try_later WHERE household_id = ? AND recipe_id = ?",
            (household_id, recipe_id),
        ).fetchone()
        is not None
    )


def _recipe_card(
    db: PgConnection,
    row,
    household_id: int,
    favorited: bool = False,
    to_try: bool = False,
    hidden: set[int] | None = None,
) -> dict:
    rid = row["id"]
    try:
        cookware = json.loads(row["cookware_json"] or "[]")
    except json.JSONDecodeError:
        raise
    ings = [
        r["canonical_name"]
        for r in db.execute(
            """SELECT i.canonical_name
               FROM recipe_ingredients ri
               JOIN ingredients i ON i.id = ri.ingredient_id
               WHERE ri.recipe_id = ? ORDER BY ri.sort""",
            (rid,),
        )
    ]
    card = {
        "id": rid,
        "household_id": row["household_id"],
        "name": row["name"],
        "slug": row["slug"],
        "servings": row["servings"],
        "cooking_minutes": row["cooking_minutes"],
        "photo_path": _shown_photo(row),
        "catalog": row["household_id"] is None,
        "favorited": favorited,
        "to_try": to_try,
        "tags": _recipe_tags(db, rid),
        "cookware": cookware,
        "ingredients": ings,
    }
    return _apply_recipe_edit(db, card, household_id, hidden)


def _is_favorited(db: PgConnection, household_id: int, recipe_id: int) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM household_favorites WHERE household_id = ? AND recipe_id = ?",
            (household_id, recipe_id),
        ).fetchone()
        is not None
    )


def _recipe_out(db: PgConnection, row, household_id: int, admin: bool = False) -> dict:
    rid = row["id"]
    ings = [
        {
            "name": r["canonical_name"],
            "quantity": r["quantity"],
            "ingredient_id": r["ingredient_id"],
        }
        for r in db.execute(
            """SELECT ri.quantity, ri.ingredient_id, i.canonical_name
               FROM recipe_ingredients ri
               JOIN ingredients i ON i.id = ri.ingredient_id
               WHERE ri.recipe_id = ? ORDER BY ri.sort""",
            (rid,),
        )
    ]
    tags = _recipe_tags(db, rid)
    try:
        instructions = json.loads(row["instructions_json"] or "[]")
    except json.JSONDecodeError:
        raise
    try:
        cookware = json.loads(row["cookware_json"] or "[]")
    except json.JSONDecodeError:
        raise
    provenance = json.loads(row["provenance_json"] or "{}")
    out = {
        "id": rid,
        "household_id": row["household_id"],
        "name": row["name"],
        "slug": row["slug"],
        "servings": row["servings"],
        "cooking_minutes": row["cooking_minutes"],
        "photo_path": _shown_photo(row),
        "photo_ai": photo_is_ai(usable_photo(row["photo_path"], row["id"], row["parent_recipe_id"])),
        "photo_shared": photo_is_borrowed(
            usable_photo(row["photo_path"], row["id"], row["parent_recipe_id"]),
            archive_id_of(row["source_url"], row["slug"]),
        ),
        "source_url": row["source_url"],
        "photo_source_url": provenance.get("photo_url") or "",
        "instructions_source": provenance.get("instructions_source"),
        "instructions_copied_from_third_party": provenance.get("instructions_copied_from_third_party"),
        "parent_recipe_id": row["parent_recipe_id"],
        "ingredients": ings,
        "instructions": instructions,
        "cookware": cookware,
        "tags": tags,
        "catalog": row["household_id"] is None,
        "favorited": _is_favorited(db, household_id, rid),
        "to_try": _is_to_try(db, household_id, rid),
    }
    if admin:
        out["dev_notes"] = row["dev_notes"] if "dev_notes" in row.keys() else ""
    return _apply_recipe_edit(db, out, household_id)


def _ensure_plan(db: PgConnection, household_id: int) -> int:
    row = db.execute(
        "SELECT id FROM plans WHERE household_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (household_id,),
    ).fetchone()
    if row:
        return row["id"]
    cur = db.execute(
        """INSERT INTO plans (household_id, start_date, days, title, created_at)
           VALUES (?, date('now'), 7, 'This week', ?)""",
        (household_id, now()),
    )
    db.commit()
    return int(cur.lastrowid)


def _plan_id_for_household(db: PgConnection, household_id: int) -> int | None:
    row = db.execute(
        "SELECT id FROM plans WHERE household_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (household_id,),
    ).fetchone()
    return int(row["id"]) if row else None


def _rebuild_grocery_for_household(db: PgConnection, household_id: int) -> None:
    plan_id = _plan_id_for_household(db, household_id)
    if plan_id is not None:
        _rebuild_grocery(db, plan_id, household_id)


def _meal_ratings(db: PgConnection, household_id: int) -> dict[int, int]:
    return {
        int(r["recipe_id"]): int(r["rating"])
        for r in db.execute(
            "SELECT recipe_id, rating FROM household_meal_ratings WHERE household_id = ?",
            (household_id,),
        )
    }


def _plan_out(db: PgConnection, plan_id: int, household_id: int) -> dict:
    ratings = _meal_ratings(db, household_id)
    plan = db.execute(
        "SELECT * FROM plans WHERE id = ? AND household_id = ? AND hidden = 0",
        (plan_id, household_id),
    ).fetchone()
    if not plan:
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    slots = []
    for s in db.execute(
        """SELECT s.*, r.name AS recipe_name, r.photo_path, r.parent_recipe_id,
                  r.cooking_minutes
           FROM plan_slots s JOIN recipes r ON r.id = s.recipe_id
           WHERE s.plan_id = ? ORDER BY s.sort, s.id""",
        (plan_id,),
    ):
        edit = _recipe_edit(db, household_id, s["recipe_id"])
        slots.append(
            {
                "id": s["id"],
                "recipe_id": s["recipe_id"],
                "recipe_name": (edit["name"] if edit and edit["name"] else s["recipe_name"]),
                "photo_path": usable_photo(s["photo_path"], s["recipe_id"], s["parent_recipe_id"]),
                "cooking_minutes": (
                    edit["cooking_minutes"] if edit else s["cooking_minutes"]
                ),
                "day_index": s["day_index"],
                "meal_type": s["meal_type"],
                "servings": s["servings"],
                "sort": s["sort"],
                "cooked": bool(s["cooked"]) if "cooked" in s.keys() else False,
                "rating": ratings.get(int(s["recipe_id"]), 0),
            }
        )
    return {
        "id": plan["id"],
        "title": plan["title"],
        "start_date": plan["start_date"],
        "days": plan["days"],
        "status": plan["status"],
        "created_at": plan["created_at"],
        "slots": slots,
        **json.loads(plan["suggestion_json"] or "{}"),
        "suggestion_note": json.loads(plan["suggestion_json"] or "{}").get("suggestion_note") if plan["status"] == "suggested" else None,
    }


@router.get("/recipes")
def list_recipes(
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    q: str = "",
    tag: str = "",
    hidden_only: bool = Query(default=False, alias="hidden"),
    mine: bool = False,
    limit: int = Query(default=60, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    sql = """SELECT DISTINCT r.* FROM recipes r
             LEFT JOIN recipe_tags t ON t.recipe_id = r.id
             LEFT JOIN household_recipe_edits e
               ON e.recipe_id = r.id AND e.household_id = ?
             WHERE (r.household_id IS NULL OR r.household_id = ?)"""
    args: list = [household_id, household_id]
    public_sql, public_args = public_recipe_sql("r")
    sql += f" AND {public_sql}"
    args.extend(public_args)
    if hidden_only:
        sql += """ AND r.id IN (
                 SELECT recipe_id FROM household_hidden_recipes WHERE household_id = ?
               )"""
        args.append(household_id)
    if mine:
        # The kitchen's own recipes (made, imported or copied), whatever the filters say.
        sql += " AND r.household_id = ?"
        args.append(household_id)
    if q.strip():
        needed = hard_tokens(q) or search_tokens(q)
        for tok in needed:
            sql += " AND COALESCE(NULLIF(e.name, ''), r.name) ILIKE ?"
            args.append(f"%{tok}%")
    if tag.strip():
        sql += " AND t.tag = ?"
        args.append(tag.strip())
    laps = Laps()
    if hidden_only or mine:
        sql += " ORDER BY r.name LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        rows = db.execute(sql, args).fetchall()
    else:
        diets, allergens, avoids, _ = _filter_prefs(db, household_id)
        pool, pool_hit = _household_pool(db, household_id, diets, allergens, avoids)
        downvoted = {rid for rid, rating in _meal_ratings(db, household_id).items() if rating < 0}
        sql += " ORDER BY r.name"
        matches = [r for r in db.execute(sql, args).fetchall() if r["id"] in pool.allowed]
        # Priority first: no avoided, hidden or downvoted recipes, and variants only when
        # searched for. A search that the priority ones don't fill a page for gets the rest
        # after them; plain browsing never shows them, so a recipe just hidden stays gone.
        searching = bool(q.strip())
        held = pool.demoted | downvoted | (frozenset() if searching else pool.variants)
        priority = [r for r in matches if r["id"] not in held]
        if searching and len(priority) < limit:
            priority += [r for r in matches if r["id"] in held]
        rows = priority[offset:offset + limit]
        laps.counts.update(pool="hit" if pool_hit else "built", matches=len(matches))
    laps.counts.update(results=len(rows), offset=offset)
    laps.lap("query")
    favs = _favorite_ids(db, household_id)
    later = _try_ids(db, household_id)
    hidden_ids = _hidden_recipe_ids(db, household_id)
    cards = [
        _recipe_card(db, r, household_id, r["id"] in favs, r["id"] in later, hidden_ids)
        for r in rows
    ]
    laps.lap("cards")
    laps.publish("recipes")
    _log.debug("recipes hh=%d q=%r tag=%r %s", household_id, q.strip() or None, tag.strip() or None, laps.fmt())
    # Every recipe this kitchen could find, before filters: shown in the search box placeholder.
    total = db.execute(
        f"SELECT COUNT(*) AS n FROM recipes r WHERE (r.household_id IS NULL OR r.household_id = ?) AND {public_sql}",
        (household_id, *public_args),
    ).fetchone()["n"]
    return {"recipes": cards, "total": int(total)}


@router.get("/tags")
def list_tags(db: PgConnection = DbDep, household_id: int = HhDep):
    public_sql, public_args = public_recipe_sql("r")
    rows = db.execute(
        f"""SELECT t.tag, COUNT(*) AS n
           FROM recipe_tags t
           JOIN recipes r ON r.id = t.recipe_id
           WHERE (r.household_id IS NULL OR r.household_id = ?)
             AND {public_sql}
           GROUP BY t.tag
           ORDER BY n DESC, t.tag
           LIMIT 40""",
        (household_id, *public_args),
    ).fetchall()
    return {"tags": [{"tag": r["tag"], "count": r["n"]} for r in rows]}


def _web_link(url: str | None) -> str:
    url = (url or "").strip()[:2000]
    return url if url.lower().startswith(("http://", "https://")) else ""


def _copy_site_photo(url: str, household_id: int) -> str:
    """The kitchen's private copy of an imported page's photo, or '' to fall back to the link."""
    if not url:
        return ""
    try:
        return save_photo_bytes(fetch_image(url))
    except RecipeImportError as exc:
        _log.info("recipe photo copy hh=%d failed %s", household_id, exc.code)
    except HTTPException:
        _log.info("recipe photo copy hh=%d failed not_a_usable_image", household_id)
    return ""


def _shown_photo(row) -> str:
    """A recipe's stored photo; a kitchen's imported recipe falls back to its page's photo link."""
    stored = usable_photo(row["photo_path"], row["id"], row["parent_recipe_id"])
    if stored or row["household_id"] is None:
        return stored
    try:
        return _web_link(json.loads(row["provenance_json"] or "{}").get("photo_url"))
    except (json.JSONDecodeError, AttributeError):
        return ""


@router.post("/recipes")
def create_recipe(
    body: RecipeCreate,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    ts = now()
    source_url = (body.source_url or "").strip()[:2000]
    provenance = {
        "instructions_source": "import" if body.imported else "household",
        "instructions_copied_from_third_party": bool(body.imported),
    }
    photo_link = _web_link(body.photo_url)
    if photo_link:
        provenance["photo_url"] = photo_link
    photo = save_photo(body.photo_data) if body.photo_data else _copy_site_photo(photo_link, household_id)
    with transaction(db):
        cur = db.execute(
            """INSERT INTO recipes (
                household_id, slug, name, servings, cooking_minutes,
                instructions_json, cookware_json, source_url, provenance_json,
                photo_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                household_id,
                pantry_key(body.name).replace(" ", "-")[:80],
                body.name.strip(),
                body.servings,
                body.cooking_minutes,
                json.dumps(body.instructions),
                json.dumps(body.cookware),
                source_url,
                json.dumps(provenance),
                photo,
                ts,
                ts,
            ),
        )
        rid = int(cur.lastrowid)
        _set_recipe_ingredients(db, rid, body.ingredients)
        for tag in body.tags:
            db.execute(
                "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?, ?)",
                (rid, tag[:40]),
            )
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (rid,)).fetchone()
    _invalidate_pool(household_id)
    return _recipe_out(db, row, household_id)


@router.post("/recipes/import")
def import_recipe_draft(body: RecipeImport, household_id: int = HhDep):
    """Read a public recipe page into a draft for the cook to check. Saves nothing."""
    try:
        return import_recipe(body.url)
    except RecipeImportError as exc:
        _log.info("recipe import hh=%d failed %s", household_id, exc.code)
        raise HTTPException(422, {"error": exc.code, "detail": exc.message})


@router.get("/recipes/{recipe_id}")
def get_recipe(
    recipe_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    admin=OptionalAdminDep,
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    return _recipe_out(db, row, household_id, admin is not None)


@router.put("/recipes/{recipe_id}/favorite")
def put_favorite(
    recipe_id: int,
    body: FavoritePut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    admin=OptionalAdminDep,
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    with transaction(db):
        if body.on:
            db.execute(
                """INSERT OR IGNORE INTO household_favorites
                   (household_id, recipe_id, created_at) VALUES (?, ?, ?)""",
                (household_id, recipe_id, now()),
            )
        else:
            db.execute(
                "DELETE FROM household_favorites WHERE household_id = ? AND recipe_id = ?",
                (household_id, recipe_id),
            )
    return _recipe_out(db, row, household_id, admin is not None)


@router.put("/recipes/{recipe_id}/hidden")
def put_hidden(
    recipe_id: int,
    body: FavoritePut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    admin=OptionalAdminDep,
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    with transaction(db):
        if body.on:
            db.execute(
                """INSERT OR IGNORE INTO household_hidden_recipes
                   (household_id, recipe_id, created_at) VALUES (?, ?, ?)""",
                (household_id, recipe_id, now()),
            )
        else:
            db.execute(
                "DELETE FROM household_hidden_recipes WHERE household_id = ? AND recipe_id = ?",
                (household_id, recipe_id),
            )
    _invalidate_pool(household_id)
    return _recipe_out(db, row, household_id, admin is not None)


@router.delete("/recipes/{recipe_id}/edit")
def revert_recipe_edit(
    recipe_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    _admin=AdminDep,  # recipe editing is for the Dinnerdesk admins only
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    if row["household_id"] is not None:
        raise HTTPException(400, {"error": "bad_request", "detail": "restore is only for catalog recipes"})
    if not _recipe_edit(db, household_id, recipe_id):
        raise HTTPException(404, {"error": "not_found", "detail": "overlay"})
    with transaction(db):
        db.execute(
            "DELETE FROM household_recipe_edits WHERE household_id = ? AND recipe_id = ?",
            (household_id, recipe_id),
        )
        _rebuild_grocery_for_household(db, household_id)
    _invalidate_pool(household_id)
    return _recipe_out(db, row, household_id, True)


@router.put("/recipes/{recipe_id}/try")
def put_try_later(
    recipe_id: int,
    body: FavoritePut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    admin=OptionalAdminDep,
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    with transaction(db):
        if body.on:
            db.execute(
                """INSERT OR IGNORE INTO household_try_later
                   (household_id, recipe_id, created_at) VALUES (?, ?, ?)""",
                (household_id, recipe_id, now()),
            )
        else:
            db.execute(
                "DELETE FROM household_try_later WHERE household_id = ? AND recipe_id = ?",
                (household_id, recipe_id),
            )
    return _recipe_out(db, row, household_id, admin is not None)


@router.put("/recipes/{recipe_id}/rating")
def put_meal_rating(
    recipe_id: int,
    body: RatingPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    """Thumbs on a meal. Suggestions never pick a 👎 meal again and lean toward 👍 ones."""
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    with transaction(db):
        if body.rating:
            db.execute(
                """INSERT INTO household_meal_ratings (household_id, recipe_id, rating, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(household_id, recipe_id) DO UPDATE SET
                     rating = excluded.rating, updated_at = excluded.updated_at""",
                (household_id, recipe_id, body.rating, now()),
            )
        else:
            db.execute(
                "DELETE FROM household_meal_ratings WHERE household_id = ? AND recipe_id = ?",
                (household_id, recipe_id),
            )
    return {"recipe_id": recipe_id, "rating": body.rating}


@router.put("/recipes/{recipe_id}/dev-notes")
def put_dev_notes(
    recipe_id: int,
    body: DevNotesPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    _admin=AdminDep,  # recipe editing is for the Dinnerdesk admins only
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    with transaction(db):
        db.execute(
            "UPDATE recipes SET dev_notes = ?, updated_at = ? WHERE id = ?",
            (body.text, now(), recipe_id),
        )
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    return _recipe_out(db, row, household_id, True)


def _copy_recipe(db: PgConnection, row, household_id: int) -> int:
    shown = _recipe_out(db, row, household_id)
    ts = now()
    cur = db.execute(
        """INSERT INTO recipes (
            household_id, slug, name, servings, cooking_minutes,
            instructions_json, cookware_json, source_url, provenance_json,
            photo_path, parent_recipe_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            household_id,
            row["slug"],
            shown["name"],
            shown["servings"],
            shown["cooking_minutes"],
            json.dumps(shown.get("instructions") or []),
            json.dumps(shown.get("cookware") or []),
            row["source_url"],
            row["provenance_json"],
            row["photo_path"],
            row["id"],
            ts,
            ts,
        ),
    )
    new_id = int(cur.lastrowid)
    _set_recipe_ingredients(db, new_id, shown.get("ingredients") or [])
    for tag in shown.get("tags") or []:
        db.execute(
            "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?, ?)",
            (new_id, tag),
        )
    return new_id


@router.patch("/recipes/{recipe_id}")
def patch_recipe(
    recipe_id: int,
    body: RecipePatch,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    admin=OptionalAdminDep,
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    # A kitchen edits its own recipes; everything else is for the Dinnerdesk admins only.
    if admin is None and (row["household_id"] != household_id or body.as_copy):
        raise HTTPException(403, {"error": "forbidden", "detail": "admin"})
    catalog = row["household_id"] is None
    # recipe_tags has no household_id, and photo_path gates public_recipe_sql eligibility,
    # so a tag or photo change on a shared catalog row affects every household's candidates.
    global_change = catalog and not body.as_copy and (body.tags is not None or body.photo_data is not None)
    target = recipe_id
    with transaction(db):
        if catalog and not body.as_copy:
            if body.photo_data is not None:
                photo = save_photo(body.photo_data)
                db.execute("UPDATE recipes SET photo_path = ?, updated_at = ? WHERE id = ?", (photo, now(), recipe_id))
                row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
            if body.tags is not None:
                db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
                for tag in body.tags:
                    if tag.strip():
                        db.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?, ?)", (recipe_id, tag.strip()[:40]))
                provenance = json.loads(row["provenance_json"] or "{}")
                provenance["admin_tags_edited"] = True
                db.execute("UPDATE recipes SET provenance_json = ?, updated_at = ? WHERE id = ?", (json.dumps(provenance), now(), recipe_id))
                row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
            base = _recipe_out(db, row, household_id)
            _upsert_recipe_edit(db, household_id, recipe_id, body, base)
            _rebuild_grocery_for_household(db, household_id)
        else:
            copied = catalog and body.as_copy
            if copied:
                target = _copy_recipe(db, row, household_id)
                row = db.execute("SELECT * FROM recipes WHERE id = ?", (target,)).fetchone()
            fields = []
            args = []
            if body.photo_data is not None:
                fields.append("photo_path = ?")
                args.append(save_photo(body.photo_data))
            if body.name is not None:
                fields.append("name = ?")
                args.append(body.name.strip())
            if body.servings is not None:
                fields.append("servings = ?")
                args.append(body.servings)
            if "cooking_minutes" in body.model_fields_set:
                fields.append("cooking_minutes = ?")
                args.append(body.cooking_minutes)
            if body.instructions is not None:
                fields.append("instructions_json = ?")
                args.append(json.dumps(body.instructions))
            if body.cookware is not None:
                fields.append("cookware_json = ?")
                args.append(json.dumps(body.cookware))
            if body.tags is not None:
                db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (target,))
                for tag in body.tags:
                    db.execute(
                        "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?, ?)",
                        (target, tag[:40]),
                    )
            if body.ingredients is not None:
                _set_recipe_ingredients(db, target, body.ingredients)
            if fields or body.tags is not None or body.ingredients is not None:
                fields.append("updated_at = ?")
                args.append(now())
                args.append(target)
                db.execute(
                    f"UPDATE recipes SET {', '.join(fields)} WHERE id = ? AND household_id = ?",
                    (*args, household_id),
                )
            if not copied:
                _rebuild_grocery_for_household(db, household_id)
    # Invalidate only after commit, so a concurrent load can't re-cache pre-commit rows.
    if global_change:
        _invalidate_all_pools()
    else:
        _invalidate_pool(household_id)
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (target,)).fetchone()
    return _recipe_out(db, row, household_id, admin is not None)


@router.delete("/recipes/{recipe_id}")
def delete_recipe(
    recipe_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    if row["household_id"] is None:
        raise HTTPException(403, {"error": "forbidden", "detail": "catalog is read-only"})
    with transaction(db):
        db.execute(
            "DELETE FROM recipes WHERE id = ? AND household_id = ?",
            (recipe_id, household_id),
        )
    _invalidate_pool(household_id)
    return {"ok": True}


@router.get("/plans")
def list_plans(db: PgConnection = DbDep, household_id: int = HhDep):
    pid = _ensure_plan(db, household_id)
    return {"plans": [_plan_out(db, row["id"], household_id) for row in db.execute(
        "SELECT id FROM plans WHERE household_id = ? AND hidden = 0 ORDER BY id DESC", (household_id,)
    )]}


@router.get("/plans/current")
def current_plan(db: PgConnection = DbDep, household_id: int = HhDep):
    pid = _ensure_plan(db, household_id)
    return _plan_out(db, pid, household_id)


def _meals_key(rows) -> list[tuple[int, int | None]]:
    return sorted((int(r["recipe_id"]), r["servings"]) for r in rows)


def _default_slot_servings(
    db: PgConnection, household_id: int, recipe_id: int
) -> int:
    household = db.execute("SELECT prefs_json FROM households WHERE id = ?", (household_id,)).fetchone()
    prefs = json.loads((household["prefs_json"] if household else None) or "{}")
    portions = prefs.get("family_portions")
    if type(portions) is int and 1 <= portions <= 50:
        return portions
    rec = db.execute("SELECT servings FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    edit = _recipe_edit(db, household_id, recipe_id)
    if edit and edit["servings"]:
        return int(edit["servings"])
    return int(rec["servings"]) if rec and rec["servings"] else 4


def _take_cooked(slot: SlotIn, unmatched: list) -> int:
    if slot.id is not None:
        for i, prev in enumerate(unmatched):
            if prev["id"] == slot.id and prev["recipe_id"] == slot.recipe_id:
                unmatched.pop(i)
                return 1 if prev["cooked"] else 0
    for i, prev in enumerate(unmatched):
        if prev["recipe_id"] == slot.recipe_id:
            unmatched.pop(i)
            return 1 if prev["cooked"] else 0
    return 0


@router.put("/plans/{plan_id}/slots")
def put_slots(
    plan_id: int,
    body: SlotsPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    plan = db.execute(
        "SELECT id FROM plans WHERE id = ? AND household_id = ?",
        (plan_id, household_id),
    ).fetchone()
    if not plan:
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    old_rows = list(
        db.execute(
            """SELECT id, recipe_id, servings, cooked FROM plan_slots
               WHERE plan_id = ? ORDER BY sort, id""",
            (plan_id,),
        )
    )
    old_meals = _meals_key(old_rows)
    unmatched = [dict(r) for r in old_rows]
    resolved = []
    for slot in body.slots:
        rec = db.execute(
            "SELECT id, household_id FROM recipes WHERE id = ?",
            (slot.recipe_id,),
        ).fetchone()
        if not rec or not _recipe_visible(rec, household_id):
            raise HTTPException(400, {"error": "bad_recipe", "detail": slot.recipe_id})
        servings = slot.servings
        if servings is None:
            servings = _default_slot_servings(db, household_id, slot.recipe_id)
        cooked = _take_cooked(slot, unmatched)
        resolved.append((slot, servings, cooked))
    new_meals = sorted((slot.recipe_id, servings) for slot, servings, _cooked in resolved)
    with transaction(db):
        db.execute("DELETE FROM plan_slots WHERE plan_id = ?", (plan_id,))
        for i, (slot, servings, cooked) in enumerate(resolved):
            db.execute(
                """INSERT INTO plan_slots
                   (plan_id, day_index, meal_type, recipe_id, servings, notes, sort, cooked)
                   VALUES (?, ?, ?, ?, ?, '', ?, ?)""",
                (
                    plan_id,
                    slot.day_index,
                    slot.meal_type[:20],
                    slot.recipe_id,
                    servings,
                    i,
                    cooked,
                ),
            )
        if old_meals != new_meals:
            _rebuild_grocery(db, plan_id, household_id)
    return _plan_out(db, plan_id, household_id)


def _owned_slot(db: PgConnection, slot_id: int, household_id: int):
    return db.execute(
        """SELECT s.id, s.plan_id, s.recipe_id, s.servings, s.day_index, s.cooked
           FROM plan_slots s
           JOIN plans p ON p.id = s.plan_id
           WHERE s.id = ? AND p.household_id = ?""",
        (slot_id, household_id),
    ).fetchone()


@router.patch("/slots/{slot_id}")
def patch_slot(
    slot_id: int,
    body: SlotPatch,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    row = _owned_slot(db, slot_id, household_id)
    if not row:
        raise HTTPException(404, {"error": "not_found", "detail": "slot"})
    if (
        body.cooked is None
        and body.servings is None
        and body.day_index is None
        and body.scheduled_date is None
        and not body.unschedule
    ):
        raise HTTPException(400, {"error": "empty_patch", "detail": "slot"})
    if body.scheduled_date is not None:
        start = db.execute("SELECT start_date FROM plans WHERE id = ?", (row["plan_id"],)).fetchone()["start_date"]
        body.day_index = (body.scheduled_date - date.fromisoformat(str(start))).days
        if body.day_index < 0:
            raise HTTPException(400, {"message": "Choose a date on or after the plan starts."})
    rebuild = body.servings is not None and body.servings != row["servings"]
    with transaction(db):
        if body.cooked is not None:
            db.execute(
                "UPDATE plan_slots SET cooked = ? WHERE id = ?",
                (1 if body.cooked else 0, slot_id),
            )
        if body.servings is not None:
            db.execute(
                "UPDATE plan_slots SET servings = ? WHERE id = ?",
                (body.servings, slot_id),
            )
        if body.unschedule:
            db.execute(
                "UPDATE plan_slots SET day_index = NULL WHERE id = ?",
                (slot_id,),
            )
        elif body.day_index is not None:
            db.execute(
                "UPDATE plan_slots SET day_index = ? WHERE id = ?",
                (body.day_index, slot_id),
            )
        if body.day_index is not None and not body.unschedule:
            db.execute("UPDATE plans SET days = CASE WHEN days < ? THEN ? ELSE days END WHERE id = ?",
                       (body.day_index + 1, body.day_index + 1, row["plan_id"]))
        if rebuild:
            _rebuild_grocery(db, row["plan_id"], household_id)
    plan = _plan_out(db, row["plan_id"], household_id)
    slot = next((s for s in plan["slots"] if s["id"] == slot_id), None)
    return slot


@router.delete("/slots/{slot_id}")
def delete_slot(
    slot_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    row = _owned_slot(db, slot_id, household_id)
    if not row:
        raise HTTPException(404, {"error": "not_found", "detail": "slot"})
    with transaction(db):
        db.execute("DELETE FROM plan_slots WHERE id = ?", (slot_id,))
        _rebuild_grocery(db, row["plan_id"], household_id)
    return _plan_out(db, row["plan_id"], household_id)


def _combine_duplicate_grocery_lines(db: PgConnection, plan_id: int) -> dict[int, int]:
    """Combine the same displayed food and placement, including manually added repeats."""
    groups = {}
    remapped = {}
    rows = list(db.execute("SELECT g.*, i.canonical_name FROM grocery_lines g LEFT JOIN ingredients i ON i.id = g.ingredient_id WHERE g.plan_id = ? ORDER BY g.id", (plan_id,)))
    for row in rows:
        name = row["custom_text"] or row["canonical_name"]
        groups.setdefault((pantry_key(name), row["store"], row["aisle"]), []).append(row)
    for group in groups.values():
        if len(group) < 2:
            continue
        keep = next((r for r in group if json.loads(r["source_slots_json"])), group[0])
        quantity = combine_quantities([r["quantity"] for r in group if r["quantity"]])
        meals = {}
        for row in group:
            for meal in _resolve_used_in(db, plan_id, row["source_slots_json"]):
                key = (meal["id"], meal["name"])
                if key in meals:
                    meals[key]["quantity"] = combine_quantities([meals[key]["quantity"], meal["quantity"]])
                else:
                    meals[key] = dict(meal)
            remapped[row["id"]] = keep["id"]
        explicit = any(r["quantity_override"] is not None or (r["quantity"] and not json.loads(r["source_slots_json"])) for r in group)
        db.execute("UPDATE grocery_lines SET quantity = ?, quantity_override = ?, checked = ?, source_slots_json = ? WHERE id = ?", (quantity, quantity if explicit else None, int(all(r["checked"] for r in group)), json.dumps(list(meals.values())), keep["id"]))
        for row in group:
            if row["id"] != keep["id"]:
                db.execute("DELETE FROM grocery_lines WHERE id = ?", (row["id"],))
    return remapped


def _rebuild_grocery(db: PgConnection, plan_id: int, household_id: int) -> None:
    aliases = _aliases(db)
    slot_ings = []
    for s in db.execute(
        """SELECT s.id, s.recipe_id, s.servings, r.name, r.servings AS recipe_servings
           FROM plan_slots s JOIN recipes r ON r.id = s.recipe_id
           WHERE s.plan_id = ?""",
        (plan_id,),
    ):
        edit = _recipe_edit(db, household_id, s["recipe_id"])
        recipe_name = (edit["name"] if edit and edit["name"] else s["name"])
        base_serv = (
            int(edit["servings"])
            if edit and edit["servings"]
            else int(s["recipe_servings"] or 4)
        )
        slot_serv = int(s["servings"] or base_serv)
        factor = Fraction(slot_serv, base_serv) if base_serv else Fraction(1)
        if edit:
            try:
                overlay_ings = json.loads(edit["ingredients_json"] or "[]")
            except json.JSONDecodeError:
                raise
        else:
            overlay_ings = None
        if overlay_ings is not None:
            for ing in overlay_ings:
                slot_ings.append(
                    {
                        "name": ing.get("name") or "",
                        "quantity": scale_quantity(ing.get("quantity") or "", factor),
                        "recipe_id": s["recipe_id"],
                        "recipe_name": recipe_name,
                    }
                )
        else:
            for ing in db.execute(
                """SELECT i.canonical_name, ri.quantity
                   FROM recipe_ingredients ri
                   JOIN ingredients i ON i.id = ri.ingredient_id
                   WHERE ri.recipe_id = ?""",
                (s["recipe_id"],),
            ):
                slot_ings.append(
                    {
                        "name": ing["canonical_name"],
                        "quantity": scale_quantity(ing["quantity"], factor),
                        "recipe_id": s["recipe_id"],
                        "recipe_name": recipe_name,
                    }
                )
    pantry_have = {
        r["name"]
        for r in db.execute(
            "SELECT name FROM pantry_items WHERE household_id = ? AND have = 1",
            (household_id,),
        )
    }
    never = {
        r["name"]
        for r in db.execute(
            "SELECT name FROM pantry_items WHERE household_id = ? AND never_shop = 1",
            (household_id,),
        )
    }
    prev_rows = list(
        db.execute("SELECT * FROM grocery_lines WHERE plan_id = ?", (plan_id,))
    )
    prev = {r["ingredient_id"]: r for r in prev_rows if r["ingredient_id"] is not None}
    prev.update({r["custom_text"]: r for r in prev_rows})
    lines = merge_grocery(slot_ings, pantry_have, never, aliases, _overrides(db, household_id))
    hh = db.execute("SELECT prefs_json FROM households WHERE id = ?", (household_id,)).fetchone()
    try:
        hh_prefs = json.loads((hh["prefs_json"] if hh else None) or "{}")
    except json.JSONDecodeError:
        raise
    auto_check = bool(hh_prefs.get("pantry_auto_check"))
    used_ids = set()
    for line in lines:
        iid = _get_or_create_ingredient(db, line["name"])
        old = prev.get(iid) or prev.get(line["name"])
        if old and old["name_override"] is not None:
            item_name = pantry_key(old["name_override"])
            line["from_pantry"] = any(pantry_key(n) == item_name for n in pantry_have)
            line["never_shop"] = any(pantry_key(n) == item_name for n in never)
        owned_check = auto_check and line["from_pantry"]
        checked = line["checked"] or owned_check
        qty = line["quantity"]
        aisle = line["aisle"]
        store = ""
        if old:
            # Keep where the household put it, even for always-checked staples.
            store = old["store"] if "store" in old.keys() else ""
            aisle = old["aisle"] or aisle
        place = db.execute("SELECT store, aisle FROM grocery_places WHERE household_id = ? AND name = ?",
                           (household_id, pantry_key(old["name_override"] if old and old["name_override"] is not None else line["name"]))).fetchone()
        if place:
            store, aisle = place["store"], place["aisle"]
        if old and not line["never_shop"]:
            used_ids.add(old["id"])
            checked = bool(old["checked"])
            if old["never_shop"]:
                # No longer a staple: back to unchecked unless it's in the pantry.
                checked = owned_check
            elif auto_check and line["from_pantry"] and not old["from_pantry"]:
                checked = True  # just added to the pantry
            elif auto_check and old["from_pantry"] and not line["from_pantry"]:
                checked = False  # just taken out of the pantry
        elif old:
            used_ids.add(old["id"])
        values = (iid, old["quantity_override"] if old and old["quantity_override"] is not None else qty,
                  aisle, store, int(checked), int(line["from_pantry"]), int(line["never_shop"]),
                  old["name_override"] if old and old["name_override"] is not None else line["name"],
                  json.dumps(line["used_in"]))
        if old:
            db.execute("""UPDATE grocery_lines SET ingredient_id = ?, quantity = ?, aisle = ?, store = ?,
                          checked = ?, from_pantry = ?, never_shop = ?, custom_text = ?, source_slots_json = ?
                          WHERE id = ?""", (*values, old["id"]))
        else:
            db.execute("""INSERT INTO grocery_lines (ingredient_id, quantity, aisle, store, checked,
                          from_pantry, never_shop, custom_text, source_slots_json, plan_id)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (*values, plan_id))
    for old in prev_rows:
        if old["id"] not in used_ids and json.loads(old["source_slots_json"] or "[]"):
            db.execute("DELETE FROM grocery_lines WHERE id = ?", (old["id"],))
    _combine_duplicate_grocery_lines(db, plan_id)
    _refresh_prep(db, plan_id, household_id)


@router.post("/plans/{plan_id}/grocery")
def rebuild_grocery(
    plan_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    plan = db.execute(
        "SELECT id FROM plans WHERE id = ? AND household_id = ?",
        (plan_id, household_id),
    ).fetchone()
    if not plan:
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    with transaction(db):
        _rebuild_grocery(db, plan_id, household_id)
    return list_grocery(plan_id, db, household_id)


def _resolve_used_in(db: PgConnection, plan_id: int, raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        raise
    plan_rows = list(
        db.execute(
            """SELECT DISTINCT r.id, r.name, r.photo_path, r.parent_recipe_id,
                      r.cooking_minutes
               FROM plan_slots s
               JOIN recipes r ON r.id = s.recipe_id
               WHERE s.plan_id = ?""",
            (plan_id,),
        )
    )
    by_id = {row["id"]: row for row in plan_rows}
    by_name = {row["name"]: row for row in plan_rows}
    out = []
    seen: set[int] = set()

    def add_row(row, quantity: str = "") -> None:
        rid = row["id"]
        if rid in seen:
            return
        seen.add(rid)
        out.append(
            {
                "id": rid,
                "name": row["name"],
                "photo_path": usable_photo(
                    row["photo_path"] or "", row["id"], row["parent_recipe_id"]
                ),
                "cooking_minutes": row["cooking_minutes"],
                "quantity": quantity,
            }
        )

    def add_name_only(name: str, quantity: str = "") -> None:
        if any(m["name"] == name for m in out):
            return
        out.append(
            {
                "id": None,
                "name": name,
                "photo_path": "",
                "cooking_minutes": None,
                "quantity": quantity,
            }
        )

    if data and isinstance(data[0], dict):
        for item in data:
            rid = item.get("id")
            name = item.get("name") or ""
            quantity = item.get("quantity") or ""
            if rid in by_id:
                add_row(by_id[rid], quantity)
            elif name in by_name:
                add_row(by_name[name], quantity)
            elif rid:
                # "You'll use this in" is about this plan. A recipe id that is no longer on
                # the plan is stale, so it is left out. (The old lookup also raised KeyError,
                # because it didn't select parent_recipe_id.)
                continue
            elif name:
                add_name_only(name, quantity)
    else:
        for name in data:
            if not isinstance(name, str) or not name:
                continue
            if name in by_name:
                add_row(by_name[name])
            else:
                add_name_only(name)
    return out


@router.get("/plans/{plan_id}/grocery")
def list_grocery(
    plan_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    plan = db.execute(
        "SELECT id FROM plans WHERE id = ? AND household_id = ?",
        (plan_id, household_id),
    ).fetchone()
    if not plan:
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    lines = []
    for r in db.execute(
        """SELECT g.*, i.canonical_name, i.package_size, i.package_unit
           FROM grocery_lines g
           LEFT JOIN ingredients i ON i.id = g.ingredient_id
           WHERE g.plan_id = ? ORDER BY g.aisle, g.id""",
        (plan_id,),
    ):
        used_in = _resolve_used_in(db, plan_id, r["source_slots_json"])
        lines.append(
            {
                "id": r["id"],
                "name": r["custom_text"] or r["canonical_name"],
                "ingredient_photo_path": ingredient_photo_path(r["custom_text"] or r["canonical_name"]),
                "quantity": r["quantity"],
                "aisle": r["aisle"],
                "store": r["store"] if "store" in r.keys() else "",
                "package_size": r["package_size"] if "package_size" in r.keys() else "",
                "package_unit": r["package_unit"] if "package_unit" in r.keys() else "",
                "checked": bool(r["checked"]),
                "from_pantry": bool(r["from_pantry"]),
                "never_shop": bool(r["never_shop"]),
                "used_by": [m["name"] for m in used_in if m.get("name")],
                "used_in": used_in,
            }
        )
    return {"lines": lines}


@router.post("/plans/{plan_id}/grocery/lines")
def add_grocery_line(
    plan_id: int,
    body: GroceryLineCreate,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    plan = db.execute(
        "SELECT id FROM plans WHERE id = ? AND household_id = ?",
        (plan_id, household_id),
    ).fetchone()
    if not plan:
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    name = body.name.strip()
    if not name:
        raise HTTPException(400, {"error": "bad_request", "detail": "name"})
    if in_grocery_catalog(name):
        name = preferred_grocery_name(name)
        iid = _get_or_create_ingredient(db, name)
    else:
        iid = None
    aisle = (body.aisle or "").strip() or aisle_for(name)
    store = (body.store or "").strip()
    photo = ingredient_photo_path(name)
    with transaction(db):
        cur = db.execute(
            """INSERT INTO grocery_lines (
                plan_id, ingredient_id, quantity, unit, aisle, store, checked,
                from_pantry, never_shop, custom_text, source_slots_json
            ) VALUES (?, ?, ?, '', ?, ?, 0, 0, 0, ?, '[]')""",
            (plan_id, iid, body.quantity.strip(), aisle, store, name),
        )
        line_id = int(cur.lastrowid)
        line_id = _combine_duplicate_grocery_lines(db, plan_id).get(line_id, line_id)
    return next(line for line in list_grocery(plan_id, db, household_id)["lines"] if line["id"] == line_id)


@router.patch("/grocery/lines/{line_id}")
def patch_grocery(
    line_id: int,
    body: GroceryPatch,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    row = db.execute(
        """SELECT g.id FROM grocery_lines g
           JOIN plans p ON p.id = g.plan_id
           WHERE g.id = ? AND p.household_id = ?""",
        (line_id, household_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, {"error": "not_found", "detail": "line"})
    fields, args = [], []
    if body.checked is not None:
        fields.append("checked = ?")
        args.append(1 if body.checked else 0)
    if body.quantity is not None:
        fields.extend(["quantity = ?", "quantity_override = ?"])
        args.extend([body.quantity, body.quantity])
    if body.custom_text is not None:
        fields.extend(["custom_text = ?", "name_override = ?"])
        args.extend([body.custom_text.strip(), body.custom_text.strip()])
    if body.aisle is not None:
        fields.append("aisle = ?")
        args.append(body.aisle.strip() or "other")
    if body.store is not None:
        fields.append("store = ?")
        args.append(body.store.strip())
    if not fields:
        raise HTTPException(400, {"message": "No grocery changes supplied"})
    args.append(line_id)
    with transaction(db):
        db.execute(f"UPDATE grocery_lines SET {', '.join(fields)} WHERE id = ?", args)
        if body.store is not None or body.aisle is not None:
            line = db.execute("SELECT COALESCE(g.custom_text, i.canonical_name) AS name, g.store, g.aisle FROM grocery_lines g LEFT JOIN ingredients i ON i.id = g.ingredient_id WHERE g.id = ?", (line_id,)).fetchone()
            db.execute("INSERT INTO grocery_places (household_id, name, store, aisle) VALUES (?, ?, ?, ?) ON CONFLICT(household_id, name) DO UPDATE SET store = excluded.store, aisle = excluded.aisle", (household_id, pantry_key(line["name"]), line["store"], line["aisle"]))
    return {"ok": True}


def _pantry_row(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "quantity": r["quantity"],
        "have": bool(r["have"]),
        "never_shop": bool(r["never_shop"]),
        "zone": r["zone"],
    }


def _find_pantry(db: PgConnection, household_id: int, name: str):
    want = preferred_grocery_name(name) or pantry_key(name)
    match = None
    for row in db.execute(
        "SELECT * FROM pantry_items WHERE household_id = ?",
        (household_id,),
    ):
        got = preferred_grocery_name(row["name"]) or pantry_key(row["name"])
        if got != want:
            continue
        if pantry_key(row["name"]) == want:
            return row
        if match is None:
            match = row
    return match


def _merge_pantry_rows(rows) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        name = preferred_grocery_name(row["name"]) or pantry_key(row["name"])
        if not name:
            continue
        item = _pantry_row(row)
        item["name"] = name
        prev = merged.get(name)
        if prev is None:
            merged[name] = item
            continue
        prev["have"] = prev["have"] or item["have"]
        prev["never_shop"] = prev["never_shop"] or item["never_shop"]
        if item["quantity"] and not prev["quantity"]:
            prev["quantity"] = item["quantity"]
    return sorted(merged.values(), key=lambda i: i["name"])


@router.get("/pantry")
def get_pantry(db: PgConnection = DbDep, household_id: int = HhDep):
    items = _merge_pantry_rows(
        db.execute(
            "SELECT * FROM pantry_items WHERE household_id = ? ORDER BY name",
            (household_id,),
        )
    )
    return {"items": items}


@router.get("/pantry/catalog")
def get_pantry_catalog(db: PgConnection = DbDep, household_id: int = HhDep):
    owned = {
        item["name"]: item
        for item in _merge_pantry_rows(
            db.execute(
                "SELECT * FROM pantry_items WHERE household_id = ?",
                (household_id,),
            )
        )
    }
    items = []
    seen = set()
    for name, zone in pantry_catalog():
        seen.add(name)
        row = owned.get(name)
        items.append(
            {
                "id": row["id"] if row else None,
                "name": name,
                "have": row["have"] if row else False,
                "never_shop": row["never_shop"] if row else False,
                "quantity": row["quantity"] if row else "",
                "zone": row["zone"] if row else zone,
                "catalog": True,
            }
        )
    for key, row in owned.items():
        if key in seen:
            continue
        items.append({**row, "catalog": False})
    items.sort(key=lambda i: i["name"].lower())
    return {"items": items}


@router.get("/filter-items")
def list_filter_items(
    q: str = "",
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    """Select specific ingredients for custom allergies/avoids, without invented matches."""
    words = search_tokens(q)
    if not words:
        return {"items": []}
    names = set(_grocery_name_pool(db, household_id))
    names.update(row["canonical_name"] for row in db.execute(
        """SELECT DISTINCT i.canonical_name FROM ingredients i
           JOIN recipe_ingredients ri ON ri.ingredient_id = i.id
           JOIN recipes r ON r.id = ri.recipe_id
           WHERE r.household_id IS NULL OR r.household_id = ?""", (household_id,)))
    return {"items": [{"name": name} for name in filter_item_matches(sorted(names), q)]}


@router.get("/grocery-items")
def list_grocery_items(
    q: str = "",
    limit: int = Query(default=12, ge=1, le=80),
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    pool = _grocery_name_pool(db, household_id)
    hits, note = search_grocery_names(pool, q, limit=limit)
    typed = q.strip()
    lower_hits = {n.lower() for n in hits}
    custom = typed if typed and typed.lower() not in lower_hits else ""
    return {"items": [{"name": n} for n in hits], "note": note, "custom": custom}


@router.put("/pantry")
def put_pantry(
    body: PantryPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    with transaction(db):
        db.execute("DELETE FROM pantry_items WHERE household_id = ?", (household_id,))
        for it in body.items:
            name = preferred_grocery_name(it.name) or pantry_key(it.name)
            if not name:
                continue
            iid = _get_or_create_ingredient(db, name)
            db.execute(
                """INSERT INTO pantry_items
                   (household_id, ingredient_id, name, quantity, have, never_shop, zone)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    household_id,
                    iid,
                    name,
                    it.quantity[:40],
                    1 if it.have else 0,
                    1 if it.never_shop else 0,
                    it.zone[:20],
                ),
            )
        _rebuild_grocery_for_household(db, household_id)
    return get_pantry(db, household_id)


@router.post("/pantry/items")
def upsert_pantry_item(
    body: PantryItemUpsert,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    name = preferred_grocery_name(body.name) or pantry_key(body.name)
    if not name:
        raise HTTPException(400, {"error": "bad_request", "detail": "name"})
    iid = _get_or_create_ingredient(db, name)
    existing = _find_pantry(db, household_id, name)
    quantity = body.quantity if body.quantity is not None else (existing["quantity"] if existing else "")
    with transaction(db):
        if existing:
            keep_id = existing["id"]
            db.execute(
                """UPDATE pantry_items
                   SET name = ?, have = ?, never_shop = ?, quantity = ?, zone = ?, ingredient_id = ?
                   WHERE id = ? AND household_id = ?""",
                (
                    name,
                    1 if body.have else 0,
                    1 if body.never_shop else 0,
                    quantity[:40],
                    body.zone[:20],
                    iid,
                    keep_id,
                    household_id,
                ),
            )
        else:
            cur = db.execute(
                """INSERT INTO pantry_items
                   (household_id, ingredient_id, name, quantity, have, never_shop, zone)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    household_id,
                    iid,
                    name,
                    quantity[:40],
                    1 if body.have else 0,
                    1 if body.never_shop else 0,
                    body.zone[:20],
                ),
            )
            keep_id = int(cur.lastrowid)
        for row in db.execute(
            "SELECT id, name FROM pantry_items WHERE household_id = ?",
            (household_id,),
        ).fetchall():
            if row["id"] == keep_id:
                continue
            other = preferred_grocery_name(row["name"]) or pantry_key(row["name"])
            if other == name:
                db.execute(
                    "DELETE FROM pantry_items WHERE id = ? AND household_id = ?",
                    (row["id"], household_id),
                )
        _rebuild_grocery_for_household(db, household_id)
    row = _find_pantry(db, household_id, name)
    return _pantry_row(row)


@router.delete("/pantry/items/{item_id}")
def delete_pantry_item(item_id: int, db: PgConnection = DbDep, household_id: int = HhDep):
    if not db.execute("SELECT id FROM pantry_items WHERE id = ? AND household_id = ?", (item_id, household_id)).fetchone():
        raise HTTPException(404, {"detail": "Pantry item not found"})
    with transaction(db):
        db.execute("DELETE FROM pantry_items WHERE id = ? AND household_id = ?", (item_id, household_id))
        _rebuild_grocery_for_household(db, household_id)
    return {"ok": True}


@router.patch("/pantry/items/{item_id}")
def patch_pantry_item(
    item_id: int,
    body: PantryPatch,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    row = db.execute(
        "SELECT * FROM pantry_items WHERE id = ? AND household_id = ?",
        (item_id, household_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, {"error": "not_found", "detail": "pantry"})
    fields = []
    args: list = []
    if body.have is not None:
        fields.append("have = ?")
        args.append(1 if body.have else 0)
    if body.never_shop is not None:
        fields.append("never_shop = ?")
        args.append(1 if body.never_shop else 0)
    if body.quantity is not None:
        fields.append("quantity = ?")
        args.append(body.quantity[:40])
    if not fields:
        return _pantry_row(row)
    args.extend([item_id, household_id])
    with transaction(db):
        db.execute(
            f"UPDATE pantry_items SET {', '.join(fields)} WHERE id = ? AND household_id = ?",
            args,
        )
        _rebuild_grocery_for_household(db, household_id)
    row = db.execute(
        "SELECT * FROM pantry_items WHERE id = ? AND household_id = ?",
        (item_id, household_id),
    ).fetchone()
    return _pantry_row(row)


@router.get("/overrides")
def get_overrides(db: PgConnection = DbDep, household_id: int = HhDep):
    items = [
        {"id": r["id"], "from_name": r["from_name"], "to_name": r["to_name"]}
        for r in db.execute(
            "SELECT * FROM household_overrides WHERE household_id = ? ORDER BY from_name",
            (household_id,),
        )
    ]
    return {"items": items}


@router.put("/overrides")
def put_overrides(
    body: OverridesPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    with transaction(db):
        db.execute("DELETE FROM household_overrides WHERE household_id = ?", (household_id,))
        for it in body.items:
            frm = pantry_key(it.from_name)
            to = pantry_key(it.to_name)
            if not frm or not to:
                continue
            db.execute(
                """INSERT INTO household_overrides (household_id, from_name, to_name)
                   VALUES (?, ?, ?)""",
                (household_id, frm, to),
            )
        _rebuild_grocery_for_household(db, household_id)
    return get_overrides(db, household_id)


@router.post("/overrides")
def add_override(
    body: OverrideIn,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    frm = pantry_key(body.from_name)
    to = pantry_key(body.to_name)
    if not frm or not to:
        raise HTTPException(400, {"error": "bad_request", "detail": "names"})
    with transaction(db):
        db.execute(
            "DELETE FROM household_overrides WHERE household_id = ? AND from_name = ?",
            (household_id, frm),
        )
        db.execute(
            """INSERT INTO household_overrides (household_id, from_name, to_name)
               VALUES (?, ?, ?)""",
            (household_id, frm, to),
        )
        _rebuild_grocery_for_household(db, household_id)
    return get_overrides(db, household_id)


@router.delete("/overrides/{override_id}")
def delete_override(
    override_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    with transaction(db):
        db.execute(
            "DELETE FROM household_overrides WHERE id = ? AND household_id = ?",
            (override_id, household_id),
        )
        _rebuild_grocery_for_household(db, household_id)
    return get_overrides(db, household_id)


def _missing_steps(db: PgConnection, household_id: int) -> dict[int, list[str]]:
    """Steps this household added to prep (#21), by recipe, oldest first."""
    added: dict[int, list[str]] = {}
    for r in db.execute(
        "SELECT recipe_id, step_text FROM prep_step_feedback WHERE household_id = ? AND reason = 'missing' "
        "ORDER BY updated_at, step_key", (household_id,),
    ):
        added.setdefault(int(r["recipe_id"]), []).append(r["step_text"])
    return added


def _refresh_prep(db: PgConnection, plan_id: int, household_id: int) -> None:
    """Synchronize derived prep with current household recipe edits, preserving task IDs."""
    slots = []
    added = _missing_steps(db, household_id)
    for slot in db.execute("SELECT recipe_id, servings FROM plan_slots WHERE plan_id = ? ORDER BY sort, id", (plan_id,)):
        row = db.execute("SELECT * FROM recipes WHERE id = ?", (slot["recipe_id"],)).fetchone()
        recipe = _recipe_out(db, row, household_id)
        factor = Fraction(slot["servings"], recipe["servings"])
        slots.append({"recipe_id": recipe["id"], "recipe_name": recipe["name"],
                      "instructions": recipe["instructions"], "added": added.get(recipe["id"], []),
                      "ingredients": [{**ing, "quantity": scale_quantity(ing["quantity"], factor)} for ing in recipe["ingredients"]]})
    existing = {(r["title"], r["linked_slots_json"]): r for r in db.execute("SELECT * FROM prep_tasks WHERE plan_id = ?", (plan_id,))}
    completed = set()
    for row in existing.values():
        details = json.loads(row["details_json"])
        if row["done"]:
            completed.update(f"{m['id']}:{s['key']}" for m in details.get("meals", []) for s in m.get("steps", []))
        completed.update(json.loads(row["completed_steps_json"]))
    retained = set()
    # Completion follows recipe and step identity, even when tasks regroup.
    for index, task in enumerate(prep_from_slots(slots)):
        linked = json.dumps(task["recipe_ids"])
        # Section and item name drive the Weekend prep layout (#21); without them every row
        # lands in "More prep" as "Prep garlic".
        details = json.dumps({"meals": task["meals"], "quantities": task["quantities"], "auto": task["auto"],
                              "section": task.get("section", "other"), "item": task.get("item") or task["title"],
                              "action": task.get("action", "")})
        keys = {f"{m['id']}:{s['key']}" for m in task["meals"] for s in m["steps"]}
        progress = json.dumps(sorted(completed & keys))
        done = int(bool(keys) and keys <= completed)
        old = existing.get((task["title"], linked))
        if old:
            retained.add(old["id"])
            if (old["notes"], old["sort"], old["details_json"], old["done"], old["completed_steps_json"]) != (task["notes"], index, details, done, progress):
                db.execute("UPDATE prep_tasks SET notes = ?, sort = ?, details_json = ?, done = ?, completed_steps_json = ? WHERE id = ?", (task["notes"], index, details, done, progress, old["id"]))
        else:
            db.execute("INSERT INTO prep_tasks (plan_id, title, notes, done, linked_slots_json, sort, details_json, completed_steps_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (plan_id, task["title"], task["notes"], done, linked, index, details, progress))
    for old in existing.values():
        if old["id"] not in retained:
            db.execute("DELETE FROM prep_tasks WHERE id = ?", (old["id"],))


@router.get("/plans/{plan_id}/prep")
def list_prep(
    plan_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    plan = db.execute(
        "SELECT id FROM plans WHERE id = ? AND household_id = ?",
        (plan_id, household_id),
    ).fetchone()
    if not plan:
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    with transaction(db):
        _refresh_prep(db, plan_id, household_id)
    feedback = {
        (int(r["recipe_id"]), r["step_key"]): (int(r["rating"]), r["reason"] or "", r["note"] or "")
        for r in db.execute(
            # A step the household added (#21) isn't a 👍/👎; it is taken back on its own sheet.
            "SELECT recipe_id, step_key, rating, reason, note FROM prep_step_feedback WHERE household_id = ? AND reason <> 'missing'",
            (household_id,),
        )
    }
    tasks = []
    days = _meal_days(db, plan_id)
    for r in db.execute(
        "SELECT * FROM prep_tasks WHERE plan_id = ? ORDER BY sort, id",
        (plan_id,),
    ):
        details = json.loads(r["details_json"])
        votes = []
        for meal in details.get("meals") or []:
            meal.update(days.get(int(meal["id"]), {"day": None, "day_index": None}))
            for step in meal.get("steps") or []:
                rating, reason, note = feedback.get((int(meal["id"]), step["key"]), (0, "", ""))
                step["rating"] = rating
                step["done"] = bool(r["done"]) or f"{meal['id']}:{step['key']}" in json.loads(r["completed_steps_json"])
                votes.append((rating, reason, note))
        # The item's own 👍/👎: what every step in it says, or nothing when they disagree.
        rating = votes[0][0] if votes and all(v[0] == votes[0][0] for v in votes) else 0
        reason = next((why for value, why, _ in votes if value == rating and why), "") if rating < 0 else ""
        # The cook's own words on a 👎 ("notes" is the task's recipe summary).
        reason_note = next((n for value, _, n in votes if value == rating and n), "") if rating < 0 else ""
        tasks.append({"id": r["id"], "title": r["title"], "notes": r["notes"], "done": bool(r["done"]),
                      "rating": rating, "reason": reason, "reason_note": reason_note, "section": "other", "item": r["title"],
                      "action": "", **details})
    return {"tasks": tasks}


def _meal_days(db: PgConnection, plan_id: int) -> dict[int, dict]:
    """Each recipe's first cook day on the plan: {"day": "Mon", "day_index": 0}. Unscheduled
    meals aren't listed. Weekend prep shows these next to each meal's step (#78)."""
    plan = db.execute("SELECT start_date FROM plans WHERE id = ?", (plan_id,)).fetchone()
    try:
        start = date.fromisoformat(str(plan["start_date"])[:10]) if plan else None
    except ValueError:
        start = None
    days: dict[int, dict] = {}
    for r in db.execute(
        "SELECT recipe_id, day_index FROM plan_slots WHERE plan_id = ? AND day_index IS NOT NULL ORDER BY day_index, sort, id",
        (plan_id,),
    ):
        if start is None or int(r["recipe_id"]) in days:
            continue
        when = start + timedelta(days=int(r["day_index"]))
        days[int(r["recipe_id"])] = {"day": when.strftime("%a"), "day_index": int(r["day_index"])}
    return days


def _plan_recipe_sentences(db: PgConnection, plan_id: int, household_id: int) -> list[dict]:
    """Every sentence of every recipe on the plan, the pieces a missing prep step is picked from."""
    meals, seen = [], set()
    for slot in db.execute("SELECT recipe_id FROM plan_slots WHERE plan_id = ? ORDER BY sort, id", (plan_id,)):
        if slot["recipe_id"] in seen:
            continue
        seen.add(slot["recipe_id"])
        row = db.execute("SELECT * FROM recipes WHERE id = ?", (slot["recipe_id"],)).fetchone()
        recipe = _recipe_out(db, row, household_id)
        steps = []
        for number, step in enumerate(recipe["instructions"], start=1):
            text = (step.get("text") or step.get("step") or "").strip()
            for sentence in step_sentences(text) if text else []:
                if sentence and step_key(sentence) not in {s["key"] for s in steps}:
                    steps.append({"key": step_key(sentence), "text": sentence, "step": number})
        meals.append({"id": recipe["id"], "name": recipe["name"], "steps": steps})
    return meals


@router.get("/plans/{plan_id}/prep/missing")
def list_missing_prep(plan_id: int, db: PgConnection = DbDep, household_id: int = HhDep):
    """Recipe steps that aren't in Weekend prep yet, by meal, for "Missing a prep step?" (#21).
    Steps the household already added come back with added=True so they can be taken back."""
    if not db.execute("SELECT id FROM plans WHERE id = ? AND household_id = ?", (plan_id, household_id)).fetchone():
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    with transaction(db):
        _refresh_prep(db, plan_id, household_id)
    in_prep: set[tuple[int, str]] = set()
    for r in db.execute("SELECT details_json FROM prep_tasks WHERE plan_id = ?", (plan_id,)):
        for meal in json.loads(r["details_json"]).get("meals") or []:
            for step in meal.get("steps") or []:
                if not step.get("added"):
                    in_prep.add((int(meal["id"]), step["key"]))
    notes = {
        (int(r["recipe_id"]), r["step_key"]): r["note"]
        for r in db.execute(
            "SELECT recipe_id, step_key, note FROM prep_step_feedback WHERE household_id = ? AND reason = 'missing'",
            (household_id,),
        )
    }
    meals = []
    days = _meal_days(db, plan_id)
    for meal in _plan_recipe_sentences(db, plan_id, household_id):
        steps = []
        for step in meal["steps"]:
            key = (meal["id"], step["key"])
            if key in in_prep:
                continue
            steps.append({**step, "added": key in notes, "note": notes.get(key, "")})
        if steps:
            meals.append({**meal, **days.get(meal["id"], {"day": None, "day_index": None}), "steps": steps})
    # Scheduled meals first, in cook order (#78: the sheet lists meals by day).
    meals.sort(key=lambda m: (m["day_index"] is None, m["day_index"] or 0))
    return {"meals": meals}


@router.put("/plans/{plan_id}/prep/missing")
def put_missing_prep(
    plan_id: int,
    body: PrepMissingPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    """Add a recipe step to Weekend prep that the app skipped, with an optional note on why.
    It shows in this household's prep from now on and is logged for review (GET /dev/prep-feedback)."""
    if not db.execute("SELECT id FROM plans WHERE id = ? AND household_id = ?", (plan_id, household_id)).fetchone():
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    meal = next((m for m in _plan_recipe_sentences(db, plan_id, household_id) if m["id"] == body.recipe_id), None)
    step = next((s for s in meal["steps"] if s["key"] == body.key), None) if meal else None
    if not step:
        raise HTTPException(404, {"error": "not_found", "detail": "recipe step"})
    with transaction(db):
        if body.added:
            db.execute(
                """INSERT INTO prep_step_feedback
                   (household_id, recipe_id, step_key, step_text, category, auto, rating, reason, note, updated_at)
                   VALUES (?, ?, ?, ?, 'Missing prep step', 0, 1, 'missing', ?, ?)
                   ON CONFLICT(household_id, recipe_id, step_key) DO UPDATE SET
                     step_text = excluded.step_text, category = excluded.category, auto = excluded.auto,
                     rating = excluded.rating, reason = excluded.reason, note = excluded.note,
                     updated_at = excluded.updated_at""",
                (household_id, body.recipe_id, body.key, step["text"], body.note.strip(), now()),
            )
        else:
            db.execute(
                "DELETE FROM prep_step_feedback WHERE household_id = ? AND recipe_id = ? AND step_key = ? AND reason = 'missing'",
                (household_id, body.recipe_id, body.key),
            )
        _refresh_prep(db, plan_id, household_id)
    return {"ok": True, "added": body.added}


def _prep_items(details: dict) -> list[tuple[int, str]]:
    return [(int(m["id"]), s["key"]) for m in details.get("meals") or [] for s in m.get("steps") or []]


def _owned_prep_task(db: PgConnection, task_id: int, household_id: int):
    row = db.execute(
        """SELECT t.* FROM prep_tasks t
           JOIN plans p ON p.id = t.plan_id
           WHERE t.id = ? AND p.household_id = ? FOR UPDATE OF t""",
        (task_id, household_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, {"error": "not_found", "detail": "prep"})
    return row


@router.put("/prep/feedback")
def put_prep_feedback(
    body: PrepStepFeedbackPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    """Was this a useful step to do ahead? Logged for review only; it doesn't change what Prep shows."""
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (body.recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    with transaction(db):
        if body.rating:
            db.execute(
                """INSERT INTO prep_step_feedback
                   (household_id, recipe_id, step_key, step_text, category, auto, rating, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(household_id, recipe_id, step_key) DO UPDATE SET
                     step_text = excluded.step_text, category = excluded.category, auto = excluded.auto,
                     rating = excluded.rating, updated_at = excluded.updated_at
                     WHERE prep_step_feedback.reason <> 'missing'""",
                (household_id, body.recipe_id, body.key, body.text, body.category,
                 1 if body.auto else 0, body.rating, now()),
            )
        else:
            db.execute(
                "DELETE FROM prep_step_feedback WHERE household_id = ? AND recipe_id = ? AND step_key = ? AND reason <> 'missing'",
                (household_id, body.recipe_id, body.key),
            )
    return {"ok": True, "rating": body.rating}


@router.put("/prep/{task_id}/feedback")
def put_prep_task_feedback(
    task_id: int,
    body: PrepTaskFeedbackPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    """👍/👎 on a whole prep item: the same vote, and reason, for every meal's step in it.
    Logged for review (GET /dev/prep-feedback); it doesn't change what Prep shows."""
    with transaction(db):
        row = _owned_prep_task(db, task_id, household_id)
        details = json.loads(row["details_json"] or "{}")
        reason = body.reason if body.rating < 0 else ""
        note = body.note.strip() if body.rating < 0 else ""
        for meal in details.get("meals") or []:
            for step in meal.get("steps") or []:
                if body.rating:
                    db.execute(
                        """INSERT INTO prep_step_feedback
                           (household_id, recipe_id, step_key, step_text, category, auto, rating, reason, note, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(household_id, recipe_id, step_key) DO UPDATE SET
                             step_text = excluded.step_text, category = excluded.category,
                             auto = excluded.auto, rating = excluded.rating, reason = excluded.reason,
                             note = excluded.note, updated_at = excluded.updated_at
                             WHERE prep_step_feedback.reason <> 'missing'""",
                        (household_id, int(meal["id"]), step["key"], step.get("text") or "", row["title"],
                         1 if step.get("auto", True) else 0, body.rating, reason, note, now()),
                    )
                else:
                    db.execute(
                        "DELETE FROM prep_step_feedback WHERE household_id = ? AND recipe_id = ? AND step_key = ? AND reason <> 'missing'",
                        (household_id, int(meal["id"]), step["key"]),
                    )
    return {"ok": True, "rating": body.rating, "reason": reason, "note": note}


@router.patch("/prep/{task_id}")
def patch_prep(
    task_id: int,
    body: PrepPatch,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    with transaction(db):
        row = _owned_prep_task(db, task_id, household_id)
        details = json.loads(row["details_json"] or "{}")
        keys = [f"{recipe_id}:{key}" for recipe_id, key in _prep_items(details)]
        db.execute(
            "UPDATE prep_tasks SET done = ?, completed_steps_json = ? WHERE id = ?",
            (int(body.done), json.dumps(keys if body.done else []), task_id),
        )
    return {"ok": True}


@router.put("/prep/{task_id}/steps")
def put_prep_step(
    task_id: int,
    body: PrepStepPatch,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    """Check off one item inside a prep task. The task is done once every item is."""
    with transaction(db):
        row = _owned_prep_task(db, task_id, household_id)
        details = json.loads(row["details_json"] or "{}")
        keys = {f"{recipe_id}:{key}" for recipe_id, key in _prep_items(details)}
        key = f"{body.recipe_id}:{body.key}"
        if key not in keys:
            raise HTTPException(404, {"error": "not_found", "detail": "prep step"})
        completed = keys.copy() if row["done"] else set(json.loads(row["completed_steps_json"])) & keys
        if body.done:
            completed.add(key)
        else:
            completed.discard(key)
        done = bool(keys) and completed == keys
        db.execute("UPDATE prep_tasks SET done = ?, completed_steps_json = ? WHERE id = ?", (int(done), json.dumps(sorted(completed)), task_id))
    return {"ok": True, "done": done}


@router.get("/household")
def get_household_row(db: PgConnection = DbDep, household_id: int = HhDep):
    household_filters(db, household_id)
    row = db.execute("SELECT * FROM households WHERE id = ?", (household_id,)).fetchone()
    if not row:
        raise HTTPException(404, {"error": "not_found", "detail": "household"})
    try:
        prefs = json.loads(row["prefs_json"] or "{}")
    except json.JSONDecodeError:
        raise
    return {"id": row["id"], "name": row["name"], "prefs": prefs}


# "Download my data" (#64): every table that holds this household's own data. Catalog
# recipes, other households, and secrets (password hashes, session and invite tokens) are
# never included.
_EXPORT_TABLES = [
    ("favorites", "household_favorites"), ("try_later", "household_try_later"),
    ("hidden_recipes", "household_hidden_recipes"), ("meal_ratings", "household_meal_ratings"),
    ("prep_feedback", "prep_step_feedback"), ("pantry", "pantry_items"),
    ("substitutions", "household_overrides"), ("recipe_edits", "household_recipe_edits"),
    ("stores_and_aisles", "grocery_places"), ("submissions", "recipe_submissions"),
    ("plan_reports", "plan_reports"), ("recipe_reports", "recipe_reports"),
    ("feedback", "feedback"),
]
_EXPORT_SECRET_COLUMNS = {"password_hash", "token", "token_hash", "household_id"}


def _rows(cursor) -> list[dict]:
    out = []
    for r in cursor:
        row = {k: r[k] for k in r.keys() if k not in _EXPORT_SECRET_COLUMNS}
        for k, v in list(row.items()):
            if k.endswith("_json") and isinstance(v, str):
                try:
                    row[k[:-5]] = json.loads(v)
                    del row[k]
                except json.JSONDecodeError:
                    pass
        out.append(row)
    return out


@router.get("/household/export")
def export_household(request: Request, db: PgConnection = DbDep, household_id: int = HhDep):
    """Everything stored for this household, as one JSON file to download (#64).

    When Taste Lab's store is offline the rest still downloads, marked `complete: false` with
    what's missing, so the app can say so and offer a retry (#101)."""
    missing: list[str] = []
    try:
        household_filters(db, household_id)  # Fold old Taste Lab filters in, so the file has them.
    except Exception:
        _log.exception("Export couldn't fold Taste Lab filters for household %s", household_id)
        missing.append("taste_lab_filters")
    home = db.execute("SELECT name, prefs_json, created_at FROM households WHERE id = ?", (household_id,)).fetchone()
    if not home:
        raise HTTPException(404, {"error": "not_found", "detail": "household"})
    data: dict = {
        "exported_at": now(),
        "about": "Everything Dinnerdesk stores for your household. Passwords and sign-in tokens are never included.",
        "household": {"name": home["name"], "created_at": home["created_at"],
                      "prefs": json.loads(home["prefs_json"] or "{}")},
        "members": _rows(db.execute(
            "SELECT email, created_at FROM users WHERE household_id = ? ORDER BY id", (household_id,))),
        "recipes_you_added": _rows(db.execute(
            "SELECT * FROM recipes WHERE household_id = ? ORDER BY id", (household_id,))),
        "plans": [],
    }
    # Your own sign-in details. Other members' recovery emails stay private to them.
    account = session_info(db, request.cookies.get(SESSION_COOKIE))
    if account:
        data["your_account"] = _rows(db.execute(
            "SELECT email, recovery_email, email_verified_at, created_at FROM users WHERE id = ?",
            (account["user_id"],)))[0]
    for recipe in data["recipes_you_added"]:
        recipe["ingredients"] = _rows(db.execute(
            """SELECT ri.ingredient_id, i.canonical_name AS name,
                      ri.quantity, ri.unit, ri.note, ri.sort
               FROM recipe_ingredients ri JOIN ingredients i ON i.id = ri.ingredient_id
               WHERE ri.recipe_id = ? ORDER BY ri.sort, ri.ingredient_id""", (recipe["id"],)))
        recipe["tags"] = _recipe_tags(db, recipe["id"])
    for plan in _rows(db.execute("SELECT * FROM plans WHERE household_id = ? ORDER BY id", (household_id,))):
        pid = plan["id"]
        plan["meals"] = _rows(db.execute(
            """SELECT s.day_index, s.meal_type, s.servings, s.cooked, s.notes, r.name AS recipe
               FROM plan_slots s JOIN recipes r ON r.id = s.recipe_id
               WHERE s.plan_id = ? ORDER BY s.sort, s.id""", (pid,)))
        plan["grocery_list"] = _rows(db.execute("SELECT * FROM grocery_lines WHERE plan_id = ? ORDER BY id", (pid,)))
        plan["prep"] = _rows(db.execute("SELECT title, done, notes FROM prep_tasks WHERE plan_id = ? ORDER BY sort, id", (pid,)))
        data["plans"].append(plan)
    for key, table in _EXPORT_TABLES:
        data[key] = _rows(db.execute(f"SELECT * FROM {table} WHERE household_id = ?", (household_id,)))
    accounts = [str(r["id"]) for r in db.execute("SELECT id FROM users WHERE household_id = ?", (household_id,))]
    try:
        data["taste_lab"] = snapshots_for_accounts([*accounts, f"guest:{household_id}"])
    except Exception:  # Taste Lab's own store can be offline; the rest of the export still works.
        _log.exception("Export couldn't read Taste Lab for household %s", household_id)
        data["taste_lab"] = "unavailable right now"
        missing.append("taste_lab")
    data["complete"] = not missing
    data["missing"] = missing
    return JSONResponse(
        data, headers={"Content-Disposition": f'attachment; filename="dinnerdesk-data-{date.today().isoformat()}.json"'})


@router.put("/household")
def put_household(
    body: HouseholdPut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    # Fold old Taste Lab filters in before this save, so a later read can't add them back on top.
    household_filters(db, household_id)
    row = db.execute("SELECT * FROM households WHERE id = ?", (household_id,)).fetchone()
    if not row:
        raise HTTPException(404, {"error": "not_found", "detail": "household"})
    try:
        prefs = json.loads(row["prefs_json"] or "{}")
    except json.JSONDecodeError:
        raise
    removed_stores = set()
    if body.prefs is not None:
        grocery = body.prefs.get("grocery")
        if isinstance(grocery, dict) and "stores" in grocery:
            previous = {store["id"] for store in prefs.get("grocery", {}).get("stores", [])}
            current = {store["id"] for store in grocery["stores"]}
            removed_stores = previous - current
        saved_filters = prefs.get("filters")
        prefs.update(body.prefs)
        if isinstance(body.prefs.get("filters"), dict):
            # Settings, the tour and Taste Lab each send only what they show; merge so one
            # screen can't wipe another's choices. Diets rule each other out; "none" isn't an avoid.
            prefs["filters"] = merge_filters(saved_filters, body.prefs["filters"])
    name = body.name.strip() if body.name else row["name"]
    with transaction(db):
        db.execute(
            "UPDATE households SET name = ?, prefs_json = ? WHERE id = ?",
            (name, json.dumps(prefs), household_id),
        )
        for store_id in removed_stores:
            db.execute("UPDATE grocery_places SET store = '' WHERE household_id = ? AND store = ?", (household_id, store_id))
            db.execute("UPDATE grocery_lines SET store = '' WHERE store = ? AND plan_id IN (SELECT id FROM plans WHERE household_id = ?)", (store_id, household_id))
        if body.prefs is not None and "pantry_auto_check" in body.prefs:
            # Turning the switch on or off checks or unchecks pantry items on this week's list.
            plan_id = _plan_id_for_household(db, household_id)
            if plan_id is not None:
                db.execute(
                    "UPDATE grocery_lines SET checked = ? WHERE plan_id = ? AND from_pantry = 1 AND never_shop = 0",
                    (1 if body.prefs["pantry_auto_check"] else 0, plan_id),
                )
    return get_household_row(db, household_id)


@router.get("/dev/prep-feedback")
def get_prep_feedback(_admin=AdminDep, db: PgConnection = DbDep):
    """Every prep-step vote across households, for deciding whether the picker,
    the recipe, or nothing needs to change. Newest first."""
    rows = [
        {
            "recipe_id": r["recipe_id"],
            "recipe_name": r["recipe_name"],
            "household_id": r["household_id"],
            "category": r["category"],
            "step": r["step_text"],
            "picked_by": "app" if r["auto"] else "recipe tag",
            "rating": r["rating"],
            "reason": r["reason"] or "",
            "note": r["note"] or "",
            "updated_at": r["updated_at"],
        }
        for r in db.execute(
            """SELECT f.*, r.name AS recipe_name
               FROM prep_step_feedback f JOIN recipes r ON r.id = f.recipe_id
               ORDER BY f.updated_at DESC"""
        )
    ]
    by_category: dict[str, dict[str, int]] = {}
    for row in rows:
        tally = by_category.setdefault(row["category"] or "(none)", {"up": 0, "down": 0})
        tally["up" if row["rating"] > 0 else "down"] += 1
    return {"votes": rows, "by_category": by_category}


@router.post("/plans/{plan_id}/report")
def report_plan(plan_id: int, body: PlanReportCreate, db: PgConnection = DbDep, household_id: int = HhDep):
    """Report a bad suggestion. Saves the note with the plan as it is now and its suggestion
    context (filters, pantry, taste, each meal's score and reasons when it was suggested)."""
    if not db.execute("SELECT id FROM plans WHERE id = ? AND household_id = ?", (plan_id, household_id)).fetchone():
        raise HTTPException(404, {"error": "not_found", "detail": "plan"})
    snapshot = {"plan": _plan_out(db, plan_id, household_id), "filters_when_reported": household_filters(db, household_id)}
    with transaction(db):
        cur = db.execute(
            "INSERT INTO plan_reports (household_id, plan_id, note, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (household_id, plan_id, body.note.strip(), json.dumps(snapshot), now()),
        )
    return {"ok": True, "id": int(cur.lastrowid)}


@router.post("/recipes/{recipe_id}/report")
def report_recipe(recipe_id: int, body: RecipeReportCreate, db: PgConnection = DbDep, household_id: int = HhDep):
    """Report a problem with a recipe. Saves the recipe as this household sees it now (with its
    edits) and how it stands against their filters, so a diet or allergy report shows whether
    the filter let it through or the recipe is mislabeled."""
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    shown = _recipe_out(db, row, household_id)
    diets, allergens, avoids, _ = _filter_prefs(db, household_id)
    name, names = shown.get("name") or "", [i.get("name") or "" for i in shown.get("ingredients") or []]
    hard, soft = blocks_for(diets, allergens), blocks_for([], avoids)
    snapshot = {
        "recipe": shown,
        "filters": {"diets": diets, "allergens": allergens, "avoids": avoids},
        "passes_diets_and_allergies": diet_allowed(name, names, hard),
        "matched_diet_or_allergy_words": matched_words(name, names, hard),
        "matched_avoid_words": matched_words(name, names, soft),
    }
    with transaction(db):
        cur = db.execute(
            "INSERT INTO recipe_reports (household_id, recipe_id, reason, note, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (household_id, recipe_id, body.reason, body.note.strip(), json.dumps(snapshot), now()),
        )
    return {"ok": True, "id": int(cur.lastrowid)}


@router.get("/dev/recipe-reports")
def get_recipe_reports(_admin=AdminDep, db: PgConnection = DbDep):
    """Every recipe report across households, newest first, for deciding what to fix."""
    return {"reports": [
        {"id": r["id"], "household_id": r["household_id"], "household_name": r["household_name"],
         "recipe_id": r["recipe_id"], "recipe_name": r["recipe_name"], "reason": r["reason"], "note": r["note"],
         "created_at": r["created_at"], "snapshot": json.loads(r["snapshot_json"] or "{}")}
        for r in db.execute(
            """SELECT p.*, h.name AS household_name, rc.name AS recipe_name FROM recipe_reports p
               LEFT JOIN households h ON h.id = p.household_id
               LEFT JOIN recipes rc ON rc.id = p.recipe_id ORDER BY p.created_at DESC"""
        )
    ]}


@router.get("/dev/plan-reports")
def get_plan_reports(_admin=AdminDep, db: PgConnection = DbDep):
    """Every meal plan report across households, newest first, for deciding what to fix."""
    return {"reports": [
        {"id": r["id"], "household_id": r["household_id"], "household_name": r["household_name"],
         "plan_id": r["plan_id"], "note": r["note"], "created_at": r["created_at"],
         "snapshot": json.loads(r["snapshot_json"] or "{}")}
        for r in db.execute(
            """SELECT p.*, h.name AS household_name FROM plan_reports p
               LEFT JOIN households h ON h.id = p.household_id ORDER BY p.created_at DESC"""
        )
    ]}


def server_build() -> str:
    """The deployed commit, short (Railway sets RAILWAY_GIT_COMMIT_SHA), or "" when unknown."""
    return (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "")[:7]


IOS_BUILD = re.compile(r"ios (\S+) \((\d+)\)")


def _app_versions(rows) -> dict[int, dict]:
    """Which version sent each report, and whether it was behind. A web page is behind when
    its build isn't the server's at the time (an old tab); an iOS build is behind when a newer
    one has sent a report since."""
    builds = [(int(m[2]), m[0]) for r in rows if (m := IOS_BUILD.fullmatch(r["snapshot"].get("app") or ""))]
    newest = max(builds, default=(0, ""))
    out = {}
    for r in rows:
        app, server = r["snapshot"].get("app") or "", r["snapshot"].get("server") or ""
        behind = ""
        if app.startswith("web ") and server and app[4:] != server:
            behind = f"server was on {server}"
        elif (m := IOS_BUILD.fullmatch(app)) and int(m[2]) < newest[0]:
            behind = f"newest is {newest[1]}"
        out[r["id"]] = {"version": app or "unknown", "behind": behind}
    return out


@router.post("/feedback")
def send_feedback(body: FeedbackCreate, request: Request, db: PgConnection = DbDep, household_id: int = HhDep):
    """Report a bug or suggest a feature (#145). Keeps which app and build sent it, so a bug
    can be matched to the version that had it."""
    note = body.note.strip()
    if not note:
        raise HTTPException(422, {"error": "invalid", "detail": "note"})
    account = session_info(db, request.cookies.get(SESSION_COOKIE))
    # Saved before the row; a bad image stops the report with a clear message instead.
    screenshots = [save_screenshot(data) for data in body.screenshots]
    snapshot = {
        "app": request.headers.get("x-dinnerdesk-app", ""),
        "server": server_build(),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "screen": body.screen.strip(),
        "screenshots": screenshots,
    }
    ts = now()
    with transaction(db):
        cur = db.execute(
            "INSERT INTO feedback (household_id, user_id, kind, note, status, snapshot_json, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'new', ?, ?, ?)",
            (household_id, account["user_id"] if account else None, body.kind, note, json.dumps(snapshot), ts, ts),
        )
    return {"ok": True, "id": int(cur.lastrowid)}


@router.get("/dev/feedback")
def get_feedback(_admin=AdminDep, db: PgConnection = DbDep):
    """Every bug report and feature request across households, newest first."""
    rows = [
        {"id": r["id"], "household_id": r["household_id"], "household_name": r["household_name"],
         "email": r["email"], "kind": r["kind"], "note": r["note"], "status": r["status"],
         "created_at": r["created_at"], "updated_at": r["updated_at"],
         "snapshot": json.loads(r["snapshot_json"] or "{}"),
         "screenshots": [f"/api/dev/feedback/{r['id']}/screenshots/{i}"
                         for i in range(len(json.loads(r["snapshot_json"] or "{}").get("screenshots") or []))]}
        for r in db.execute(
            """SELECT f.*, h.name AS household_name, u.email AS email FROM feedback f
               LEFT JOIN households h ON h.id = f.household_id
               LEFT JOIN users u ON u.id = f.user_id ORDER BY f.created_at DESC, f.id DESC"""
        )
    ]
    versions = _app_versions(rows)
    return {"feedback": [{**r, **versions[r["id"]]} for r in rows]}


@router.get("/dev/feedback/{feedback_id}/screenshots/{index}")
def get_feedback_screenshot(feedback_id: int, index: int, _admin=AdminDep, db: PgConnection = DbDep):
    """A screenshot sent with a report. Admins only: screenshots can show private details."""
    row = db.execute("SELECT snapshot_json FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
    names = json.loads(row["snapshot_json"] or "{}").get("screenshots") or [] if row else []
    if not 0 <= index < len(names):
        raise HTTPException(404, {"error": "not_found", "detail": "screenshot"})
    path = feedback_dir() / names[index]
    if not path.is_file():
        raise HTTPException(404, {"error": "not_found", "detail": "screenshot"})
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.put("/dev/feedback/{feedback_id}/status")
def set_feedback_status(feedback_id: int, body: FeedbackStatusPut, _admin=AdminDep, db: PgConnection = DbDep):
    """Mark a report or request new, planned, done, or declined."""
    if not db.execute("SELECT id FROM feedback WHERE id = ?", (feedback_id,)).fetchone():
        raise HTTPException(404, {"error": "not_found", "detail": "feedback"})
    with transaction(db):
        db.execute("UPDATE feedback SET status = ?, updated_at = ? WHERE id = ?", (body.status, now(), feedback_id))
    return {"ok": True}


@router.get("/dev/ingredient-review")
def get_ingredient_review(_admin=AdminDep):
    groups = review_groups(ROOT)
    return {
        "groups": groups,
        "counts": {
            queue: sum(
                1
                for group in groups
                if group["queue"] == queue
                and group["answer"].get("status") != "answered"
            )
            for queue in ("easy", "harder")
        },
        "answered": sum(
            1 for group in groups if group["answer"].get("status") == "answered"
        ),
        "second_review": {
            "total": sum(
                1
                for group in groups
                if group["audit"]
                and group["audit"].get("review_status") != "removed"
            ),
            "resolved": sum(
                1
                for group in groups
                if group["audit"].get("review_status") == "resolved"
            ),
        },
        "sources": ["allrecipes", "mealime", "myplate"],
        "proposal_only": True,
    }


@router.get("/dev/ingredient-review/flagged")
def get_flagged_recipes(_admin=AdminDep):
    rows = collect_flagged_recipes(ROOT)
    save_flagged_recipes(ROOT, rows)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["reason"], []).append(row)
    return {
        "count": len(rows),
        "proposal_only": True,
        "reasons": [
            {"reason": reason, "count": len(items), "recipes": items}
            for reason, items in grouped.items()
        ],
    }


@router.put("/dev/ingredient-review/{group_id}/notes")
def put_ingredient_review_notes(
    group_id: str,
    body: IngredientReviewNotes,
    _admin=AdminDep,
):
    save_group_notes(ROOT, group_id, body.notes)
    return {"ok": True}


@router.put("/dev/ingredient-review/{group_id}/answer")
def put_ingredient_review_answer(
    group_id: str,
    body: IngredientReviewAnswer,
    _admin=AdminDep,
):
    try:
        save_group_answer(
            ROOT,
            group_id,
            body.action,
            body.target,
            body.names,
        )
    except KeyError:
        raise HTTPException(
            404, {"error": "not_found", "detail": "review group"}
        ) from None
    except ValueError as exc:
        raise HTTPException(
            400, {"error": "invalid", "detail": str(exc)}
        ) from None
    return {"ok": True, "proposal_only": True}


@router.put("/dev/ingredient-review/{group_id}/audit")
def put_ingredient_review_audit(
    group_id: str,
    body: IngredientReviewAudit,
    _admin=AdminDep,
):
    try:
        save_group_audit(
            ROOT,
            group_id,
            body.verdict,
            body.reason,
            body.suggested_action,
            body.suggested_target,
            body.suggested_names,
        )
    except KeyError:
        raise HTTPException(
            404, {"error": "not_found", "detail": "answered review group"}
        ) from None
    except ValueError as exc:
        raise HTTPException(
            400, {"error": "invalid", "detail": str(exc)}
        ) from None
    return {"ok": True, "proposal_only": True}


@router.put("/dev/ingredient-review/{group_id}/audit-resolution")
def put_ingredient_review_audit_resolution(
    group_id: str,
    body: IngredientReviewAuditResolution,
    _admin=AdminDep,
):
    try:
        resolve_group_audit(ROOT, group_id, body.resolution)
    except KeyError:
        raise HTTPException(
            404, {"error": "not_found", "detail": "audit record"}
        ) from None
    return {"ok": True, "proposal_only": True}


@router.get("/templates")
def list_templates(db: PgConnection = DbDep):
    public_sql, public_args = public_recipe_sql("r")
    rows = db.execute(
        f"""SELECT r.id, r.name, r.slug, r.photo_path FROM recipes r
            WHERE r.household_id IS NULL AND {public_sql}""",
        public_args,
    ).fetchall()
    by_name = {}
    by_slug = {}
    for r in rows:
        by_name.setdefault((r["name"] or "").strip().lower(), r)
        if r["slug"]:
            by_slug[str(r["slug"])] = r
    root = catalog_dir() / "templates"
    families = []
    if root.is_dir():
        for path in sorted(root.rglob("recipes.json")):
            data = json.loads(path.read_text())
            resolved = []
            photo = ""
            for item in data.get("recipes") or []:
                name = (item.get("name") or "").strip()
                row = by_name.get(name.lower()) or by_slug.get(str(item.get("id") or ""))
                if not row:
                    continue
                resolved.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "photo_path": usable_photo(row["photo_path"] or "", row["id"]),
                    }
                )
                shown = usable_photo(row["photo_path"] or "", row["id"])
                if not photo and shown:
                    photo = shown
            families.append(
                {
                    "id": data.get("family") or path.parent.name,
                    "name": (data.get("family") or path.parent.name).replace("_", " "),
                    "photo_path": photo,
                    "recipes": resolved,
                }
            )
    return {"families": families}


def _filter_prefs(db: PgConnection, household_id: int) -> tuple[list, list, list, int | None]:
    """Diets and allergies (hard rules), avoids (soft), and max cook time."""
    filters = household_filters(db, household_id)
    time = filters.get("time")
    max_minutes = int(time) if str(time or "").isdigit() else None
    return filters["diets"], filters["allergens"], filters["avoids"], max_minutes


# Per-household recipe pools (app.domain.pool). Built once and kept until the household's
# filters change (the key no longer matches) or its recipes or the catalog change
# (_invalidate_pool, which callers must run after their transaction commits). Sync routes
# run on a thread pool, so every access holds _POOL_LOCK. The generation counters stop a
# build that began before an invalidation from storing rows read before that commit.
_POOLS: OrderedDict[int, tuple[tuple, Pool]] = OrderedDict()
_POOL_MAX = 1000  # households kept; the least recently used is dropped past this
_POOL_LOCK = threading.Lock()
_POOL_GEN: dict[int, int] = {}
_POOL_GLOBAL_GEN = 0


def _pool_generation(household_id: int) -> tuple[int, int]:
    return _POOL_GLOBAL_GEN, _POOL_GEN.get(household_id, 0)


def _store_pool(household_id: int, gen: tuple[int, int], key: tuple, pool: Pool) -> None:
    with _POOL_LOCK:
        if _pool_generation(household_id) != gen:
            return  # invalidated mid-build; what we read may predate that commit
        _POOLS[household_id] = (key, pool)
        _POOLS.move_to_end(household_id)
        while len(_POOLS) > _POOL_MAX:
            _POOLS.popitem(last=False)


def _household_pool(db: PgConnection, household_id: int, diets: list, allergens: list, avoids: list) -> tuple[Pool, bool]:
    """This household's recipe pool, and whether it was already built."""
    key = filters_key(diets, allergens, avoids)
    with _POOL_LOCK:
        entry = _POOLS.get(household_id)
        if entry and entry[0] == key:
            _POOLS.move_to_end(household_id)
            return entry[1], True
        gen = _pool_generation(household_id)
    pool = build_pool(
        _load_household_recipes(db, household_id),
        blocks_for(diets, allergens),
        blocks_for([], avoids),
        TASTE_SKIP,
    )
    _store_pool(household_id, gen, key, pool)
    return pool, False


def _load_household_recipes(db: PgConnection, household_id: int) -> list[dict]:
    """Every recipe this household can see, with what build_pool needs to sort it."""
    public_sql, public_args = public_recipe_sql("r")
    rows = db.execute(
        f"""SELECT r.id, r.name, r.slug, r.source_url, r.household_id, r.provenance_json,
                   COALESCE(NULLIF(e.name, ''), r.name) AS display_name,
                   COALESCE(e.cooking_minutes, r.cooking_minutes) AS minutes,
                   e.ingredients_json AS edited_ingredients,
                   h.recipe_id IS NOT NULL AS hidden
            FROM recipes r
            LEFT JOIN household_recipe_edits e
              ON e.recipe_id = r.id AND e.household_id = ?
            LEFT JOIN household_hidden_recipes h
              ON h.recipe_id = r.id AND h.household_id = ?
            WHERE (r.household_id IS NULL OR r.household_id = ?)
              AND {public_sql}""",
        (household_id, household_id, household_id, *public_args),
    ).fetchall()
    if not rows:
        return []

    rid_list = [int(row["id"]) for row in rows]
    marks = ",".join("?" for _ in rid_list)

    tags_by: dict[int, set[str]] = {}
    for tag in db.execute(
        f"SELECT recipe_id, tag FROM recipe_tags WHERE recipe_id IN ({marks})",
        rid_list,
    ):
        tags_by.setdefault(int(tag["recipe_id"]), set()).add(tag["tag"])

    ings_by: dict[int, list[str]] = {}
    for item in db.execute(
        f"""SELECT ri.recipe_id, i.canonical_name
           FROM recipe_ingredients ri
           JOIN ingredients i ON i.id = ri.ingredient_id
           WHERE ri.recipe_id IN ({marks})
           ORDER BY ri.recipe_id, ri.sort""",
        rid_list,
    ):
        ings_by.setdefault(int(item["recipe_id"]), []).append(item["canonical_name"])

    recipes = []
    for row in rows:
        rid = int(row["id"])
        key = archive_id(row)
        keys = [str(rid)]
        if key not in keys:
            keys.append(key)
        # Filters check this kitchen's edited ingredient list when it has one.
        edited = [i.get("name") or "" for i in json.loads(row["edited_ingredients"] or "[]")]
        recipes.append(
            {
                "id": rid,
                "keys": keys,
                "slug": row["slug"],
                "name": row["display_name"],
                "ingredients": ings_by.get(rid) or [],
                "filter_ingredients": [i for i in edited if i],
                "tags": sorted(tags_by.get(rid, set())),
                "cooking_minutes": row["minutes"],
                "own": row["household_id"] == household_id,
                "hidden": bool(row["hidden"]),
                "variant_of": json.loads(row["provenance_json"] or "{}").get("variant_of") or None,
            }
        )
    return recipes


def _invalidate_pool(household_id: int) -> None:
    """Drop one household's pool after its own recipe data changes commit."""
    with _POOL_LOCK:
        _POOL_GEN[household_id] = _POOL_GEN.get(household_id, 0) + 1
        _POOLS.pop(household_id, None)


def _invalidate_all_pools() -> None:
    """Drop every household's pool after a global catalog change commits."""
    global _POOL_GLOBAL_GEN
    with _POOL_LOCK:
        _POOL_GLOBAL_GEN += 1
        _POOL_GEN.clear()  # the global bump already outdates every in-flight build
        _POOLS.clear()


# Shown on a meal picked from the backup tier, when too few meals keep every preference.
BACKUP_REASON = "backup pick: not enough meals fit all your preferences"


# What the latest _suggest_meals call in this request worked with, so the plan it becomes can
# keep the why: the filters, pantry and taste then, and each meal's score and reasons. A plan
# report (#141 follow-up) shows it next to the cook's complaint.
_SUGGEST_CONTEXT: contextvars.ContextVar[dict | None] = contextvars.ContextVar("suggest_context", default=None)


def _rank_inputs(db: PgConnection, household_id: int, kept: set[int], laps: Laps | None = None) -> dict:
    """Everything a household's ranking reads, so a suggestion's stamp covers exactly that."""
    laps = laps or Laps()
    filters = household_filters(db, household_id)
    diets, allergens, avoids, max_minutes = _filter_prefs(db, household_id)
    pool, pool_hit = _household_pool(db, household_id, diets, allergens, avoids)
    laps.lap("pool")
    selected_ingredients = []
    for rid in sorted(kept):
        row = db.execute("SELECT * FROM recipes WHERE id = ?", (rid,)).fetchone()
        if row and _recipe_visible(row, household_id):
            selected_ingredients.extend(i["name"] for i in _recipe_out(db, row, household_id)["ingredients"])
    laps.lap("kept")
    aliases = _aliases(db)
    swaps = _overrides(db, household_id)
    pantry = norm_pantry(
        [r["name"] for r in db.execute(
            "SELECT name FROM pantry_items WHERE household_id = ? AND have = 1 AND never_shop = 0",
            (household_id,),
        )],
        aliases,
        swaps,
    )
    ignored = norm_pantry(
        [r["name"] for r in db.execute(
            "SELECT name FROM pantry_items WHERE household_id = ? AND never_shop = 1",
            (household_id,),
        )],
        aliases,
        swaps,
    )
    laps.lap("pantry")
    accounts = [
        str(r["id"])
        for r in db.execute("SELECT id FROM users WHERE household_id = ?", (household_id,))
    ]
    accounts.append(f"guest:{household_id}")
    # Settings → Filters is the one filter system (Taste Lab edits it too), so the diet,
    # allergy and avoid lists inside old Taste Lab snapshots no longer apply here.
    snapshots = [
        {k: v for k, v in snap.items() if k != "profile"} for snap in snapshots_for_accounts(accounts)
    ]
    laps.lap("snapshots")
    rated = _meal_ratings(db, household_id)
    history = [(int(row["id"]), json.loads(row["suggestion_json"] or "{}")) for row in db.execute(
        "SELECT id, suggestion_json FROM plans WHERE household_id = ? ORDER BY id", (household_id,))]
    laps.lap("history")
    cooked = {
        int(row["recipe_id"])
        for row in db.execute(
            """SELECT DISTINCT s.recipe_id FROM plan_slots s
               JOIN plans p ON p.id = s.plan_id
               WHERE p.household_id = ? AND s.cooked = 1""",
            (household_id,),
        )
    }
    return {
        "filters": filters, "diets": diets, "allergens": allergens, "avoids": avoids, "max_minutes": max_minutes,
        "pool": pool, "pool_hit": pool_hit, "kept": kept, "selected_ingredients": selected_ingredients,
        "aliases": aliases, "swaps": swaps, "pantry": pantry, "ignored": ignored, "snapshots": snapshots,
        "rated": rated, "history": history, "favorites": _favorite_ids(db, household_id),
        "to_try": _try_ids(db, household_id), "cooked": cooked,
    }


def _suggest_meals(db: PgConnection, household_id: int, want: int, kept_recipe_ids: set[int] | None = None) -> tuple[list[dict], str, dict]:
    kept = kept_recipe_ids or set()
    laps = Laps()
    inputs = _rank_inputs(db, household_id, kept, laps)
    diets, allergens, avoids, max_minutes = inputs["diets"], inputs["allergens"], inputs["avoids"], inputs["max_minutes"]
    pool, pool_hit = inputs["pool"], inputs["pool_hit"]
    selected_ingredients, aliases, swaps = inputs["selected_ingredients"], inputs["aliases"], inputs["swaps"]
    pantry, ignored, snapshots, rated = inputs["pantry"], inputs["ignored"], inputs["snapshots"], inputs["rated"]
    favorites, to_try, cooked = inputs["favorites"], inputs["to_try"], inputs["cooked"]
    recipes = [recipe for recipe in pool.meals if recipe["id"] not in kept]
    backup = [recipe for recipe in pool.backup_meals if recipe["id"] not in kept]
    laps.counts.update(want=want, candidates=len(recipes), backup=len(backup), pool="hit" if pool_hit else "built")
    # Plan thumbs count like Taste Lab swipes: a 👎 drops the meal, a 👍 boosts it and similar meals.
    if rated:
        snapshots = [*snapshots, {
            "account_id": f"household-{household_id}-ratings",
            "swipes": [{"recipe_id": str(rid), "liked": up > 0} for rid, up in rated.items()],
        }]
    history = [h for _, h in inputs["history"]]
    # Approvals are plan-level signals; refusals and swaps are graded evidence, not bans.
    snapshots = [*snapshots, {"account_id": f"household-{household_id}-suggestions", "plans": [
        {"verdict": "up", "recipe_ids": h.get("suggested_recipe_ids", [])}
        for h in history if h.get("decision") == "approve"]}]
    # Diets, allergies and avoids are already applied by the pool, so learn gets none of them.
    taste = learn(
        snapshots,
        recipes + backup,
        max_minutes=max_minutes,
        aliases=aliases,
        overrides=swaps,
        skip=ignored,
    )
    taste.suggestion_penalties = suggestion_penalties(history)
    taste.diets = diets
    filters = household_filters(db, household_id)
    taste.soft = {
        "cuisines": filters.get("cuisines") or [],
        "protein_more": filters.get("protein_more") or [],
        "protein_less": filters.get("protein_less") or [],
    }
    promote(taste, recipes + backup, {rid for rid, up in rated.items() if up > 0})
    laps.lap("learn")
    plan_ings = norm_pantry(selected_ingredients, aliases, swaps)
    laps.lap("pick_inputs")
    picked = pick_meals(
        recipes,
        taste,
        pantry,
        favorites,
        aliases,
        want,
        swaps,
        ignored,
        to_try,
        cooked,
        plan_ings=plan_ings,
        laps=laps,
    )
    if len(picked) < want:
        # Not enough meals keep every preference. Fill the rest from the backup tier: avoided,
        # hidden and downvoted meals and variants, still never breaking a diet or allergy.
        # Every priority meal not picked by now was rejected as downvoted.
        chosen = {row["id"] for row in picked}
        fallback = backup + [recipe for recipe in recipes if recipe["id"] not in chosen]
        extra = pick_meals(
            fallback,
            taste,
            pantry,
            favorites,
            aliases,
            want - len(picked),
            swaps,
            ignored,
            to_try,
            cooked,
            plan_ings=norm_pantry(selected_ingredients + [i for row in picked for i in row["ingredients"]], aliases, swaps),
            laps=laps,
            allow_downvoted=True,
        )
        for row in extra:
            row["reasons"] = [BACKUP_REASON, *row.get("reasons", [])]
        picked += extra
        laps.counts["backup_picked"] = len(extra)
    reasons = {str(row["id"]): row.get("reasons", []) for row in picked}
    note = suggestion_note(len(picked), taste)
    summary = reasons_summary([row.get("reasons", []) for row in picked])
    if summary:
        note = f"{note} {summary[0].upper()}{summary[1:]}."
    laps.lap("notes")
    laps.counts["picked"] = len(picked)
    laps.publish("suggest")
    _log.info("suggest hh=%d %s", household_id, laps.fmt())
    _SUGGEST_CONTEXT.set({
        "at": now(),
        "filters": {"diets": diets, "allergens": allergens, "avoids": avoids, "max_minutes": max_minutes},
        "pantry": sorted(pantry),
        "never_shop": sorted(ignored),
        "kept_recipe_ids": sorted(kept),
        "pool": {"priority": len(recipes), "backup": len(backup), "built_now": not pool_hit},
        "taste": {
            "liked": len(taste.liked), "passed": len(taste.passed), "favorites": len(favorites),
            "to_try": len(to_try), "cooked": len(cooked),
            "thumbs_up": sum(1 for up in rated.values() if up > 0), "thumbs_down": sum(1 for up in rated.values() if up < 0),
        },
        "steps_ms": {name: round(ms, 1) for name, ms in laps.ms.items()},
        "counts": dict(laps.counts),
        # Ranked order, so a report can show where each picked meal stood.
        "ranked": [{"id": row["id"], "name": row.get("name"), "score": row.get("score"),
                    "reasons": row.get("reasons", []), "backup": BACKUP_REASON in (row.get("reasons") or [])}
                   for row in picked],
    })
    return picked, note, reasons


@functools.cache
def _ranking_code() -> str:
    """The ranking code and the catalog files it loads. A deploy that changes either stales every stamp."""
    from app.domain import categories, diet_filter, families, grocery, ingredients, neighbors, pool, suggest, taste_rank
    digest = hashlib.sha256()
    for part in (categories, diet_filter, families, grocery, ingredients, neighbors, pool, suggest, taste_rank,
                 _rank_inputs, _suggest_meals, _rank_proposal):
        digest.update(inspect.getsource(part).encode())
    for name in ("ingredient_families.json", "ingredient_space.json", "ingredient_space.bin"):
        digest.update((catalog_dir() / name).read_bytes())
    return digest.hexdigest()


def _suggestion_stamp(db: PgConnection, household_id: int, kept: set[int], current_ids: set[int], plan_id: int | None = None) -> str:
    """A hash of everything a proposal is ranked from. plan_id is the proposal itself, left out
    of history: it didn't exist when it was ranked, and swaps made on it shouldn't stale it."""
    inputs = _rank_inputs(db, household_id, kept)
    history = []
    for pid, h in inputs["history"]:
        signal = {"decision": h.get("decision"), "changes": [c.get("from") for c in h.get("changes") or []]}
        if signal["decision"]:
            signal["suggested"] = h.get("suggested_recipe_ids", [])
        if pid != plan_id and (signal["decision"] or signal["changes"]):
            history.append(signal)
    pool = inputs["pool"]
    payload = {
        "code": _ranking_code(), "skip": sorted(TASTE_SKIP), "filters": inputs["filters"], "pool": pool.digest,
        "kept": sorted(kept), "selected": inputs["selected_ingredients"], "current": sorted(current_ids),
        "aliases": inputs["aliases"], "swaps": inputs["swaps"], "pantry": sorted(inputs["pantry"]),
        "ignored": sorted(inputs["ignored"]), "snapshots": inputs["snapshots"],
        "rated": sorted(inputs["rated"].items()), "history": history, "favorites": sorted(inputs["favorites"]),
        "to_try": sorted(inputs["to_try"]), "cooked": sorted(inputs["cooked"]),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _rank_proposal(db: PgConnection, household_id: int, count: int, kept: set[int], current_ids: set[int],
                   plan_id: int | None = None) -> tuple[list[dict], str, dict, dict | None, str]:
    """count fresh meals next to the kept ones: picked, note, reasons, context and stamp.

    plan_id is the proposal being re-ranked, if any. The stamp is taken first, so a change
    that lands mid-rank stales it rather than hiding.
    """
    stamp = _suggestion_stamp(db, household_id, kept, current_ids, plan_id)
    _SUGGEST_CONTEXT.set(None)
    # The ranker is greedy, so its first picks don't depend on how many it ranks. Rank
    # enough to fill the plan even if every meal already this week goes to the back.
    candidates, note, reasons = _suggest_meals(db, household_id, count + len(current_ids - kept), kept)
    available = [m for m in candidates if m["id"] not in kept]
    # Prefer a fresh proposal; retain eligible familiar meals if the catalog is small.
    available.sort(key=lambda meal: meal["id"] in current_ids)
    picked = available[:count]
    # Keep reasons and the note to the meals actually picked.
    reasons = {str(m["id"]): m.get("reasons", []) for m in picked}
    note = _proposal_note(reasons, [m["id"] for m in picked])
    return picked, note, reasons, _plan_context(_SUGGEST_CONTEXT.get(), picked), stamp


def _proposal_note(reasons: dict, recipe_ids: list[int]) -> str:
    """Why these meals, for the suggested meals currently on a proposal."""
    count = len(recipe_ids)
    note = f"Suggested {count} {'meal' if count == 1 else 'meals'}."
    summary = reasons_summary([reasons.get(str(rid), []) for rid in recipe_ids])
    return f"{note} {summary}." if summary else note


def _plan_context(context: dict | None, picked: list[dict]) -> dict | None:
    """The suggestion context, keeping only the meals that made the plan, with their rank."""
    if not context:
        return None
    ranks = {row["id"]: i for i, row in enumerate(context["ranked"], start=1)}
    meals = {row["id"]: row for row in context["ranked"]}
    return {
        **{k: v for k, v in context.items() if k != "ranked"},
        "ranked_out_of": len(context["ranked"]),
        "meals": [{**meals.get(m["id"], {"id": m["id"]}), "rank": ranks.get(m["id"])} for m in picked],
    }


@router.post("/plans")
def create_plan(body: PlanCreate, db: PgConnection = DbDep, household_id: int = HhDep):
    source_id = _ensure_plan(db, household_id) if body.keep_current else body.source_plan_id
    source = _plan_out(db, source_id, household_id) if source_id else None
    picked: list[dict] = []
    note = None
    reasons = None
    context = None
    stamp = None
    if body.meal_count and not body.draft and (not source or body.keep_current):
        kept = {s["recipe_id"] for s in source["slots"]} if source else set()
        current = _plan_out(db, _ensure_plan(db, household_id), household_id)
        current_ids = {slot["recipe_id"] for slot in current["slots"]}
        picked, note, reasons, context, stamp = _rank_proposal(db, household_id, body.meal_count, kept, current_ids)
        if not picked:
            raise HTTPException(409, "No matching suggestions. Loosen Settings → Filters or choose meals yourself.")
    with transaction(db):
        db.execute("SELECT id FROM households WHERE id = ? FOR UPDATE", (household_id,)).fetchone()
        if not body.draft and not picked:
            db.execute("UPDATE plans SET status = 'history' WHERE household_id = ? AND status = 'active'", (household_id,))
        cur = db.execute("INSERT INTO plans (household_id, start_date, days, title, created_at, status) VALUES (?, ?, ?, ?, ?, ?)",
                         (household_id, (body.start_date or (date.fromisoformat(source["start_date"]) if body.keep_current and source else date.today())).isoformat(), source["days"] if source else 7,
                          body.title, now(), "draft" if body.draft else ("suggested" if picked else "active")))
        pid = int(cur.lastrowid)
        if source:
            for slot in source["slots"]:
                db.execute("INSERT INTO plan_slots (plan_id, day_index, meal_type, recipe_id, servings, sort, cooked) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (pid, slot["day_index"], slot["meal_type"], slot["recipe_id"], slot["servings"], slot["sort"], int(slot["cooked"]) if body.keep_current else 0))
        if picked:
            for sort, meal in enumerate(picked, start=len(source["slots"]) if source else 0):
                servings = _default_slot_servings(db, household_id, meal["id"])
                db.execute(
                    "INSERT INTO plan_slots (plan_id, day_index, meal_type, recipe_id, servings, sort, cooked) VALUES (?, NULL, 'dinner', ?, ?, ?, 0)",
                    (pid, meal["id"], servings, sort),
                )
        if picked:
            db.execute("UPDATE plans SET suggestion_json = ? WHERE id = ?", (json.dumps({"suggestion_note": f"{note} Swap any meal or approve the plan when it feels right.", "suggestion_reasons": reasons, "original_recipe_ids": [m["id"] for m in picked], "suggested_recipe_ids": [m["id"] for m in picked], "feedback": [], "changes": [], "context": context, "stamp": stamp, "ranked_with": sorted(kept)}), pid))
        else:
            _rebuild_grocery(db, pid, household_id)
    out = _plan_out(db, pid, household_id)
    return out


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, db: PgConnection = DbDep, household_id: int = HhDep):
    return _plan_out(db, plan_id, household_id)


@router.get("/grocery/places")
def get_places(db: PgConnection = DbDep, household_id: int = HhDep):
    items = {pantry_key(r["name"]): {"name": r["name"], "store": "", "aisle": aisle_for(r["name"])}
             for r in db.execute("SELECT name FROM pantry_items WHERE household_id = ?", (household_id,))}
    for r in db.execute("SELECT DISTINCT COALESCE(g.custom_text, i.canonical_name) AS name, g.store, g.aisle FROM grocery_lines g JOIN plans p ON p.id = g.plan_id LEFT JOIN ingredients i ON i.id = g.ingredient_id WHERE p.household_id = ?", (household_id,)):
        if r["name"]:
            items[pantry_key(r["name"])] = dict(r)
    for r in db.execute("SELECT name, store, aisle FROM grocery_places WHERE household_id = ?", (household_id,)):
        items[pantry_key(r["name"])] = dict(r)
    return {"items": sorted(items.values(), key=lambda r: r["name"])}


@router.put("/grocery/places")
def put_place(body: PlacementPut, db: PgConnection = DbDep, household_id: int = HhDep):
    name = pantry_key(body.name)
    with transaction(db):
        previous = db.execute("SELECT store, aisle FROM grocery_places WHERE household_id = ? AND name = ?", (household_id, name)).fetchone()
        store = body.store if body.store is not None else (previous["store"] if previous else "")
        aisle = body.aisle if body.aisle is not None else (previous["aisle"] if previous else aisle_for(name))
        db.execute("INSERT INTO grocery_places (household_id, name, store, aisle) VALUES (?, ?, ?, ?) ON CONFLICT(household_id, name) DO UPDATE SET store = excluded.store, aisle = excluded.aisle", (household_id, name, store, aisle))
        _rebuild_grocery_for_household(db, household_id)
    return {"ok": True}


@router.post("/plans/{plan_id}/decision/{decision}")
def decide_suggestion(plan_id: int, decision: str, db: PgConnection = DbDep, household_id: int = HhDep):
    if decision not in {"approve", "decline"}:
        raise HTTPException(400, "Unknown decision")
    with transaction(db):
        db.execute("SELECT id FROM households WHERE id = ? FOR UPDATE", (household_id,)).fetchone()
        plan = _plan_out(db, plan_id, household_id)
        if plan["status"] != "suggested":
            raise HTTPException(409, "This suggestion has already been reviewed")
        stored = db.execute("SELECT suggestion_json FROM plans WHERE id = ?", (plan_id,)).fetchone()
        meta = json.loads(stored["suggestion_json"])
        meta["decision"] = decision
        meta["suggestion_note"] = None
        meta["reviewed_at"] = now()
        meta["feedback"] += [{"recipe_id": str(s["recipe_id"]), "liked": decision == "approve"} for s in plan["slots"] if s["recipe_id"] in meta["suggested_recipe_ids"]]
        if decision == "approve":
            db.execute("UPDATE plans SET status = 'history' WHERE household_id = ? AND status = 'active'", (household_id,))
        db.execute("UPDATE plans SET status = ?, suggestion_json = ? WHERE id = ?", ("active" if decision == "approve" else "declined", json.dumps(meta), plan_id))
        if decision == "approve":
            _rebuild_grocery(db, plan_id, household_id)
    return _plan_out(db, plan_id, household_id)


@router.post("/plans/{plan_id}/swap/{slot_id}")
def swap_suggestion(plan_id: int, slot_id: int, body: SuggestionSwap | None = None, db: PgConnection = DbDep, household_id: int = HhDep):
    with transaction(db):
        db.execute("SELECT id FROM households WHERE id = ? FOR UPDATE", (household_id,)).fetchone()
        plan = _plan_out(db, plan_id, household_id)
        if plan["status"] != "suggested":
            raise HTTPException(409, "Review a suggested plan to swap meals")
        slot = next((s for s in plan["slots"] if s["id"] == slot_id), None)
        if not slot:
            raise HTTPException(404, "Meal not found")
        excluded = set(plan["original_recipe_ids"]) | {s["recipe_id"] for s in plan["slots"]}
        excluded |= {c["to"] for c in plan["changes"]}
        # A chosen meal is checked against the wide list; otherwise the next one past what's excluded.
        choosing = body and body.recipe_id is not None
        picked, _, _ = _suggest_meals(db, household_id, 400 if choosing else len(excluded) + 1)
        if choosing:
            current_ids = {s["recipe_id"] for s in plan["slots"]}
            meal = next((m for m in picked if m["id"] == body.recipe_id and m["id"] not in current_ids), None)
        else:
            meal = next((m for m in picked if m["id"] not in excluded), None)
        if not meal:
            raise HTTPException(409, "No more matching meals. Try loosening Settings → Filters.")
        stored = db.execute("SELECT suggestion_json FROM plans WHERE id = ?", (plan_id,)).fetchone()
        meta = json.loads(stored["suggestion_json"])
        if slot["recipe_id"] not in meta["suggested_recipe_ids"]:
            raise HTTPException(409, "This meal was selected by you")
        meta["suggested_recipe_ids"].remove(slot["recipe_id"])
        meta["suggested_recipe_ids"].append(meal["id"])
        meta["changes"].append({"from": slot["recipe_id"], "to": meal["id"], "at": now()})
        meta["suggestion_reasons"] = {**(meta["suggestion_reasons"] or {}), str(meal["id"]): meal.get("reasons", [])}
        meta["suggestion_note"] = (
            _proposal_note(meta["suggestion_reasons"], meta["suggested_recipe_ids"])
            + " Swap any meal or approve the plan when it feels right."
        )
        meta["feedback"].append({"recipe_id": str(slot["recipe_id"]), "liked": False})
        db.execute("UPDATE plans SET suggestion_json = ? WHERE id = ?", (json.dumps(meta), plan_id))
        db.execute("UPDATE plan_slots SET recipe_id = ?, servings = ? WHERE id = ?", (meal["id"], _default_slot_servings(db, household_id, meal["id"]), slot_id))
    return _plan_out(db, plan_id, household_id)


_REFRESH_LOCKS: dict[int, threading.Lock] = {}
_REFRESH_LOCKS_LOCK = threading.Lock()


def _refresh_lock(household_id: int) -> threading.Lock:
    with _REFRESH_LOCKS_LOCK:
        return _REFRESH_LOCKS.setdefault(household_id, threading.Lock())


def _fresh_suggestion(db: PgConnection, household_id: int) -> int | None:
    """The household's pending suggestion, re-ranked first if anything it was ranked from changed.

    A saved suggestion is never shown stale: filters, pantry, Taste Lab, thumbs, history, the
    recipes and the ranking code all go into its stamp. The lock makes a read that arrives
    during a background re-rank wait for it instead of ranking again.
    """
    with _refresh_lock(household_id):
        row = db.execute("SELECT id, suggestion_json FROM plans WHERE household_id = ? AND status = 'suggested' AND hidden = 0 ORDER BY id DESC LIMIT 1", (household_id,)).fetchone()
        if not row:
            return None
        plan_id, raw = int(row["id"]), row["suggestion_json"]
        meta = json.loads(raw or "{}")
        plan = _plan_out(db, plan_id, household_id)
        suggested = meta.get("suggested_recipe_ids") or []
        slot_ids = {s["recipe_id"] for s in plan["slots"]}
        current_ids = {s["recipe_id"] for s in _plan_out(db, _ensure_plan(db, household_id), household_id)["slots"]}
        ranked_with = set(meta.get("ranked_with", slot_ids - set(suggested))) & slot_ids
        if meta.get("stamp") and meta["stamp"] == _suggestion_stamp(db, household_id, ranked_with, current_ids, plan_id):
            return plan_id
        # Keep the household's own picks: meals from its week, and swaps it chose that still
        # keep its diets and allergies. Re-rank every other suggested meal.
        pool, _ = _household_pool(db, household_id, *_filter_prefs(db, household_id)[:3])
        swapped_in = {c["to"] for c in meta.get("changes") or []}
        kept = (slot_ids - set(suggested)) | {rid for rid in swapped_in & slot_ids if rid in pool.allowed}
        stale = [s for s in plan["slots"] if s["recipe_id"] not in kept]
        picked, _, reasons, context, stamp = _rank_proposal(db, household_id, len(stale), kept, current_ids, plan_id)
        with transaction(db):
            db.execute("SELECT id FROM households WHERE id = ? FOR UPDATE", (household_id,)).fetchone()
            now_row = db.execute("SELECT status, suggestion_json FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not now_row or now_row["status"] != "suggested" or now_row["suggestion_json"] != raw:
                return plan_id  # reviewed, swapped or resized mid-rank; that change wins
            for slot, meal in zip(stale, picked):
                db.execute("UPDATE plan_slots SET recipe_id = ?, servings = ? WHERE id = ?",
                           (meal["id"], _default_slot_servings(db, household_id, meal["id"]), slot["id"]))
            for slot in stale[len(picked):]:
                db.execute("DELETE FROM plan_slots WHERE id = ?", (slot["id"],))
            fresh = [m["id"] for m in picked]
            meta["suggested_recipe_ids"] = [rid for rid in suggested if rid in kept] + fresh
            meta["original_recipe_ids"] = list(dict.fromkeys([*(meta.get("original_recipe_ids") or []), *fresh]))
            meta["suggestion_reasons"] = {**{k: v for k, v in (meta.get("suggestion_reasons") or {}).items() if int(k) in kept}, **reasons}
            meta["suggestion_note"] = (
                _proposal_note(meta["suggestion_reasons"], meta["suggested_recipe_ids"])
                + " Swap any meal or approve the plan when it feels right."
            )
            meta.update(context=context, stamp=stamp, ranked_with=sorted(kept), refreshed_at=now())
            db.execute("UPDATE plans SET suggestion_json = ? WHERE id = ?", (json.dumps(meta), plan_id))
        _log.info("suggestion refreshed hh=%d plan=%d replaced=%d", household_id, plan_id, len(stale))
        return plan_id


# Re-ranks off the request path, so a household's next open finds its suggestion already fresh.
# Each write schedules one for its household; a later write pushes it back, so a run of Taste Lab
# swipes ranks once. One worker thread, so ranks never compete with each other for the CPU.
_REFRESH_DELAY = 2.0  # seconds after the last write
_REFRESH_DUE: dict[int, float] = {}
_REFRESH_WAKE = threading.Condition()
_REFRESH_WORKER: threading.Thread | None = None


def schedule_suggestion_refresh(household_id: int, delay: float = _REFRESH_DELAY) -> None:
    with _REFRESH_WAKE:
        _REFRESH_DUE[household_id] = time.monotonic() + delay
        _REFRESH_WAKE.notify()


def _refresh_now(household_id: int) -> None:
    db = connect()
    try:
        _fresh_suggestion(db, household_id)
    except Exception:
        _log.exception("suggestion refresh failed hh=%d", household_id)
    finally:
        db.close()


def _drain_refreshes() -> None:
    """Run every scheduled refresh now, due or not (tests, and nothing else)."""
    with _REFRESH_WAKE:
        due = list(_REFRESH_DUE)
        _REFRESH_DUE.clear()
    for household_id in due:
        _refresh_now(household_id)


def _refresh_loop() -> None:
    while True:
        with _REFRESH_WAKE:
            while not _REFRESH_DUE:
                _REFRESH_WAKE.wait()
            household_id, due = min(_REFRESH_DUE.items(), key=lambda item: item[1])
            wait = due - time.monotonic()
            if wait > 0:
                _REFRESH_WAKE.wait(wait)
                continue
            del _REFRESH_DUE[household_id]
        _refresh_now(household_id)


def start_suggestion_refresher(db: PgConnection) -> None:
    """Start the worker and queue every pending suggestion: a relaunch emptied the pools, and
    a deploy may have changed the ranking code, so check each before its household opens it."""
    global _REFRESH_WORKER
    with _REFRESH_WAKE:
        if _REFRESH_WORKER is not None:
            return
        _REFRESH_WORKER = threading.Thread(target=_refresh_loop, name="suggestion-refresh", daemon=True)
        _REFRESH_WORKER.start()
    for row in db.execute("SELECT DISTINCT household_id FROM plans WHERE status = 'suggested' AND hidden = 0"):
        schedule_suggestion_refresh(int(row["household_id"]), 0)


@router.get("/suggestions/current")
def pending_suggestion(db: PgConnection = DbDep, household_id: int = HhDep):
    plan_id = _fresh_suggestion(db, household_id)
    return {"plan": _plan_out(db, plan_id, household_id) if plan_id else None}


@router.get("/suggestions/recipes")
def recipe_suggestions(db: PgConnection = DbDep, household_id: int = HhDep):
    meals, _, _ = _suggest_meals(db, household_id, 12)
    return {"recipe_ids": [m["id"] for m in meals]}


@router.post("/plans/{plan_id}/resize")
def resize_suggestion(plan_id: int, body: SuggestionResize, db: PgConnection = DbDep, household_id: int = HhDep):
    with transaction(db):
        db.execute("SELECT id FROM households WHERE id = ? FOR UPDATE", (household_id,)).fetchone()
        plan = _plan_out(db, plan_id, household_id)
        if plan["status"] != "suggested":
            raise HTTPException(409, "This plan has already been reviewed")
        suggested = list(plan["suggested_recipe_ids"])
        kept_count = sum(s["recipe_id"] not in suggested for s in plan["slots"])
        if body.meal_count < kept_count:
            raise HTTPException(409, "Keep enough room for your selected meals")
        delta = body.meal_count - len(plan["slots"])
        if delta > 0:
            excluded = {s["recipe_id"] for s in plan["slots"]} | set(plan["original_recipe_ids"])
            excluded |= {c["to"] for c in plan["changes"]}
            picked, _, _ = _suggest_meals(db, household_id, len(excluded) + delta)
            added = [m for m in picked if m["id"] not in excluded][:delta]
            if len(added) < delta:
                raise HTTPException(409, "Not enough matching meals. Adjust filters or choose meals yourself.")
            for index, meal in enumerate(added):
                db.execute("INSERT INTO plan_slots (plan_id, recipe_id, servings, sort, meal_type) VALUES (?, ?, ?, ?, 'dinner')",
                    (plan_id, meal["id"], _default_slot_servings(db, household_id, meal["id"]), len(plan["slots"]) + index))
                suggested.append(meal["id"])
        elif delta < 0:
            removable = [s for s in reversed(plan["slots"]) if s["recipe_id"] in suggested][:-delta]
            for slot in removable:
                db.execute("DELETE FROM plan_slots WHERE id = ?", (slot["id"],))
                suggested.remove(slot["recipe_id"])
        row = db.execute("SELECT suggestion_json FROM plans WHERE id = ?", (plan_id,)).fetchone()
        meta = json.loads(row["suggestion_json"])
        meta["suggested_recipe_ids"] = suggested
        meta.setdefault("count_changes", []).append({"from": len(plan["slots"]), "to": body.meal_count, "at": now()})
        reasons = meta.setdefault("suggestion_reasons", {})
        if delta > 0:
            reasons.update({str(meal["id"]): meal.get("reasons", []) for meal in added})
        meta["suggestion_note"] = _proposal_note(reasons, suggested)
        db.execute("UPDATE plans SET suggestion_json = ? WHERE id = ?", (json.dumps(meta), plan_id))
    return _plan_out(db, plan_id, household_id)


@router.get("/suggestions/capabilities")
def suggestion_capabilities(household_id: int = HhDep):
    return {"version": 2, "review": True, "resize": True, "swap": True}


@router.delete("/plans/{plan_id}")
def delete_saved_plan(plan_id: int, db: PgConnection = DbDep, household_id: int = HhDep):
    with transaction(db):
        db.execute("SELECT id FROM households WHERE id = ? FOR UPDATE", (household_id,)).fetchone()
        plan = _plan_out(db, plan_id, household_id)
        if plan["status"] == "active":
            raise HTTPException(409, "Your current plan cannot be deleted. Start another plan first.")
        # Remove from the library while retaining preference evidence for recommendations.
        db.execute("UPDATE plans SET hidden = 1 WHERE id = ?", (plan_id,))
    return {"ok": True}


@router.get("/plans/{plan_id}/swap-options/{slot_id}")
def suggestion_swap_options(plan_id: int, slot_id: int, q: str = "", db: PgConnection = DbDep, household_id: int = HhDep):
    plan = _plan_out(db, plan_id, household_id)
    if plan["status"] != "suggested":
        raise HTTPException(409, "This plan has already been reviewed")
    slot = next((s for s in plan["slots"] if s["id"] == slot_id), None)
    if not slot or slot["recipe_id"] not in plan["suggested_recipe_ids"]:
        raise HTTPException(404, "Suggested meal not found")
    picked, _, _ = _suggest_meals(db, household_id, 400)
    held = {s["recipe_id"] for s in plan["slots"]}
    words = q.casefold().split()
    options = []
    for meal in picked:
        blob = " ".join([meal["name"], *meal.get("ingredients", [])]).casefold()
        if meal["id"] in held or not all(word in blob for word in words):
            continue
        row = db.execute("SELECT photo_path, parent_recipe_id FROM recipes WHERE id = ?", (meal["id"],)).fetchone()
        options.append({"id": meal["id"], "name": meal["name"], "cooking_minutes": meal.get("cooking_minutes"),
            "photo_path": usable_photo(row["photo_path"], meal["id"], row["parent_recipe_id"]) if row else None})
        if len(options) == 50:
            break
    return {"recipes": options}
