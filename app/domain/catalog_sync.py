"""Keep the catalog files (the private dd_support repo) and the live database the same.

The catalog lives in three places: the dd_support repo, the copy of its `data/` and `food/`
folders on the server's volume (DINNERDESK_CATALOG_DIR and FOOD_DIR), and PostgreSQL. The repo's
`catalog_sync.py` script keeps them in step through the token-protected routes in
`app/catalog_sync_routes.py`:

1. pull   what only the server has: admin recipe edits, uploaded photos, deleted photos, and the
          files the admin tools write (SERVER_OWNED) come back into the repo's files.
2. push   files that differ from the repo go up to the server's volume.
3. import the files go into the database. A recipe an admin edited is matched against its file
          first: when they agree the "admin edited" flag is cleared, so later file edits flow in
          again; when they disagree the admin's version is kept and reported as a conflict.

This module has no database or web code, so the rules can be tested on their own.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

# Files the server's admin tools write. The server's copy wins; the repo never pushes them.
SERVER_OWNED_DATA = frozenset({
    "ingredient_normalization_answers.json",
    "recipes_needing_manual_review.json",
})
UPLOADED_PHOTO = re.compile(r"admin-upload-[0-9a-f]{32}\.jpg")
# What may be written through the sync: catalog data and recipe photos, nothing executable.
DATA_SUFFIXES = frozenset({".json", ".bin", ".md", ".txt", ".csv"})
PHOTO_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
MAX_FILE_BYTES = 50 * 1024 * 1024
LFS_POINTER = b"version https://git-lfs"

# Recipe fields an admin can edit, grouped the way the provenance flags group them.
CONTENT_FIELDS = ("name", "servings", "cooking_minutes", "instructions", "cookware", "ingredients")


class BadPath(ValueError):
    pass


def safe_rel(rel: str) -> tuple[str, str]:
    """('data' | 'food', path inside it) for a sync path like 'data/recipes/1606.json' or
    'food/x.jpg'. Raises BadPath for anything else: absolute paths, '..', hidden files, folders
    inside food/, or file types the catalog doesn't use."""
    text = str(rel or "").replace("\\", "/")
    p = PurePosixPath(text)
    parts = p.parts
    if not text or p.is_absolute() or len(parts) < 2 or parts[0] not in ("data", "food"):
        raise BadPath(rel)
    if any(part in ("", ".", "..") or part.startswith(".") for part in parts[1:]):
        raise BadPath(rel)
    root, inner = parts[0], "/".join(parts[1:])
    suffix = PurePosixPath(inner).suffix.lower()
    if root == "food" and (len(parts) != 2 or suffix not in PHOTO_SUFFIXES):
        raise BadPath(rel)
    if root == "data" and suffix not in DATA_SUFFIXES:
        raise BadPath(rel)
    return root, inner


def is_server_owned(rel: str) -> bool:
    root, inner = safe_rel(rel)
    if root == "data":
        return inner in SERVER_OWNED_DATA
    return bool(UPLOADED_PHOTO.fullmatch(inner))


def check_upload(rel: str, body: bytes, sha256: str) -> None:
    """Refuse an upload that isn't a real, complete catalog file."""
    safe_rel(rel)
    if is_server_owned(rel):
        raise BadPath(f"{rel} is written by the server's admin tools; the repo never replaces it")
    if len(body) > MAX_FILE_BYTES:
        raise BadPath(f"{rel} is over {MAX_FILE_BYTES // (1024 * 1024)} MB")
    if body.startswith(LFS_POINTER):
        raise BadPath(f"{rel} is a Git LFS pointer, not the file; run git lfs pull first")
    if hashlib.sha256(body).hexdigest() != (sha256 or "").lower():
        raise BadPath(f"{rel} arrived incomplete (checksum mismatch)")
    if rel.endswith(".json"):
        json.loads(body)  # a broken JSON file would stop the app from starting


def file_hashes(root: Path, cache: dict | None = None) -> dict[str, str]:
    """sha256 of every file under root that the sync handles, keyed by its path inside root.
    cache maps a path to (size, mtime, sha) so unchanged photos aren't read again."""
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        inner = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in inner.split("/")):
            continue
        stat = path.stat()
        key = str(path)
        hit = cache.get(key) if cache is not None else None
        if hit and hit[0] == stat.st_size and hit[1] == stat.st_mtime_ns:
            out[inner] = hit[2]
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if cache is not None:
            cache[key] = (stat.st_size, stat.st_mtime_ns, digest)
        out[inner] = digest
    return out


# ------------------------------------------------------------------ recipe content

def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def steps_from_db(instructions_json: str) -> list[dict]:
    """The database's steps ({text, ings, prep}) in the catalog file's format."""
    try:
        steps = json.loads(instructions_json or "[]")
    except json.JSONDecodeError:
        return []
    out = []
    for s in steps if isinstance(steps, list) else []:
        if isinstance(s, str):
            s = {"text": s}
        if not isinstance(s, dict):
            continue
        item = {
            "step": str(s.get("text") or s.get("step") or ""),
            "ingredients_for_step": str(s.get("ings") or s.get("ingredients_for_step") or ""),
        }
        if s.get("prep"):
            item["prep"] = True
        out.append(item)
    return out


def _comparable_steps(steps) -> list[tuple]:
    out = []
    for s in steps or []:
        if isinstance(s, str):
            out.append((_clean(s), "", False))
        elif isinstance(s, dict):
            out.append((
                _clean(s.get("step") or s.get("text")),
                _clean(s.get("ingredients_for_step") or s.get("ings")).replace(" ", ""),
                bool(s.get("prep")),
            ))
    return out


