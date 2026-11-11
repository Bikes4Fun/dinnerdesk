"""Routes the dd_support repo's catalog_sync.py uses to keep files and database the same.

Turned off unless CATALOG_SYNC_TOKEN is set; every request must send it as
`Authorization: Bearer <token>`. Rules and the overall flow are in app/domain/catalog_sync.py.

    GET  /api/catalog-sync/state          checksums of every catalog file and photo, plus each
                                          catalog recipe as the database has it now
    GET  /api/catalog-sync/file?path=...  one file, e.g. data/recipes/1606.json or food/x.jpg
    PUT  /api/catalog-sync/file?path=...&sha256=...   replace one file (not SERVER_OWNED ones)
    POST /api/catalog-sync/import         import the files into the database; returns a report
"""

from __future__ import annotations

import hmac
import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.assets import catalog_dir, food_dir
from app.db.database import PgConnection
from app.deps import get_db
from app.domain import recipe_photos
from app.domain.catalog_sync import RECIPE_WORKFLOW_FIELDS, BadPath, check_upload, file_hashes, safe_rel, steps_from_db
from app.domain.recipe_photos import archive_id_of, is_uploaded_photo

router = APIRouter(prefix="/catalog-sync")
_HASHES: dict = {}  # (size, mtime, sha) per file, so a sync doesn't re-read every photo


def require_sync_token(request: Request) -> None:
    token = (os.environ.get("CATALOG_SYNC_TOKEN") or "").strip()
    if len(token) < 32:
        # Off unless a long random token is configured; look like any unknown route.
        raise HTTPException(404, {"error": "not_found", "detail": "route"})
    sent = request.headers.get("authorization") or ""
    if not hmac.compare_digest(sent.encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, {"error": "unauthorized", "detail": "catalog sync token"})


SyncDep = Depends(require_sync_token)
DbDep = Depends(get_db)


def _root(name: str) -> Path:
    return catalog_dir() if name == "data" else food_dir()


def _target(rel: str) -> Path:
    try:
        root_name, inner = safe_rel(rel)
    except BadPath:
        raise HTTPException(400, {"error": "bad_path", "detail": rel})
    root = _root(root_name).resolve()
    path = (root / inner).resolve()
    if root not in path.parents:
        raise HTTPException(400, {"error": "bad_path", "detail": rel})
    return path


def _recipe_state(db: PgConnection, row, tags: dict, gallery: dict) -> dict:
    flags = json.loads(row["provenance_json"] or "{}")
    ingredients = flags.get("admin_ingredients")
    if ingredients is None and flags.get("admin_content_edited"):
        ingredients = [
            {"name": r["canonical_name"], "quantity": r["quantity"]}
            for r in db.execute(
                """SELECT i.canonical_name, ri.quantity FROM recipe_ingredients ri
                   JOIN ingredients i ON i.id = ri.ingredient_id WHERE ri.recipe_id = ? ORDER BY ri.sort""",
                (row["id"],),
            )
        ]
    return {
        "slug": row["slug"],
        "archive_id": archive_id_of(row["source_url"], row["slug"]),
        "admin_edited": {
            "content": flags.get("admin_content_edited") is True,
            "tags": flags.get("admin_tags_edited") is True,
            "photo": flags.get("admin_photo_edited") is True,
            "retired": flags.get("admin_retired_edited") is True,
            "reviewed": flags.get("admin_reviewed_edited") is True,
            **{field: flags.get(f"admin_{field}_edited") is True for field in RECIPE_WORKFLOW_FIELDS},
        },
        "retired": flags.get("retired") is True,
        "reviewed": flags.get("reviewed") is True,
        **{field: flags.get(field) is True for field in RECIPE_WORKFLOW_FIELDS},
        "content": {
            "name": row["name"],
            "servings": row["servings"],
            "cooking_minutes": row["cooking_minutes"],
            "instructions": steps_from_db(row["instructions_json"]),
            "cookware": json.loads(row["cookware_json"] or "[]"),
            "ingredients": ingredients,
        },
        "tags": tags.get(row["id"], []),
        "photo_path": row["photo_path"] or "",
        "gallery": gallery.get(row["id"], []),
        "removed_photos": flags.get("removed_photos") or [],
        "dev_notes": row["dev_notes"] or "",
    }


