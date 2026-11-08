"""AI photos in the photo folder count without being listed in recipe_photos.json."""
from app.domain.recipe_photos import found_ai_photos


def test_folder_ai_photos_count_on_their_own(tmp_path):
    for name in [
        "2197_orange-glazed-pork-chops_ai-generated.png",
        "29876_blt_PRIMARY_ai-generated.png",
        "29876_blt_ai-generated.png",
        "guacamole_guacamole_ai-generated.png",
        "11759790_REVIEW_baked-queso-chicken_ai-generated.png",  # still being judged
        "4400_REDO_fish-tacos_ai-generated.png",
        "1606_taco.jpg",  # not marked AI: must be listed by hand
        "allrecipes_123_photo_ai-generated.png",  # names a recipe site
    ]:
        (tmp_path / name).write_bytes(b"x")
    assert found_ai_photos(tmp_path) == [
        ("29876_blt_PRIMARY_ai-generated.png", 29876),  # primary first
        ("2197_orange-glazed-pork-chops_ai-generated.png", 2197),
        ("29876_blt_ai-generated.png", 29876),
        ("guacamole_guacamole_ai-generated.png", None),
    ]


def test_missing_folder_finds_nothing(tmp_path):
    assert found_ai_photos(tmp_path / "nope") == []
