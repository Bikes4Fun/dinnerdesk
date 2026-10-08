"""Private runtime assets, separate from PostgreSQL and the code repository."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def catalog_dir() -> Path:
    value = os.environ.get("DINNERDESK_CATALOG_DIR", "").strip()
    if not value:
        raise RuntimeError("Set DINNERDESK_CATALOG_DIR to the private catalog metadata directory before starting the application")
    path = Path(value).expanduser()
    if not path.is_dir():
        raise RuntimeError(f"Catalog directory does not exist: {path}")
    return path


def food_dir() -> Path:
    value = os.environ.get("FOOD_DIR", "").strip()
    if not value:
        raise RuntimeError("Set FOOD_DIR to the private recipe photo directory before starting the application")
    path = Path(value).expanduser()
    if not path.is_dir():
        raise RuntimeError(f"Recipe photo directory does not exist: {path}")
    return path
