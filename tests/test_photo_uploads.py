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


def test_jpeg_upload_of_tested_png_is_one_photo_with_original_credit(tmp_path, monkeypatch):
    from app.domain.recipe_photos import unique_gallery, same_photo
    from PIL import ImageDraw
    monkeypatch.setenv("FOOD_DIR", str(tmp_path))
    image = Image.new("RGB", (320, 400))
    image.putdata([(40 + x * 150 // 320, 40 + y * 150 // 400, 40 + (x + y) * 150 // 720)
                   for y in range(400) for x in range(320)])
    image.save(tmp_path / "tested.png")
    uploaded = save_photo("data:image/png;base64," + base64.b64encode((tmp_path / "tested.png").read_bytes()).decode())
    photos = [{"path": uploaded, "primary": True, "tested": False, "credit": "Photo uploaded to Dinnerdesk"},
              {"path": "food/tested.png", "tested": True, "credit": "Photo: Deanna", "source_url": "https://example.test/photo"}]
    before = {file.name: file.read_bytes() for file in tmp_path.iterdir()}
    out = unique_gallery(photos)
    assert len(out) == 1
    assert out[0]["path"] == uploaded and out[0]["primary"] and out[0]["tested"]
    assert out[0]["credit"] == "Photo: Deanna" and out[0]["source_url"] == "https://example.test/photo"
    assert before == {file.name: file.read_bytes() for file in tmp_path.iterdir()}
    assert not photos[0]["tested"]
    edited = image.copy()
    ImageDraw.Draw(edited).rectangle((100, 100, 130, 130), fill="white")
    edited.save(tmp_path / "edited.png")
    assert not same_photo("food/tested.png", "food/edited.png")
    image.crop((0, 0, 280, 400)).save(tmp_path / "crop.png")
    assert not same_photo("food/tested.png", "food/crop.png")
    image.resize((160, 200), Image.Resampling.LANCZOS).save(tmp_path / "resized.jpg", quality=90)
    assert same_photo("food/tested.png", "food/resized.jpg")
