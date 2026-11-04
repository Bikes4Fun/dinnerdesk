"""Explicit, backed-up ingredient cleanup. Never runs during app startup.

Preview: python -m app.db.ingredient_cleanup
Apply only after reviewing the preview: python -m app.db.ingredient_cleanup --apply --backup PATH
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TABLES = ("ingredients", "recipe_ingredients", "grocery_lines", "pantry_items",
          "ingredient_reports", "grocery_places", "household_overrides")


def snapshot(conn):
    return {table: [dict(row) for row in conn.execute(f"SELECT * FROM {table}")]
            for table in TABLES}


def plan_cleanup(data):
    from app.domain.pantry_catalog import ingredient_name

    groups = {}
    for row in sorted(data["ingredients"], key=lambda r: r["id"]):
        groups.setdefault(ingredient_name(row["canonical_name"]), []).append(row)
    identities, conflicts = [], []
    for name, rows in groups.items():
        keep = next((r for r in rows if r["canonical_name"] == name), rows[0])
        if not name:
            conflicts.append({"ingredient_ids": [r["id"] for r in rows], "reason": "empty normalized name"})
        for field in ("default_unit", "package_size", "package_unit"):
            if len({r[field] for r in rows if r[field]}) > 1:
                conflicts.append({"name": name, "field": field, "reason": "different ingredient metadata"})
        identities.append({"name": name, "keep": keep["id"],
                           "duplicates": [r["id"] for r in rows if r["id"] != keep["id"]]})
    placements = {}
    for row in data["grocery_places"]:
        placements.setdefault((row["household_id"], ingredient_name(row["name"])), []).append(row)
    for (household, name), rows in placements.items():
        if len({(r["store"], r["aisle"]) for r in rows}) > 1:
            conflicts.append({"household_id": household, "name": name,
                              "reason": "different saved store/aisle choices"})
    return {"identities": identities, "conflicts": conflicts,
            "duplicate_ingredients": sum(len(i["duplicates"]) for i in identities),
            "renamed_ingredients": sum(r["canonical_name"] != ingredient_name(r["canonical_name"])
                                       for r in data["ingredients"])}


def apply_cleanup(conn, backup_path):
    """Explicit maintenance operation; caller must review conflicts and authorize it."""
    from app.db.database import transaction
    from app.domain.pantry_catalog import ingredient_name
    with transaction(conn):
        conn.execute("LOCK TABLE " + ", ".join(TABLES) + " IN SHARE ROW EXCLUSIVE MODE")
        data = snapshot(conn)
        plan = plan_cleanup(data)
        if plan["conflicts"]:
            raise ValueError("Resolve preview conflicts before applying ingredient cleanup")
        # Exclusive creation prevents overwriting the only copy of a previous backup.
        with Path(backup_path).open("x", encoding="utf-8") as backup:
            json.dump(data, backup, ensure_ascii=False, indent=2)
        by_id = {r["id"]: r for r in data["ingredients"]}
        for identity in plan["identities"]:
            keep = by_id[identity["keep"]]
            aliases = set(json.loads(keep["aliases_json"] or "[]"))
            metadata = {f: keep[f] for f in ("default_unit", "package_size", "package_unit")}
            for old_id in identity["duplicates"]:
                old = by_id[old_id]
                aliases.update(json.loads(old["aliases_json"] or "[]"))
                aliases.add(old["canonical_name"])
                for field in metadata:
                    metadata[field] = metadata[field] or old[field]
                for table in ("recipe_ingredients", "grocery_lines", "pantry_items", "ingredient_reports"):
                    conn.execute(f"UPDATE {table} SET ingredient_id = ? WHERE ingredient_id = ?",
                                 (keep["id"], old_id))
                conn.execute("DELETE FROM ingredients WHERE id = ?", (old_id,))
            if keep["canonical_name"] != identity["name"]:
                aliases.add(keep["canonical_name"])
            conn.execute("""UPDATE ingredients SET canonical_name = ?, aliases_json = ?,
                         default_unit = ?, package_size = ?, package_unit = ? WHERE id = ?""",
                         (identity["name"], json.dumps(sorted(aliases)), *metadata.values(), keep["id"]))
        for table, fields in (("pantry_items", ("name",)),
                              ("grocery_lines", ("custom_text", "name_override")),
                              ("household_overrides", ("from_name", "to_name"))):
            for row in data[table]:
                for field in fields:
                    if row[field] is not None:
                        conn.execute(f"UPDATE {table} SET {field} = ? WHERE id = ?",
                                     (ingredient_name(row[field]), row["id"]))
        # Conflicting placements are rejected above. Identical aliases can be
        # collapsed inside one household without affecting another's preferences.
        for row in data["grocery_places"]:
            name = ingredient_name(row["name"])
            if name == row["name"]:
                continue
            conn.execute("DELETE FROM grocery_places WHERE household_id = ? AND name = ?",
                         (row["household_id"], row["name"]))
            conn.execute("""INSERT INTO grocery_places (household_id, name, store, aisle)
                         VALUES (?, ?, ?, ?) ON CONFLICT(household_id, name) DO NOTHING""",
                         (row["household_id"], name, row["store"], row["aisle"]))
        return plan


def main():
    from app.db.database import connect
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.apply and args.backup is None:
        parser.error("--apply requires --backup PATH")
    conn = connect()
    try:
        plan = apply_cleanup(conn, args.backup) if args.apply else plan_cleanup(snapshot(conn))
        print(json.dumps(plan, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