def _comparable_ingredients(ings) -> list[tuple]:
    out = []
    for ing in ings or []:
        if isinstance(ing, dict):
            out.append((_clean(ing.get("name")).lower(), _clean(ing.get("quantity")).lower()))
        else:
            out.append((_clean(ing).lower(), ""))
    return out


def _int_or_none(value):
    try:
        return int(str(value).split()[0])
    except (TypeError, ValueError, IndexError):
        return None


def content_differences(file_data: dict, db: dict) -> list[str]:
    """Which content fields differ between a recipe file and the database's version of it.
    db holds name, servings, cooking_minutes, instructions (file format), cookware and
    ingredients ([{name, quantity}] as the admin typed them). Whitespace and letter case don't
    count as differences."""
    diff = []
    if _clean(file_data.get("name")) != _clean(db.get("name")):
        diff.append("name")
    if _int_or_none(file_data.get("servings")) != _int_or_none(db.get("servings")):
        diff.append("servings")
    if _int_or_none(file_data.get("cooking_minutes")) != _int_or_none(db.get("cooking_minutes")):
        diff.append("cooking_minutes")
    if _comparable_steps(file_data.get("instructions")) != _comparable_steps(db.get("instructions")):
        diff.append("instructions")
    if [_clean(c).lower() for c in file_data.get("cookware") or []] != [
            _clean(c).lower() for c in db.get("cookware") or []]:
        diff.append("cookware")
    if db.get("ingredients") is not None and _comparable_ingredients(
            file_data.get("ingredients")) != _comparable_ingredients(db.get("ingredients")):
        diff.append("ingredients")
    return diff


def tags_match(file_tags, db_tags, skip: set[str]) -> bool:
    keep = lambda tags: sorted({_clean(t) for t in tags or [] if _clean(t) and _clean(t) not in skip})
    return keep(file_tags) == keep(db_tags)


def same_photo(a: str, b: str) -> bool:
    return PurePosixPath(str(a or "")).name == PurePosixPath(str(b or "")).name


# ------------------------------------------------------------------ pulling into files

def merge_recipe_file(file_data: dict, server: dict, skip_tags: set[str]) -> tuple[dict, list[str]]:
    """The recipe file with the server's admin edits written in, and what changed.
    server is one recipe from GET /api/catalog-sync/state. Only the parts an admin edited
    (its flags) are taken; every other field in the file is kept exactly as it was."""
    out = dict(file_data)
    changed: list[str] = []
    flags = server.get("admin_edited") or {}
    if flags.get("content"):
        db = server.get("content") or {}
        for field in content_differences(file_data, db):
            value = db.get(field)
            if field == "ingredients" and value is None:
                continue
            out[field] = value
            changed.append(field)
    if flags.get("tags") and not tags_match(file_data.get("tags"), server.get("tags"), skip_tags):
        kept = [t for t in file_data.get("tags") or [] if t in skip_tags]
        out["tags"] = kept + [t for t in server.get("tags") or [] if t not in kept]
        changed.append("tags")
    if flags.get("photo") and not same_photo(file_data.get("photo_path"), server.get("photo_path")):
        out["photo_path"] = server.get("photo_path") or ""
        changed.append("photo_path")
    if flags.get("retired") and bool(file_data.get("retired")) != bool(server.get("retired")):
        out["retired"] = bool(server.get("retired"))  # removed from / brought back to the app
        changed.append("retired")
    notes = (server.get("dev_notes") or "").strip()
    if notes != (file_data.get("dev_notes") or "").strip() and (notes or "dev_notes" in file_data):
        out["dev_notes"] = notes
        changed.append("dev_notes")
    return out, changed


def merge_photo_list(photos: dict, recipes: list[dict]) -> tuple[dict, list[str]]:
    """recipe_photos.json with the server's photo changes written in: photos uploaded in the
    admin screen are listed for their recipe, and photos deleted there are taken off it."""
    use = list(photos.get("use") or [])
    listed = {(Path(str(e.get("file") if isinstance(e, dict) else e)).name,
               str(e.get("recipe_id")) if isinstance(e, dict) else "None") for e in use}
    notes: list[str] = []
    for r in recipes:
        archive = r.get("archive_id")
        if not archive:
            continue
        removed = {Path(p).name for p in r.get("removed_photos") or []}
        if removed:
            keep = []
            for e in use:
                name = Path(str(e.get("file") if isinstance(e, dict) else e)).name
                owner = str(e.get("recipe_id")) if isinstance(e, dict) else "None"
                if name in removed and owner == str(archive):
                    notes.append(f"removed {name} from recipe {archive}")
                    listed.discard((name, owner))
                    continue
                keep.append(e)
            use = keep
        for path in [r.get("photo_path") or ""] + list(r.get("gallery") or []):
            name = Path(path).name
            if UPLOADED_PHOTO.fullmatch(name) and (name, str(archive)) not in listed and name not in removed:
                use.append({"file": name, "recipe_id": int(archive) if str(archive).isdigit() else archive,
                            "credit": "Uploaded in the Dinnerdesk admin screen", "uploaded_in_app": True})
                listed.add((name, str(archive)))
                notes.append(f"listed upload {name} for recipe {archive}")
    out = dict(photos)
    out["use"] = use
    return out, notes
