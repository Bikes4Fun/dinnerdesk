"""Which recipe photos may be shown.

Each entry in the configured catalog’s recipe_photos.json names a photo file. It is
shown only when it is listed there. The recipe row's photo_path picks the
file. Those recipe ids are archive ids, and the live database assigns its
own, so the list is not matched against the database id.
"""

from __future__ import annotations

from app.assets import catalog_dir, food_dir

import json
import hashlib
import re
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageOps, ImageChops, ImageStat


# Photos from recipe sites are never ours to show, even if one is listed by mistake.
THIRD_PARTY_MARKS = ("mealime", "allrecipes", "myplate")


def is_third_party_entry(item) -> bool:
    """True for an allowlist entry whose file or credit names a recipe site."""
    if isinstance(item, str):
        text = item
    else:
        text = " ".join(str(item.get(k) or "") for k in ("file", "credit", "owner", "source_url"))
    return any(mark in text.lower() for mark in THIRD_PARTY_MARKS)


def our_photo_entries(data: dict) -> list[tuple[str, int | None]]:
    """(file name, archive recipe id) for each allowlisted photo that is ours: Dinnerdesk's AI
    photos, the developer's own, and credited free-to-use photos. Recipe-site photos are left out."""
    out = []
    for item in data.get("use") or []:
        if is_third_party_entry(item):
            continue
        if isinstance(item, str):
            name, raw = Path(item).name, None
        else:
            name, raw = Path(str(item.get("file") or "")).name, item.get("recipe_id")
        if name:
            out.append((name, int(raw) if raw is not None and str(raw).isdigit() else None))
    return out


# Dinnerdesk's own AI photos count without being listed: any file in the photo folder named
# "<recipe id>_<name>_ai-generated.png" (or .jpg/.webp). Files with REVIEW or REDO in the name are
# still being judged and don't count yet. A "_PRIMARY_" photo is its recipe's first choice.
AUTO_PHOTO = re.compile(r"^([A-Za-z0-9-]+?)_.+_ai-generated\.(?:png|jpe?g|webp)$")
NOT_YET = re.compile(r"(?:^|_)(?:REVIEW|REDO)(?:_|$)")


def found_ai_photos(folder: Path) -> list[tuple[str, int | None]]:
    """(file name, archive recipe id) for each AI photo in `folder` that counts on its own,
    _PRIMARY_ photos first."""
    out = []
    try:
        names = sorted(p.name for p in folder.iterdir() if p.is_file())
    except OSError:
        return []
    for name in names:
        m = AUTO_PHOTO.match(name)
        if not m or NOT_YET.search(name) or is_third_party_entry(name):
            continue
        prefix = m.group(1)
        out.append((name, int(prefix) if prefix.isdigit() else None))
    return sorted(out, key=lambda item: "_PRIMARY_" not in item[0])


USE: dict[str, int | None] = {}
# Photos made with AI: entries marked `"ai_generated": true`, or files named
# `<id>_<name>_ai-generated.png`. Those recipes say so with a purple ★ tip (#33).
AI: set[str] = set()
AI_SUFFIX = "_ai-generated"
# Photos meant for a different recipe and borrowed by a similar one (#33): entries marked
# `"shared_photo": true` with no recipe of their own, or any entry whose `recipe_id` (an archive
# id) isn't the recipe showing it. Those recipes say so with a purple ★ tip.
SHARED: set[str] = set()
CREDITS: dict[str, dict[str, str]] = {}
# Photos the Dinnerdesk developer took of the recipe as cooked: entries marked
# `"developer_tested": true`. They show a gold ★ "Developer tested" badge on the photo.
TESTED: set[str] = set()
# Every listed photo, by the archive id of the recipe it was taken for, in file order. A catalog
# recipe's gallery shows them all, so one recipe can have several different photos.
GALLERY: dict[str, list[str]] = {}


def reload() -> None:
    """Read recipe_photos.json again, e.g. after the catalog sync replaced it. The tables are
    updated in place, so every module that imported them sees the new list."""
    data = json.loads((catalog_dir() / "recipe_photos.json").read_text())
    for table in (USE, AI, SHARED, CREDITS, TESTED, GALLERY):
        table.clear()
    for item in data.get("use") or []:
        if is_third_party_entry(item):
            continue
        if isinstance(item, str):
            name = Path(item).name
            recipe_id = None
            ai = False
        else:
            name = Path(str(item.get("file") or "")).name
            raw = item.get("recipe_id")
            recipe_id = int(raw) if raw is not None and str(raw).isdigit() else None
            ai = item.get("ai_generated") is True
            source = str(item.get("source_url") or "")
            CREDITS[name] = {
                "credit": str(item.get("credit") or item.get("owner") or ""),
                "source_url": source if source.startswith(("https://", "http://")) else "",
            }
            if item.get("shared_photo") is True:
                SHARED.add(name)
            if item.get("developer_tested") is True:
                TESTED.add(name)
            if name and recipe_id is not None:
                GALLERY.setdefault(str(recipe_id), []).append(name)
        if name:
            USE[name] = recipe_id
            if ai:
                AI.add(name)
    try:
        folder = food_dir()
    except RuntimeError:
        return
    for name, recipe_id in found_ai_photos(folder):
        AI.add(name)
        if name in USE:
            continue
        USE[name] = recipe_id
        if recipe_id is not None:
            listed = GALLERY.setdefault(str(recipe_id), [])
            listed.insert(0, name) if "_PRIMARY_" in name else listed.append(name)


