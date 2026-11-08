"""Coming-soon recipes: one of our photos is in, our own steps aren't written yet.

Every rule about them lives in this class, and both the catalog import (app/db/catalog.py) and
the API (app/routes.py) use it, so they can't disagree. The apps only read the `coming_soon` flag
on a recipe card and show it greyed out, labelled, and not clickable.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.offering import Offering


class ComingSoon:
    # provenance_json of a coming-soon row contains this (SQL LIKE pattern / plain text).
    MARK_SQL = '%"coming_soon": true%'
    MARK = '"coming_soon": true'
    # What a coming-soon record keeps from the original: everything but its words.
    KEEP = ("id", "slug", "name", "servings", "cooking_minutes", "ingredients", "cookware",
            "source_url", "tags", "photo_path", "variant_of")

    @classmethod
    def record(cls, data: dict) -> dict:
        """The parts of a not-yet-rewritten recipe the app may keep: everything but its steps."""
        out = {k: data[k] for k in cls.KEEP if k in data}
        out.update({"instructions": [], "instructions_copied_from_third_party": True, "coming_soon": True})
        return out

    @staticmethod
    def is_candidate(data: dict, photos: dict[str, list[str]]) -> bool:
        """A catalog recipe file that should show as coming soon: has one of our photos, isn't
        withheld (pizza, breakfast, snacks) or retired, and its steps are someone else's or missing."""
        if Offering.withheld(str(data.get("name") or ""), data.get("tags")) or data.get("retired"):
            return False
        photo = Path((data.get("photo_path") or "").strip()).name
        return bool(photo) and photo in photos.get("*", []) and bool(
            data.get("instructions_copied_from_third_party") or not data.get("instructions"))

    @classmethod
    def is_row(cls, row) -> bool:
        """A database recipe row that is coming soon (catalog recipe marked at import)."""
        return row["household_id"] is None and cls.MARK in (row["provenance_json"] or "")
