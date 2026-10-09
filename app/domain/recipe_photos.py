"""Which recipe photos may be shown.

Each entry in the configured catalog’s recipe_photos.json names a photo file. It is
shown only when it is listed there. The recipe row's photo_path picks the
file. Those recipe ids are archive ids, and the live database assigns its
own, so the list is not matched against the database id.
"""

from __future__ import annotations

from app.assets import catalog_dir

import json
from pathlib import Path


_DATA = json.loads((catalog_dir() / "recipe_photos.json").read_text())
USE: dict[str, int | None] = {}
# Photos made with AI: entries marked `"ai_generated": true`, or files named
# `<id>_<name>_ai-generated.png`. Those recipes say so with a purple ★ tip (#33).
AI: set[str] = set()
AI_SUFFIX = "_ai-generated"
for item in _DATA.get("use") or []:
    if isinstance(item, str):
        name = Path(item).name
        recipe_id = None
        ai = False
    else:
        name = Path(str(item.get("file") or "")).name
        raw = item.get("recipe_id")
        recipe_id = int(raw) if raw is not None else None
        ai = item.get("ai_generated") is True
    if name:
        USE[name] = recipe_id
        if ai:
            AI.add(name)


def photo_name(path: str) -> str:
    return Path(str(path or "")).name


def photo_allowed(name: str) -> bool:
    return bool(photo_name(name)) and photo_name(name) in USE


def usable_photo(path: str, *_recipe_ids: int | None) -> str:
    text = str(path or "").strip()
    filename = photo_name(text)
    if not filename or filename not in USE:
        return ""
    return text


def photo_is_ai(path: str) -> bool:
    """True when the photo shown for a recipe was made with AI."""
    name = photo_name(path)
    return bool(name) and (name in AI or Path(name).stem.endswith(AI_SUFFIX))
