"""Coming-soon recipes: our photo is in, the rewritten steps aren't. Needs no database."""
from app.db.catalog import coming_soon_record, is_coming_soon

PHOTOS = {"*": ["29876_blt_PRIMARY_ai-generated.png"]}


def _original(**extra):
    return {"id": 29876, "slug": "29876", "name": "BLT", "servings": 2,
            "photo_path": "food/29876_blt_PRIMARY_ai-generated.png",
            "instructions": [{"step": "Someone else's words."}],
            "instructions_copied_from_third_party": True, **extra}


def test_original_with_our_photo_is_coming_soon():
    assert is_coming_soon(_original(), PHOTOS)


def test_needs_our_photo_and_not_retired():
    assert not is_coming_soon(_original(photo_path="food/other.png"), PHOTOS)
    assert not is_coming_soon(_original(retired=True), PHOTOS)


def test_rewritten_recipe_is_ready_not_coming_soon():
    assert not is_coming_soon(_original(instructions_copied_from_third_party=False), PHOTOS)


def test_record_drops_the_copied_steps():
    rec = coming_soon_record(_original(description="copied blurb"))
    assert rec["instructions"] == [] and rec["coming_soon"] is True
    assert rec["instructions_copied_from_third_party"] is True  # never public
    assert "description" not in rec and rec["photo_path"].endswith("PRIMARY_ai-generated.png")
