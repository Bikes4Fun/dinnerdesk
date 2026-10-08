# Public code and private application data

The repository presents the application code for employer review. The live application provides viewing and testing. No demo recipes or illustrations are bundled.

Real recipe JSON, photos, ingredient mappings and trained vectors are kept outside Git. PostgreSQL independently stores imported recipe records and household state. Moving local input files does not delete or change database rows.

## Local private catalog

The preserved catalog is in the sibling support directory. Export these variables before starting the API or importing:

```sh
export DINNERDESK_CATALOG_DIR="$(cd ../dd_support/catalog/dinnerdesk/data && pwd)"
export FOOD_DIR="$(cd ../dd_support/catalog/dinnerdesk/food && pwd)"
```

Keep `dd_support` private. Its `catalog/dinnerdesk/migration-manifest.json` records the saved paths and SHA-256 checksums of all 153 files. Keep a separate backup; ignoring files is not a backup.

## Railway transition: required before deploying this branch

1. Back up PostgreSQL and private assets using your existing operational process.
2. Provision persistent storage for the private asset package, outside the Git deployment checkout. Copy `data/` and `food/` from the preserved package. Verify against the migration manifest after uploading. The local support copy alone is not accessible to Railway.
3. Set `DINNERDESK_CATALOG_DIR` to that storage's `data` directory and `FOOD_DIR` to its `food` directory. Retain existing `DATABASE_URL`, authentication and mail settings. Keep `GROCERY_PHOTO_DIR` if already configured.
4. Deploy after the private paths exist. Railway startup now applies schema initialization and starts the API; it does not import any recipe catalog. A missing asset directory fails startup with a clear configuration error.
5. Check existing recipes, photos, Taste Lab suggestions, pantry and household plans. Existing PostgreSQL rows retain their photo filenames; the external photo directory supplies those files, and external `recipe_photos.json` supplies the allowlist.

For a deliberate catalog update, run `python -m app.db.catalog` in an environment with the private asset paths and the intended database URL. The importer updates catalog records by slug and commits changes. This is an explicit maintenance operation, not part of every deployment. The deprecated `DINNERDESK_IMPORT_CATALOG` startup setting is no longer used.

No production database, Railway configuration or deployment was changed as part of this repository migration. Before deploying, you must complete the storage upload and environment configuration above.

## Railway setup completed October 8, 2026

The existing `weekplate-volume` attached to the Dinnerdesk app was reused. Its mount
path remains `/web/public/food/`; the PostgreSQL volume was not changed. A new folder
`dinnerdesk-catalog-2026-10-08` contains 150 private catalog and photo files plus a
SHA-256 manifest. The upload was downloaded again and all 150 checksums verified.

The app service now has these settings, saved without triggering a deployment:

```text
DINNERDESK_CATALOG_DIR=/web/public/food/dinnerdesk-catalog-2026-10-08/data
FOOD_DIR=/web/public/food/dinnerdesk-catalog-2026-10-08/food
```

The live service still runs GitHub `main`. Publish and deploy the cleaned code through
the normal release process to activate its external asset readers. The local Git
checkout has no remote configured. Existing volume files and database records were
not overwritten by this upload.

## Publication

The recovered Git repository has no earlier commits or remote. Its first commit can therefore contain only public source without rewriting history. `.gitignore` excludes legacy private directories, environment files, database backups and build output. If publishing to an existing remote with historical data, those old remote commits require a separate history review; this branch cannot remove data already published elsewhere.
