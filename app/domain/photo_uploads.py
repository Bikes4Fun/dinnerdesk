"""Validate uploaded images and store them normalized: recipe photos on the public food
volume, bug report screenshots in a private folder."""
import base64
import binascii
from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException
from app.assets import feedback_dir, food_dir


def _jpeg_bytes(raw: bytes, message: str) -> bytes:
    """Re-encode image bytes as JPEG, upright, at most 2400px. Re-encoding drops EXIF,
    including where a phone photo was taken."""
    try:
        if not raw or len(raw) > 5_000_000:
            raise ValueError()
        with Image.open(BytesIO(raw)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 25_000_000:
                raise ValueError()
            image.load()
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((2400, 2400))
            output = BytesIO()
            image.save(output, "JPEG", quality=90)
    except (ValueError, binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, message) from exc
    return output.getvalue()


def _data_url_bytes(data: str, message: str) -> bytes:
    try:
        header, encoded = data.split(",", 1)
        if header not in {"data:image/jpeg;base64", "data:image/png;base64", "data:image/webp;base64"}:
            raise ValueError()
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(400, message) from exc
    return raw


def save_photo(data: str) -> str:
    """Store a photo sent as a data: URL."""
    raw = _data_url_bytes(data, "Choose a JPEG, PNG, or WebP photo under 5 MB and 25 megapixels.")
    return save_photo_bytes(raw)


def save_photo_bytes(raw: bytes) -> str:
    """Store JPEG, PNG or WebP bytes as a normalized JPEG on the food volume."""
    jpeg = _jpeg_bytes(raw, "Choose a JPEG, PNG, or WebP photo under 5 MB and 25 megapixels.")
    name = f"admin-upload-{uuid4().hex}.jpg"
    (food_dir() / name).write_bytes(jpeg)
    return f"food/{name}"


def save_screenshot(data: str) -> str:
    """A bug report screenshot, stored privately. Returns its file name."""
    message = "Screenshots must be JPEG, PNG, or WebP images under 5 MB."
    jpeg = _jpeg_bytes(_data_url_bytes(data, message), message)
    name = f"feedback-{uuid4().hex}.jpg"
    (feedback_dir() / name).write_bytes(jpeg)
    return name
