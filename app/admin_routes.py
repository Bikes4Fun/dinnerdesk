"""Admin review pages: plain HTML with the data filled in on the server. Admins only.

Each page in app/admin_pages has `/*DATA*/null` where its data goes. Notes and decisions made on
a page save in that browser, and the page's Export button downloads them.
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.assets import catalog_dir
from app.db.database import PgConnection
from app.deps import AdminDep, DbDep
from app.domain.recipe_photos import usable_photo

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
    raise HTTPException(404, {"error": "not_found", "detail": "admin page"})