reload()


def photo_name(path: str) -> str:
    return Path(str(path or "")).name


def is_uploaded_photo(path: str) -> bool:
    return bool(re.fullmatch(r"admin-upload-[0-9a-f]{32}\.jpg", photo_name(path)))


def photo_allowed(name: str) -> bool:
    filename = photo_name(name)
    uploaded = is_uploaded_photo(filename)
    return bool(filename) and (filename in USE or (uploaded and (food_dir() / filename).is_file()))


def usable_photo(path: str, *_recipe_ids: int | None) -> str:
    text = str(path or "").strip()
    filename = photo_name(text)
    if not filename or not photo_allowed(filename):
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


def photo_is_tested(path: str) -> bool:
    """True when the developer took this photo of the recipe as cooked."""
    return photo_name(path) in TESTED


@lru_cache(maxsize=256)
def _photo_pixels(path: str, size: int, modified: int) -> tuple:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGBA")
        preview = image.convert("RGB").resize((128, 128), Image.Resampling.LANCZOS).tobytes()
        return image.size, hashlib.sha256(image.tobytes()).hexdigest(), preview


def unique_gallery(photos: list[dict]) -> list[dict]:
    """Collapse image copies, including upload re-encoding, without changing source files."""
    unique: list[dict] = []
    for photo in photos:
        kept = next((item for item in unique if same_photo(item["path"], photo["path"])), None)
        if kept is None:
            unique.append(dict(photo))
            continue
        if (photo.get("tested") and not kept.get("tested")) or kept.get("credit") == "Photo source not recorded":
            if photo.get("credit"):
                kept.update({field: photo.get(field, "") for field in ("credit", "source_url")})
        for flag in ("primary", "tested", "ai", "shared"):
            kept[flag] = bool(kept.get(flag) or photo.get(flag))
    return unique


def _local_photo(path: str) -> tuple | None:
    if path.startswith(("https://", "http://")):
        return None
    try:
        file = food_dir() / photo_name(path)
        stat = file.stat()
        return _photo_pixels(str(file), stat.st_size, stat.st_mtime_ns)
    except (OSError, RuntimeError, ValueError, Image.DecompressionBombError):
        return None


def same_photo(first: str, second: str) -> bool:
    if photo_identity(first) == photo_identity(second):
        return True
    a, b = _local_photo(first), _local_photo(second)
    if a is None or b is None:
        return False
    (aw, ah), (bw, bh) = a[0], b[0]
    if abs(aw * bh - bw * ah) / max(aw * bh, bw * ah) > 0.001:
        return False
    # Allow tiny JPEG/resize differences, but retain crops, edits and distinct photos.
    difference = ImageChops.difference(Image.frombytes("RGB", (128, 128), a[2]),
                                       Image.frombytes("RGB", (128, 128), b[2]))
    return max(ImageStat.Stat(difference).mean) <= 1.5 and max(hi for _, hi in difference.getextrema()) <= 16


def photo_identity(path: str) -> tuple:
    if path.startswith(("https://", "http://")):
        return "url", path
    local = _local_photo(path)
    return ("pixels", *local[:2]) if local else ("file", photo_name(path))


def catalog_gallery(archive_id: str | None) -> list[str]:
    """Paths of the listed photos taken for the recipe with this archive id."""
    return [f"food/{name}" for name in GALLERY.get(str(archive_id), [])] if archive_id else []


def photo_credit(path: str) -> dict[str, str]:
    """Only cite recorded photo metadata, never assume the recipe's source owns its photo."""
    recorded = CREDITS.get(photo_name(path), {})
    owner = recorded.get("credit", "")
    if photo_is_ai(path):
        label = f"AI-generated photo · {owner}" if owner else "AI-generated photo"
    elif owner:
        label = f"Photo: {owner}"
    elif is_uploaded_photo(path):
        label = "Photo uploaded to Dinnerdesk"
    else:
        label = "Photo source not recorded"
    return {"credit": label, "source_url": recorded.get("source_url", "")}
