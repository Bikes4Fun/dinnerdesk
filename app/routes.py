"""HTTP routes. Household comes from deps, never from the client."""

from __future__ import annotations

import json
from app.db.database import PgConnection
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.db.catalog import public_recipe_sql
from app.db.seed import pantry_catalog
from app.db.database import ROOT, now, transaction
from app.assets import catalog_dir
from app.deps import AdminDep, DbDep, HhDep
from fractions import Fraction

from app.domain.ingredient_photos import photo_path as ingredient_photo_path
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
from app.domain.prep import prep_from_slots
from app.domain.diet_filter import allowed as diet_allowed, blocks_for, merge_filters
from app.domain.search import hard_tokens, search_grocery_names, tokens as search_tokens
from app.domain.suggest import norm_pantry
from app.domain.taste_rank import learn, pick_meals, promote, reasons_summary, suggestion_note, suggestion_penalties
from app.taste_lab import SKIP as TASTE_SKIP
from app.taste_lab import archive_id, household_filters, snapshots_for_accounts
from app.models import (
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
    RecipePatch,
    SlotPatch,
    SlotsPut,
    SubmissionCreate,
)

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
        "photo_path": usable_photo(row["photo_path"], row["id"], row["parent_recipe_id"]),
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


def _recipe_out(db: PgConnection, row, household_id: int) -> dict:
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
        "photo_path": usable_photo(row["photo_path"], row["id"], row["parent_recipe_id"]),
        "photo_ai": photo_is_ai(usable_photo(row["photo_path"], row["id"], row["parent_recipe_id"])),
        "photo_shared": photo_is_borrowed(
            usable_photo(row["photo_path"], row["id"], row["parent_recipe_id"]),
            archive_id_of(row["source_url"], row["slug"]),
        ),
        "source_url": row["source_url"],
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
        "dev_notes": row["dev_notes"] if "dev_notes" in row.keys() else "",
    }
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


def _diet_filtered(db: PgConnection, household_id: int, rows: list, groups: list[list[str]]) -> list:
    """Rows that pass the kitchen's diet/avoid filters. Two queries, not one per recipe.

    Uses this kitchen's edited name and ingredients when it has edited a recipe.
    Recipes this kitchen wrote itself always show.
    """
    ings: dict[int, list[str]] = {}
    for r in db.execute(
        """SELECT ri.recipe_id, i.canonical_name FROM recipe_ingredients ri
           JOIN ingredients i ON i.id = ri.ingredient_id
           JOIN recipes rc ON rc.id = ri.recipe_id
           WHERE rc.household_id IS NULL OR rc.household_id = ?""",
        (household_id,),
    ):
        ings.setdefault(int(r["recipe_id"]), []).append(r["canonical_name"])
    edits = {
        int(e["recipe_id"]): e
        for e in db.execute(
            "SELECT recipe_id, name, ingredients_json FROM household_recipe_edits WHERE household_id = ?",
            (household_id,),
        )
    }
    out = []
    for row in rows:
        rid = int(row["id"])
        if row["household_id"] == household_id:
            out.append(row)
            continue
        name, names = row["name"], ings.get(rid, [])
        edit = edits.get(rid)
        if edit:
            name = edit["name"] or name
            edited = [i.get("name") or "" for i in json.loads(edit["ingredients_json"] or "[]")]
            if edited:
                names = edited
        if diet_allowed(name, names, groups):
            out.append(row)
    return out


