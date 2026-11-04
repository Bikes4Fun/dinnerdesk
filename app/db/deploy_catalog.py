"""Railway's deploy step: refresh the private catalog from dd_support, then import it.

Runs before the API starts (see railpack.json). It never stops the API from starting: if
GitHub or the import fails, it says why and the site keeps the recipes it already has.

With DD_SUPPORT_REPO set, a shallow, sparse git checkout of dd_support is kept at
DD_SUPPORT_DIR (on the volume, so later deploys download only what changed). Point
DINNERDESK_CATALOG_DIR and FOOD_DIR inside it:

    DD_SUPPORT_REPO=Bikes4Fun/weekplate        owner/name on GitHub, or any git URL or path
    DD_SUPPORT_TOKEN=github_pat_...            read-only token for a private GitHub repo
    DD_SUPPORT_BRANCH=main                     optional
    DD_SUPPORT_DIR=/web/public/food/dd_support
    DINNERDESK_CATALOG_DIR=$DD_SUPPORT_DIR/catalog/dinnerdesk/data
    FOOD_DIR=$DD_SUPPORT_DIR/catalog/dinnerdesk/food
    DINNERDESK_IMPORT_CATALOG=1                import the catalog on every deploy

Then every deploy adds recipes that are rewritten and have one of our photos, and applies
catalog edits. Edits made in the app's admin pages are kept (see upsert_catalog_recipe).
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

SPARSE_PATHS = ["catalog/dinnerdesk", "recipes/rewritten"]
# dd_support keeps photos in Git LFS; a checkout alone holds only small pointer files.
LFS_PATHS = "catalog/dinnerdesk/food/**"


def _repo_url(repo: str) -> str:
    if "://" in repo or repo.startswith(("git@", "/", ".", "~")):
        return os.path.expanduser(repo)
    return f"https://github.com/{repo}.git"


def _git(args: list[str], cwd: Path | None = None) -> None:
    token = os.environ.get("DD_SUPPORT_TOKEN", "").strip()
    auth = []
    if token:
        # Passed per command, so the token is never written into the checkout's git config.
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        auth = ["-c", f"http.extraHeader=Authorization: Basic {basic}"]
    # Photos are fetched by _pull_photos, only for the folders the app reads.
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}
    subprocess.run(["git", *auth, *args], cwd=cwd, env=env, check=True, capture_output=True, text=True)


def _pull_photos(target: Path) -> None:
    """Replace LFS pointer files under catalog/dinnerdesk/food with the photos. Only new or
    changed photos are downloaded; the rest are already on the volume."""
    attributes = target / ".git" / "info" / "attributes"
    attributes.parent.mkdir(parents=True, exist_ok=True)
    attributes.write_text(f"{LFS_PATHS} filter=lfs diff=lfs merge=lfs -text\n")
    _git(["lfs", "install", "--local", "--skip-smudge"], cwd=target)
    _git(["lfs", "pull", f"--include={LFS_PATHS}"], cwd=target)


def sync_dd_support() -> bool:
    """Bring DD_SUPPORT_DIR up to date with the dd_support branch. False if not configured."""
    repo = os.environ.get("DD_SUPPORT_REPO", "").strip()
    if not repo:
        return False
    target = Path(os.environ.get("DD_SUPPORT_DIR", "").strip() or "dd_support").expanduser()
    branch = os.environ.get("DD_SUPPORT_BRANCH", "").strip() or "main"
    if not (target / ".git").is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--depth", "1", "--filter=blob:none", "--sparse", "--branch", branch,
              _repo_url(repo), str(target)])
        _git(["sparse-checkout", "set", *SPARSE_PATHS], cwd=target)
    else:
        _git(["remote", "set-url", "origin", _repo_url(repo)], cwd=target)
        _git(["sparse-checkout", "set", *SPARSE_PATHS], cwd=target)
        _git(["fetch", "--depth", "1", "origin", branch], cwd=target)
        _git(["reset", "--hard", "FETCH_HEAD"], cwd=target)
    _pull_photos(target)
    return True


def main() -> None:
    try:
        if sync_dd_support():
            print("deploy: dd_support catalog is up to date", flush=True)
    except subprocess.CalledProcessError as exc:
        print(f"deploy: could not update dd_support, keeping the files already here: {exc.stderr.strip()}",
              file=sys.stderr, flush=True)
    except Exception as exc:  # noqa: BLE001 - never block startup
        print(f"deploy: could not update dd_support, keeping the files already here: {exc}",
              file=sys.stderr, flush=True)

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
