"""Railway's deploy step: import the catalog that is already on the server.

Runs before the API starts (see railpack.json). It never stops the API from starting: if the
import fails, it says why and the site keeps the recipes it already has.

Recipes and photos reach the server one way only: dd_support's catalog sync (its
catalog_sync.py, run by a GitHub Action on every push that changes catalog/dinnerdesk/) uploads
the files into DINNERDESK_CATALOG_DIR and FOOD_DIR on the volume and imports them. A deploy
doesn't download anything; with DINNERDESK_IMPORT_CATALOG=1 it imports those same files again,
so a new version of the app sees the current catalog. DD_SUPPORT_* settings are no longer used.
"""

from __future__ import annotations

import os
import subprocess  # noqa: F401  (kept so tests can check no git command runs)
import sys


def main() -> None:
    if os.environ.get("DD_SUPPORT_REPO", "").strip():
        print("deploy: DD_SUPPORT_REPO is no longer used; the catalog sync puts files on the server",
              flush=True)
    # Imported only now: the photo allowlist is read when these modules load.
    from app.db.catalog import main as import_catalog, should_import_catalog

    if not should_import_catalog():
        print("deploy: DINNERDESK_IMPORT_CATALOG is not set; recipes not imported", flush=True)
        return
    try:
        import_catalog()
    except Exception as exc:  # noqa: BLE001 - never block startup
        print(f"deploy: catalog import failed, the site keeps its current recipes: {exc}",
              file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