@router.get("/recipes")
def list_recipes(
    db: PgConnection = DbDep,
    household_id: int = HhDep,
    q: str = "",
    tag: str = "",
    hidden_only: bool = Query(default=False, alias="hidden"),
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
    else:
        sql += """ AND r.id NOT IN (
                 SELECT recipe_id FROM household_hidden_recipes WHERE household_id = ?
               )"""
    args.append(household_id)
    if q.strip():
        needed = hard_tokens(q) or search_tokens(q)
        for tok in needed:
            sql += " AND COALESCE(NULLIF(e.name, ''), r.name) ILIKE ?"
            args.append(f"%{tok}%")
    if tag.strip():
        sql += " AND t.tag = ?"
        args.append(tag.strip())
    diets, avoids, _ = _filter_prefs(db, household_id)
    groups = [] if hidden_only else blocks_for(diets, avoids)
    if groups:
        # Diet and avoid filters need ingredients, so filter before paging.
        sql += " ORDER BY r.name"
        candidates = db.execute(sql, args).fetchall()
        rows = _diet_filtered(db, household_id, candidates, groups)[offset:offset + limit]
    else:
        sql += " ORDER BY r.name LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        rows = db.execute(sql, args).fetchall()
    favs = _favorite_ids(db, household_id)
    later = _try_ids(db, household_id)
    hidden_ids = _hidden_recipe_ids(db, household_id)
    return {
        "recipes": [
            _recipe_card(db, r, household_id, r["id"] in favs, r["id"] in later, hidden_ids)
            for r in rows
        ]
    }


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


@router.post("/recipes")
def create_recipe(
    body: RecipeCreate,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    ts = now()
    with transaction(db):
        cur = db.execute(
            """INSERT INTO recipes (
                household_id, slug, name, servings, cooking_minutes,
                instructions_json, cookware_json, source_url, provenance_json,
                photo_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', '', ?, ?)""",
            (
                household_id,
                pantry_key(body.name).replace(" ", "-")[:80],
                body.name.strip(),
                body.servings,
                body.cooking_minutes,
                json.dumps(body.instructions),
                json.dumps(body.cookware),
                (body.source_url or "").strip()[:2000],
                ts,
                ts,
            ),
        )
        rid = int(cur.lastrowid)
        for i, ing in enumerate(body.ingredients):
            name = ing.get("name") if isinstance(ing, dict) else str(ing)
            qty = ing.get("quantity", "") if isinstance(ing, dict) else ""
            iid = _get_or_create_ingredient(db, name)
            db.execute(
                """INSERT INTO recipe_ingredients
                   (recipe_id, ingredient_id, quantity, unit, note, sort)
                   VALUES (?, ?, ?, '', '', ?)""",
                (rid, iid, qty or "", i),
            )
        for tag in body.tags:
            db.execute(
                "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?, ?)",
                (rid, tag[:40]),
            )
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (rid,)).fetchone()
    return _recipe_out(db, row, household_id)


@router.get("/recipes/{recipe_id}")
def get_recipe(
    recipe_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    return _recipe_out(db, row, household_id)


@router.put("/recipes/{recipe_id}/favorite")
def put_favorite(
    recipe_id: int,
    body: FavoritePut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
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
    return _recipe_out(db, row, household_id)


@router.put("/recipes/{recipe_id}/hidden")
def put_hidden(
    recipe_id: int,
    body: FavoritePut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
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
    return _recipe_out(db, row, household_id)


@router.delete("/recipes/{recipe_id}/edit")
def revert_recipe_edit(
    recipe_id: int,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
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
    return _recipe_out(db, row, household_id)


@router.put("/recipes/{recipe_id}/try")
def put_try_later(
    recipe_id: int,
    body: FavoritePut,
    db: PgConnection = DbDep,
    household_id: int = HhDep,
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
    return _recipe_out(db, row, household_id)


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
    return _recipe_out(db, row, household_id)


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
):
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row or not _recipe_visible(row, household_id):
        raise HTTPException(404, {"error": "not_found", "detail": "recipe"})
    with transaction(db):
        catalog = row["household_id"] is None
        if catalog and not body.as_copy:
            base = _recipe_out(db, row, household_id)
            _upsert_recipe_edit(db, household_id, recipe_id, body, base)
            _rebuild_grocery_for_household(db, household_id)
            row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
            return _recipe_out(db, row, household_id)
        copied = catalog and body.as_copy
        target = recipe_id
        if copied:
            target = _copy_recipe(db, row, household_id)
            row = db.execute("SELECT * FROM recipes WHERE id = ?", (target,)).fetchone()
        fields = []
        args = []
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
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (target,)).fetchone()
    return _recipe_out(db, row, household_id)


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
    hits, _ = search_grocery_names(sorted(names), q, limit=len(names) or 1)
    # Every query word must match; plural queries also find singular ingredient names.
    def matches(name):
        hay = search_tokens(name)
        return all(any(part.startswith(word) or part.startswith(word[:-1] if len(word) > 3 and word.endswith("s") else word) for part in hay) for word in words)
    return {"items": [{"name": name} for name in hits if matches(name)][:40]}


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


def _refresh_prep(db: PgConnection, plan_id: int, household_id: int) -> None:
    """Synchronize derived prep with current household recipe edits, preserving task IDs."""
    slots = []
    for slot in db.execute("SELECT recipe_id, servings FROM plan_slots WHERE plan_id = ? ORDER BY sort, id", (plan_id,)):
        row = db.execute("SELECT * FROM recipes WHERE id = ?", (slot["recipe_id"],)).fetchone()
        recipe = _recipe_out(db, row, household_id)
        factor = Fraction(slot["servings"], recipe["servings"])
        slots.append({"recipe_id": recipe["id"], "recipe_name": recipe["name"],
                      "instructions": recipe["instructions"],
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
        details = json.dumps({"meals": task["meals"], "quantities": task["quantities"], "auto": task["auto"]})
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
        (int(r["recipe_id"]), r["step_key"]): (int(r["rating"]), r["reason"] or "")
        for r in db.execute(
            "SELECT recipe_id, step_key, rating, reason FROM prep_step_feedback WHERE household_id = ?",
            (household_id,),
        )
    }
    tasks = []
    for r in db.execute(
        "SELECT * FROM prep_tasks WHERE plan_id = ? ORDER BY sort, id",
        (plan_id,),
    ):
        details = json.loads(r["details_json"])
        votes = []
        for meal in details.get("meals") or []:
            for step in meal.get("steps") or []:
                rating, reason = feedback.get((int(meal["id"]), step["key"]), (0, ""))
                step["rating"] = rating
                step["done"] = bool(r["done"]) or f"{meal['id']}:{step['key']}" in json.loads(r["completed_steps_json"])
                votes.append((rating, reason))
        # The item's own 👍/👎: what every step in it says, or nothing when they disagree.
        rating = votes[0][0] if votes and all(v[0] == votes[0][0] for v in votes) else 0
        reason = next((why for value, why in votes if value == rating and why), "") if rating < 0 else ""
        tasks.append({"id": r["id"], "title": r["title"], "notes": r["notes"], "done": bool(r["done"]),
                      "rating": rating, "reason": reason, "section": "other", "item": r["title"],
                      "action": "", **details})
    return {"tasks": tasks}


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
                     rating = excluded.rating, updated_at = excluded.updated_at""",
                (household_id, body.recipe_id, body.key, body.text, body.category,
                 1 if body.auto else 0, body.rating, now()),
            )
        else:
            db.execute(
                "DELETE FROM prep_step_feedback WHERE household_id = ? AND recipe_id = ? AND step_key = ?",
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
        for meal in details.get("meals") or []:
            for step in meal.get("steps") or []:
                if body.rating:
                    db.execute(
                        """INSERT INTO prep_step_feedback
                           (household_id, recipe_id, step_key, step_text, category, auto, rating, reason, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(household_id, recipe_id, step_key) DO UPDATE SET
                             step_text = excluded.step_text, category = excluded.category,
                             auto = excluded.auto, rating = excluded.rating, reason = excluded.reason,
                             updated_at = excluded.updated_at""",
                        (household_id, int(meal["id"]), step["key"], step.get("text") or "", row["title"],
                         1 if step.get("auto", True) else 0, body.rating, reason, now()),
                    )
                else:
                    db.execute(
                        "DELETE FROM prep_step_feedback WHERE household_id = ? AND recipe_id = ? AND step_key = ?",
                        (household_id, int(meal["id"]), step["key"]),
                    )
    return {"ok": True, "rating": body.rating, "reason": reason}


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


def _filter_prefs(db: PgConnection, household_id: int) -> tuple[list, list, int | None]:
    """Diets, everything to keep out (allergies and avoids), and max cook time."""
    filters = household_filters(db, household_id)
    time = filters.get("time")
    max_minutes = int(time) if str(time or "").isdigit() else None
    return filters["diets"], [*filters["allergens"], *filters["avoids"]], max_minutes


def _candidate_meals(db: PgConnection, household_id: int) -> list[dict]:
    public_sql, public_args = public_recipe_sql("r")
    rows = db.execute(
        f"""SELECT r.id, r.name, r.slug, r.source_url,
                   COALESCE(NULLIF(e.name, ''), r.name) AS display_name,
                   COALESCE(e.cooking_minutes, r.cooking_minutes) AS minutes
            FROM recipes r
            LEFT JOIN household_recipe_edits e
              ON e.recipe_id = r.id AND e.household_id = ?
            WHERE (r.household_id IS NULL OR r.household_id = ?)
              AND {public_sql}
              AND r.id NOT IN (
                SELECT recipe_id FROM household_hidden_recipes WHERE household_id = ?
              )""",
        (household_id, household_id, *public_args, household_id),
    ).fetchall()
    tags_by: dict[int, set[str]] = {}
    for tag in db.execute("SELECT recipe_id, tag FROM recipe_tags"):
        tags_by.setdefault(int(tag["recipe_id"]), set()).add(tag["tag"])
    ings_by: dict[int, list[str]] = {}
    for item in db.execute(
        """SELECT ri.recipe_id, i.canonical_name
           FROM recipe_ingredients ri
           JOIN ingredients i ON i.id = ri.ingredient_id
           ORDER BY ri.recipe_id, ri.sort"""
    ):
        ings_by.setdefault(int(item["recipe_id"]), []).append(item["canonical_name"])
    meals = []
    for row in rows:
        rid = int(row["id"])
        tags = tags_by.get(rid, set())
        if tags & TASTE_SKIP and "full_meal" not in tags and "main_dish" not in tags:
            continue
        ingredients = ings_by.get(rid) or []
        if not ingredients:
            continue
        key = archive_id(row)
        keys = [str(rid)]
        if key not in keys:
            keys.append(key)
        meals.append(
            {
                "id": rid,
                "keys": keys,
                "name": row["display_name"],
                "ingredients": ingredients,
                "tags": sorted(tags),
                "cooking_minutes": row["minutes"],
            }
        )
    return meals


def _suggest_meals(db: PgConnection, household_id: int, want: int) -> tuple[list[dict], str, dict]:
    recipes = _candidate_meals(db, household_id)
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
    diets, avoids, max_minutes = _filter_prefs(db, household_id)
    accounts = [
        str(r["id"])
        for r in db.execute("SELECT id FROM users WHERE household_id = ?", (household_id,))
    ]
    # Settings → Filters is the one filter system (Taste Lab edits it too), so the diet,
    # allergy and avoid lists inside old Taste Lab snapshots no longer apply here.
    snapshots = [
        {k: v for k, v in snap.items() if k != "profile"} for snap in snapshots_for_accounts(accounts)
    ]
    # Plan thumbs count like Taste Lab swipes: a 👎 drops the meal, a 👍 boosts it and similar meals.
    rated = _meal_ratings(db, household_id)
    if rated:
        snapshots.append({
            "account_id": f"household-{household_id}-ratings",
            "swipes": [{"recipe_id": str(rid), "liked": up > 0} for rid, up in rated.items()],
        })
    history = [json.loads(row["suggestion_json"] or "{}") for row in db.execute(
        "SELECT suggestion_json FROM plans WHERE household_id = ? ORDER BY id", (household_id,))]
    # Approvals are plan-level signals; refusals and swaps are graded evidence, not bans.
    snapshots.append({"account_id": f"household-{household_id}-suggestions", "plans": [
        {"verdict": "up", "recipe_ids": h.get("suggested_recipe_ids", [])}
        for h in history if h.get("decision") == "approve"]})
    taste = learn(
        snapshots,
        recipes,
        diets=diets,
        avoids=avoids,
        max_minutes=max_minutes,
        aliases=aliases,
        overrides=swaps,
        skip=ignored,
    )
    taste.suggestion_penalties = suggestion_penalties(history)
    promote(taste, recipes, {rid for rid, up in rated.items() if up > 0})
    picked = pick_meals(
        recipes,
        taste,
        pantry,
        _favorite_ids(db, household_id),
        aliases,
        want,
        swaps,
        ignored,
        _try_ids(db, household_id),
        {
            int(row["recipe_id"])
            for row in db.execute(
                """SELECT DISTINCT s.recipe_id FROM plan_slots s
                   JOIN plans p ON p.id = s.plan_id
                   WHERE p.household_id = ? AND s.cooked = 1""",
                (household_id,),
            )
        },
    )
    reasons = {str(row["id"]): row.get("reasons", []) for row in picked}
    note = suggestion_note(len(picked), taste)
    summary = reasons_summary([row.get("reasons", []) for row in picked])
    if summary:
        note = f"{note} {summary[0].upper()}{summary[1:]}."
    return picked, note, reasons


def _proposal_note(reasons: dict, recipe_ids: list[int]) -> str:
    """Why these meals, for the suggested meals currently on a proposal."""
    count = len(recipe_ids)
    note = f"Suggested {count} {'meal' if count == 1 else 'meals'}."
    summary = reasons_summary([reasons.get(str(rid), []) for rid in recipe_ids])
    return f"{note} {summary}." if summary else note


@router.post("/plans")
def create_plan(body: PlanCreate, db: PgConnection = DbDep, household_id: int = HhDep):
    source_id = _ensure_plan(db, household_id) if body.keep_current else body.source_plan_id
    source = _plan_out(db, source_id, household_id) if source_id else None
    picked: list[dict] = []
    note = None
    reasons = None
    if body.meal_count and not body.draft and (not source or body.keep_current):
        candidates, note, reasons = _suggest_meals(db, household_id, 400)
        kept = {s["recipe_id"] for s in source["slots"]} if source else set()
        available = [m for m in candidates if m["id"] not in kept]
        current = _plan_out(db, _ensure_plan(db, household_id), household_id)
        current_ids = {slot["recipe_id"] for slot in current["slots"]}
        # Prefer a fresh proposal; retain eligible familiar meals if the catalog is small.
        available.sort(key=lambda meal: meal["id"] in current_ids)
        picked = available[:body.meal_count]
        # Ranked from 400 candidates; keep reasons and the note to the meals actually picked.
        reasons = {str(m["id"]): m.get("reasons", []) for m in picked}
        note = _proposal_note(reasons, [m["id"] for m in picked])
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
            db.execute("UPDATE plans SET suggestion_json = ? WHERE id = ?", (json.dumps({"suggestion_note": f"{note} Swap any meal or approve the plan when it feels right.", "suggestion_reasons": reasons, "original_recipe_ids": [m["id"] for m in picked], "suggested_recipe_ids": [m["id"] for m in picked], "feedback": [], "changes": []}), pid))
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
        picked, _, _ = _suggest_meals(db, household_id, 400)
        if body and body.recipe_id is not None:
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


@router.get("/suggestions/current")
def pending_suggestion(db: PgConnection = DbDep, household_id: int = HhDep):
    row = db.execute("SELECT id FROM plans WHERE household_id = ? AND status = 'suggested' AND hidden = 0 ORDER BY id DESC LIMIT 1", (household_id,)).fetchone()
    return {"plan": _plan_out(db, row["id"], household_id) if row else None}


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
            picked, _, _ = _suggest_meals(db, household_id, 400)
            excluded = {s["recipe_id"] for s in plan["slots"]} | set(plan["original_recipe_ids"])
            excluded |= {c["to"] for c in plan["changes"]}
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