@router.get("/state")
def sync_state(_auth=SyncDep, db: PgConnection = DbDep):
    tags: dict[int, list[str]] = {}
    for r in db.execute(
        "SELECT t.recipe_id, t.tag FROM recipe_tags t JOIN recipes r ON r.id = t.recipe_id"
        " WHERE r.household_id IS NULL ORDER BY t.tag"
    ):
        tags.setdefault(r["recipe_id"], []).append(r["tag"])
    gallery: dict[int, list[str]] = {}
    for r in db.execute(
        "SELECT g.recipe_id, g.path FROM recipe_photo_gallery g JOIN recipes r ON r.id = g.recipe_id"
        " WHERE r.household_id IS NULL ORDER BY g.created_at, g.path"
    ):
        gallery.setdefault(r["recipe_id"], []).append(r["path"])
    recipes = [
        _recipe_state(db, row, tags, gallery)
        for row in db.execute("SELECT * FROM recipes WHERE household_id IS NULL ORDER BY slug")
    ]
    files = {f"data/{k}": v for k, v in file_hashes(catalog_dir(), _HASHES).items()}
    for name, digest in file_hashes(food_dir(), _HASHES).items():
        if "/" not in name:
            files[f"food/{name}"] = digest
    # Files a safe_rel() check would refuse (folders inside food/, odd types) are left out.
    files = {k: v for k, v in files.items() if _allowed(k)}
    return {"files": files, "recipes": recipes,
            "uploads_in_use": sorted({Path(p).name for r in recipes for p in [r["photo_path"], *r["gallery"]]
                                      if is_uploaded_photo(p)})}


def _allowed(rel: str) -> bool:
    try:
        safe_rel(rel)
        return True
    except BadPath:
        return False


@router.get("/file")
def sync_get_file(path: str, _auth=SyncDep):
    target = _target(path)
    if not target.is_file():
        raise HTTPException(404, {"error": "not_found", "detail": path})
    return FileResponse(target)


@router.put("/file")
async def sync_put_file(path: str, sha256: str, request: Request, _auth=SyncDep):
    target = _target(path)
    body = await request.body()
    try:
        check_upload(path, body, sha256)
    except (BadPath, ValueError) as e:
        raise HTTPException(400, {"error": "rejected", "detail": str(e)})
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
        os.replace(temp, target)
    except Exception:
        Path(temp).unlink(missing_ok=True)
        raise
    return {"ok": True, "path": path, "bytes": len(body)}


@router.post("/merge")
def sync_merge(body: dict = Body(...), _auth=SyncDep, db: PgConnection = DbDep):
    """The repo's own files with the database's admin edits written in. Body:
    {"recipes": {slug: recipe file}, "photos": recipe_photos.json}. Nothing is saved here;
    the repo script writes the answer into its files. The merge rules live with the app, so
    the script needs none of its own."""
    from app.db.catalog import SKIP_TAGS
    from app.domain.catalog_sync import merge_photo_list, merge_recipe_file

    local = body.get("recipes") or {}
    state = sync_state(None, db)["recipes"]
    recipes, changes = {}, {}
    for server in state:
        file_data = local.get(server["slug"])
        if not isinstance(file_data, dict):
            continue
        merged, changed = merge_recipe_file(file_data, server, SKIP_TAGS)
        if changed:
            recipes[server["slug"]] = merged
            changes[server["slug"]] = changed
    photos, notes = merge_photo_list(body.get("photos") or {"use": []}, state)
    return {"recipes": recipes, "changes": changes, "photos": photos, "photo_notes": notes}


@router.post("/import")
def sync_import(_auth=SyncDep, db: PgConnection = DbDep):
    from app.db.catalog import load_catalog
    from app.routes import _invalidate_all_pools

    recipe_photos.reload()  # recipe_photos.json may have just been replaced
    report: dict = {}
    inserted = load_catalog(db, report)
    _invalidate_all_pools()
    return {"inserted": inserted, **report}
