from app.domain import recipe_photos


def test_allowed_photo_shows_when_database_id_differs_from_archive_id(monkeypatch):
    monkeypatch.setattr(recipe_photos, "USE", {"760.jpg": 760})
    assert recipe_photos.usable_photo("food/760.jpg", 392) == "food/760.jpg"


def test_unlisted_photo_stays_hidden(monkeypatch):
    monkeypatch.setattr(recipe_photos, "USE", {"760.jpg": 760})
    assert recipe_photos.usable_photo("food/other.jpg", 392) == ""
    assert recipe_photos.usable_photo("", 392) == ""


def test_ai_photos_are_marked_by_flag_or_file_name(monkeypatch):
    """#33: AI photos say so with a purple star tip on the recipe."""
    monkeypatch.setattr(recipe_photos, "AI", {"812.png"})
    assert recipe_photos.photo_is_ai("food/812.png")
    assert recipe_photos.photo_is_ai("food/905_lemon-chicken_ai-generated.png")
    assert not recipe_photos.photo_is_ai("food/760.jpg")
    assert not recipe_photos.photo_is_ai("")


def test_borrowed_photos_are_marked(monkeypatch):
    """#33: a photo taken for another recipe says so; the recipe it was taken for doesn't."""
    monkeypatch.setattr(recipe_photos, "USE", {"760.jpg": 760, "stock-salad.jpg": None, "812.png": 812})
    monkeypatch.setattr(recipe_photos, "SHARED", {"stock-salad.jpg"})
    monkeypatch.setattr(recipe_photos, "AI", {"812.png"})
    assert not recipe_photos.photo_is_borrowed("food/760.jpg", "760")
    assert recipe_photos.photo_is_borrowed("food/760.jpg", "905")
    assert not recipe_photos.photo_is_borrowed("food/760.jpg", None)  # no archive id: can't tell
    assert recipe_photos.photo_is_borrowed("food/stock-salad.jpg", "905")
    assert not recipe_photos.photo_is_borrowed("food/812.png", "905")  # AI photos get the AI tip
    assert not recipe_photos.photo_is_borrowed("food/unlisted.jpg", "905")


def test_archive_id_comes_from_the_source_url_or_slug():
    assert recipe_photos.archive_id_of("https://example.com/recipes/760/", None) == "760"
    assert recipe_photos.archive_id_of("https://example.com/r/lemon-chicken?x=1", "905") == "905"
    assert recipe_photos.archive_id_of(None, "lemon-chicken") is None
