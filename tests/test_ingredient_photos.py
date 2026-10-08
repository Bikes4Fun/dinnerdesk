import pytest
from app.domain.ingredient_photos import photo_path, photo_file, photo_directory


def test_photo_gallery_is_external_and_unknown_food_reserves_space(monkeypatch, tmp_path):
    monkeypatch.setenv('GROCERY_PHOTO_DIR', str(tmp_path))
    for filename in (
        'orange carrots.jpg',
        'garlic.jpg',
        'chicken breast.jpg',
        'red or purple onions.jpg',
    ):
        (tmp_path / filename).write_bytes(b'photo')
    assert photo_path('medium carrots') == '/grocery-food/orange%20carrots.jpg'
    assert photo_path('minced garlic') == '/grocery-food/garlic.jpg'
    assert photo_path('boneless skinless chicken breast') == '/grocery-food/chicken%20breast.jpg'
    assert photo_path('red onion') == '/grocery-food/red%20or%20purple%20onions.jpg'
    assert photo_path('vegetable broth') is None
    assert photo_path('carrot juice') is None
    assert photo_path('garlic powder') is None
    assert photo_file('../orange carrots.jpg') is None
    assert photo_file('orange carrots.jpg').read_bytes() == b'photo'


def test_invalid_gallery_and_missing_mapped_photo_fail(monkeypatch, tmp_path):
    monkeypatch.setenv('GROCERY_PHOTO_DIR', str(tmp_path / 'missing'))
    with pytest.raises(RuntimeError, match='existing ingredient photo directory'):
        photo_directory()
    monkeypatch.setenv('GROCERY_PHOTO_DIR', str(tmp_path))
    with pytest.raises(RuntimeError, match='Mapped ingredient photo is missing'):
        photo_path('garlic')


def test_unconfigured_gallery_has_no_photo(monkeypatch):
    monkeypatch.delenv('GROCERY_PHOTO_DIR', raising=False)
    assert photo_path('carrots') is None
