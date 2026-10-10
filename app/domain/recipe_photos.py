"""Which recipe photos may be shown.

Each entry in the configured catalog’s recipe_photos.json names a photo file. It is
shown only when it is listed there. The recipe row's photo_path picks the
file. Those recipe ids are archive ids, and the live database assigns its
own, so the list is not matched against the database id.
"""

from __future__ import annotations

from app.assets import catalog_dir

import json
import re
from pathlib import Path


_DATA = json.loads((catalog_dir() / "recipe_photos.json").read_text())
USE: dict[str, int | None] = {}
# Photos made with AI: entries marked `"ai_generated": true`, or files named
# `<id>_<name>_ai-generated.png`. Those recipes say so with a purple ★ tip (#33).
AI: set[str] = set()
AI_SUFFIX = "_ai-generated"
# Photos meant for a different recipe and borrowed by a similar one (#33): entries marked
# `"shared_photo": true` with no recipe of their own, or any entry whose `recipe_id` (an archive
# id) isn't the recipe showing it. Those recipes say so with a purple ★ tip.
SHARED: set[str] = set()
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
        if item.get("shared_photo") is True:
            SHARED.add(name)
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


_ARCHIVE_ID = re.compile(r"/(\d+)/?$")


def archive_id_of(source_url: str | None, slug: str | None) -> str | None:
    """The archive id a recipe's photo entry uses: the number at the end of its source URL,
    or an all-digit slug. None when the recipe has neither (a kitchen's own recipe)."""
    url = (source_url or "").split("?")[0].rstrip("/")
    m = _ARCHIVE_ID.search(url)
    if m:
        return m.group(1)
    slug = str(slug or "")
    return slug if slug.isdigit() else None


def photo_is_borrowed(path: str, archive_id: str | None) -> bool:
    """True when the photo shown was taken for another, similar recipe. An AI photo is
    labelled as AI instead, so this is False for those."""
    name = photo_name(path)
    if not name or name not in USE or photo_is_ai(path):
        return False
    owner = USE[name]
    if owner is not None:
        return archive_id is not None and str(owner) != str(archive_id)
    return name in SHARED
