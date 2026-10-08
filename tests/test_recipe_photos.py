from app.domain import recipe_photos


def test_allowed_photo_shows_when_database_id_differs_from_archive_id(monkeypatch):
    monkeypatch.setattr(recipe_photos, "USE", {"760.jpg": 760})
    assert recipe_photos.usable_photo("food/760.jpg", 392) == "food/760.jpg"


def test_unlisted_photo_stays_hidden(monkeypatch):
    monkeypatch.setattr(recipe_photos, "USE", {"760.jpg": 760})
    assert recipe_photos.usable_photo("food/other.jpg", 392) == ""
    assert recipe_photos.usable_photo("", 392) == ""
