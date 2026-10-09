"""Database tests use PostgreSQL, isolated by schema. Never default to Railway."""
import os
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

# Supply isolated test assets before application modules are imported.
_TEST_PHOTOS = TemporaryDirectory(prefix="dinnerdesk-test-photos-")
os.environ["DINNERDESK_CATALOG_DIR"] = str(Path(__file__).parent / "fixtures" / "catalog")
os.environ["FOOD_DIR"] = _TEST_PHOTOS.name


@pytest.fixture(autouse=True)
def isolated_database(request, monkeypatch):
    # Pure domain tests don't need a database.
    modules = {'test_api', 'test_auth', 'test_password_reset', 'test_kitchen_grocery', 'test_yolo'}
    if request.module.__name__.split('.')[-1] not in modules and request.node.name != 'test_review_api_is_proposal_only':
        yield
        return
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.fail('TEST_DATABASE_URL is required for PostgreSQL integration tests')
    import psycopg
    from psycopg import sql
    schema = 'test_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        monkeypatch.setenv('DATABASE_URL', url)
        monkeypatch.setenv('DATABASE_SCHEMA', schema)
        monkeypatch.setenv('DINNERDESK_IMPORT_CATALOG', '0')
        # Taste Lab initializes its tables once per cached module. Each test uses a
        # fresh schema, so the module must initialize against that schema as well.
        import app.taste_lab
        monkeypatch.setattr(app.taste_lab, '_mod', None)
        yield
        admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
