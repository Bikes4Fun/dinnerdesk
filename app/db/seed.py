"""Idempotent catalog seeds. Safe on every startup / pantry read."""

from __future__ import annotations

from app.assets import catalog_dir

import json
from app.db.database import PgConnection

from app.db.database import now
from app.domain.ingredients import aisle_for, pantry_key
from app.domain.pantry_catalog import catalog_entries


def seed_package_sizes(db: PgConnection) -> None:
    path = catalog_dir() / "package_sizes.json"
    try:
        packs = json.loads(path.read_text()).get("packs") or {}
    except json.JSONDecodeError:
        raise
    for raw_name, pack in packs.items():
        key = pantry_key(raw_name)
        size = str(pack.get("size") or "").strip()
        unit = str(pack.get("unit") or "").strip()
        if not key or not size:
            continue
        db.execute(
            "UPDATE ingredients SET package_size = ?, package_unit = ? WHERE canonical_name = ?",
            (size, unit, key),
        )


def _load_json_list(path, default):
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        raise


def _catalog_names() -> list[tuple[str, str]]:
    rows = _load_json_list(catalog_dir() / "pantry_catalog.json", [])
    extras = _load_json_list(catalog_dir() / "pantry_extras.json", [])
    return catalog_entries(rows if isinstance(rows, list) else [], extras if isinstance(extras, list) else [])


STAPLE_NEVER = frozenset({"salt", "black pepper", "pepper", "olive oil", "vegetable oil"})


def ensure_pantry_catalog(db: PgConnection, household_id: int) -> None:
    existing = {
        pantry_key(r["name"])
        for r in db.execute(
            "SELECT name FROM pantry_items WHERE household_id = ?",
            (household_id,),
        )
    }
    for name, zone in _catalog_names():
        if name in existing:
            continue
        row = db.execute("SELECT id FROM ingredients WHERE canonical_name = ?", (name,)).fetchone()
        if row:
            iid = row["id"]
        else:
            cur = db.execute(
                "INSERT INTO ingredients (canonical_name, aliases_json, aisle) VALUES (?, '[]', ?)",
                (name, aisle_for(name)),
            )
            iid = int(cur.lastrowid)
        never = 0
        have = 1 if never else 0
        db.execute(
            """INSERT INTO pantry_items
               (household_id, ingredient_id, name, quantity, have, never_shop, zone)
               VALUES (?, ?, ?, '', ?, ?, ?)""",
            (household_id, iid, name, have, never, zone[:20]),
        )
        existing.add(name)


def pantry_catalog() -> list[tuple[str, str]]:
    return _catalog_names()


def apply_seeds(db: PgConnection) -> None:
    seed_package_sizes(db)
    if not db.execute("SELECT 1 FROM households WHERE id = 1").fetchone():
        db.execute(
            "INSERT INTO households (id, name, prefs_json, created_at) VALUES (1, 'Home', '{}', ?)",
            (now(),),
        )
        db.execute("SELECT setval(pg_get_serial_sequence('households', 'id'), 1, true)")
    db.commit()
