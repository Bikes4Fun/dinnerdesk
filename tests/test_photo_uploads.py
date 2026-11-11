import base64
from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from app.domain.photo_uploads import save_photo
from app.domain.recipe_photos import usable_photo, photo_is_ai, photo_is_borrowed
from app.main import _food_file


def test_upload_survives_allowlist_and_serves_normalized_image(tmp_path, monkeypatch):
    monkeypatch.setenv('FOOD_DIR', str(tmp_path))
    image = BytesIO()
    Image.new('RGB', (20, 30), 'red').save(image, 'PNG')
    path = save_photo('data:image/png;base64,' + base64.b64encode(image.getvalue()).decode())
    assert usable_photo(path) == path
    assert not photo_is_ai(path)
    assert not photo_is_borrowed(path, '14803')
    with Image.open(_food_file(path.split('/')[-1])) as saved:
        assert saved.format == 'JPEG'
        assert saved.size == (20, 30)


@pytest.mark.parametrize('data', ['garbage', 'data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,broken', 'data:image/png;base64,dGV4dA=='])
def test_invalid_images_are_rejected_without_files(data, tmp_path, monkeypatch):
    monkeypatch.setenv('FOOD_DIR', str(tmp_path))
    with pytest.raises(HTTPException) as error:
        save_photo(data)
    assert error.value.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_photo_credit_uses_recorded_owner_and_source(monkeypatch):
    from app.domain.recipe_photos import photo_credit, CREDITS, AI
    monkeypatch.setitem(CREDITS, "credited.jpg", {"credit": "Dinnerdesk", "source_url": "https://example.com/photo"})
    assert photo_credit("food/credited.jpg") == {"credit": "Photo: Dinnerdesk", "source_url": "https://example.com/photo"}
    monkeypatch.setattr("app.domain.recipe_photos.AI", AI | {"credited.jpg"})
    assert photo_credit("food/credited.jpg")["credit"] == "AI-generated photo · Dinnerdesk"
    assert photo_credit("food/unrecorded.jpg")["credit"] == "Photo source not recorded"


def test_identical_photos_share_one_gallery_entry_and_keep_tested_overlay(tmp_path, monkeypatch):
    from app.domain.recipe_photos import unique_gallery
    from PIL.PngImagePlugin import PngInfo
    monkeypatch.setenv('FOOD_DIR', str(tmp_path))
    image = Image.new('RGB', (20, 30), 'red')
    image.save(tmp_path / 'original.png')
    metadata = PngInfo()
    metadata.add_text('Description', 'Developer tested')
    image.save(tmp_path / 'tested-copy.png', pnginfo=metadata)
    Image.new('RGB', (20, 30), 'blue').save(tmp_path / 'different.png')
    before = {file.name: file.read_bytes() for file in tmp_path.iterdir()}
    photos = [
        {'path': 'food/original.png', 'primary': True, 'tested': False, 'ai': False, 'shared': False},
        {'path': 'food/tested-copy.png', 'primary': False, 'tested': True, 'ai': False, 'shared': False},
        {'path': 'food/different.png', 'primary': False, 'tested': False, 'ai': False, 'shared': False},
    ]
    out = unique_gallery(photos)
    assert [p['path'] for p in out] == ['food/original.png', 'food/different.png']
    assert out[0]['primary'] and out[0]['tested']
    assert photos[0]['tested'] is False
    assert before == {file.name: file.read_bytes() for file in tmp_path.iterdir()}
    Image.new('RGB', (21, 30), 'green').save(tmp_path / 'tested-copy.png')
    assert len(unique_gallery(photos)) == 3


def test_gallery_dedup_handles_aliases_missing_files_and_remote_photos(tmp_path, monkeypatch):
    from app.domain.recipe_photos import unique_gallery
    monkeypatch.setenv('FOOD_DIR', str(tmp_path))
    photos = [{'path': 'food/missing.jpg', 'tested': False},
              {'path': '/food/missing.jpg', 'tested': True},
              {'path': 'https://example.test/missing.jpg', 'tested': False}]
    out = unique_gallery(photos)
    assert len(out) == 2 and out[0]['tested'] is True
    assert out[1]['path'] == 'https://example.test/missing.jpg'
