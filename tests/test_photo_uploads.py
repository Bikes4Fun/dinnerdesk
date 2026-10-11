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
