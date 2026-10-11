"""Validate admin photos and store normalized images on the persistent food volume."""
import base64
import binascii
from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException
from app.assets import food_dir


def save_photo(data: str) -> str:
    try:
        header, encoded = data.split(",", 1)
        if header not in {"data:image/jpeg;base64", "data:image/png;base64", "data:image/webp;base64"}:
            raise ValueError()
        raw = base64.b64decode(encoded, validate=True)
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
        raise HTTPException(400, "Choose a JPEG, PNG, or WebP photo under 5 MB and 25 megapixels.") from exc
    name = f"admin-upload-{uuid4().hex}.jpg"
    (food_dir() / name).write_bytes(output.getvalue())
    return f"food/{name}"
