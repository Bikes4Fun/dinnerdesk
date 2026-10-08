from pathlib import Path
import pytest
from app.assets import catalog_dir, food_dir
from app.db.catalog import should_import_catalog


def test_application_requires_private_paths(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("DINNERDESK_CATALOG_DIR", raising=False)
    monkeypatch.delenv("FOOD_DIR", raising=False)
    with pytest.raises(RuntimeError, match="DINNERDESK_CATALOG_DIR"):
        catalog_dir()
    with pytest.raises(RuntimeError, match="FOOD_DIR"):
        food_dir()
    monkeypatch.delenv("DINNERDESK_IMPORT_CATALOG", raising=False)
    assert not should_import_catalog()


def test_explicit_asset_paths_are_validated(monkeypatch, tmp_path):
    monkeypatch.setenv("DINNERDESK_CATALOG_DIR", str(tmp_path))
    monkeypatch.setenv("FOOD_DIR", str(tmp_path))
    assert catalog_dir() == tmp_path
    assert food_dir() == tmp_path
    monkeypatch.setenv("FOOD_DIR", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="does not exist"):
        food_dir()
