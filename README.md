# Dinnerdesk

A household meal planner: suggests the week's dinners, builds the grocery list, and combines
make-ahead prep. iPhone app (SwiftUI), website (React), and a Python API on PostgreSQL.

This proprietary portfolio repository presents the application code. The live app provides
viewing and testing. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).

| Doc | What it's for |
|---|---|
| [`docs/DESIGN.md`](docs/DESIGN.md) | How each feature works, screens, architecture, decisions |
| [`docs/TODO.md`](docs/TODO.md) | Issues, fixes, ideas, open questions (the only checklist) |
| [`docs/TESTER_CHECKLIST.md`](docs/TESTER_CHECKLIST.md) | What testers try on each build |
| [`docs/PRIVACY.md`](docs/PRIVACY.md) | Privacy policy shown in the app |

## Set up

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci --prefix web
npm run build --prefix web
```

## Run

| Setting | What it does |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL. **Required**: the server won't start without it. |
| `DINNERDESK_CATALOG_DIR` | Required directory of private catalog metadata and ingredient vectors, outside Git. |
| `FOOD_DIR` | Required directory of private recipe photos, outside Git. |
| `GROCERY_PHOTO_DIR` | Folder of individual food photos (kept outside Git). Locally: `/Users/turtlesoup/Repos/dd_support/references/individual grocery food items`. On Railway: a mounted volume. |
| `AUTH_REQUIRED` | When off, everyone shares one guest household. |

```bash
export DATABASE_URL=postgresql://localhost/dinnerdesk
export DINNERDESK_CATALOG_DIR="$(cd ../dd_support/catalog/dinnerdesk/data && pwd)"
export FOOD_DIR="$(cd ../dd_support/catalog/dinnerdesk/food && pwd)"
uvicorn app.main:app --reload          # API on http://localhost:8000
npm ci --prefix web && npm run dev --prefix web   # website
```

The iOS app is in `ios/dinnerdesk.xcodeproj`; build and run it in Xcode.

**Database changes** apply on server start: `app.db.database.init_db` creates tables and adds
missing columns. After pulling changes that touch `app/db/schema.sql`, restart the server.

**Deploy:** Railway builds the website and starts the API without importing recipes.
Before deploying this branch, upload private assets to persistent storage and set both required
asset paths. See [catalog storage and migration](docs/CATALOG_STORAGE.md). PostgreSQL records
remain independent of Git. Catalog import is an explicit operator action: `python -m app.db.catalog`.

## Test

```bash
# Pure logic tests (no database needed)
python -m pytest -q tests/test_prep.py tests/test_suggest.py tests/test_taste_rank.py

# Everything, including database tests. Use a dedicated test database, never the real one.
TEST_DATABASE_URL=postgresql://user:password@localhost/dinnerdesk_test python -m pytest -q
```

Database tests create and drop their own schema. They never fall back to `DATABASE_URL`.

## Rules for all work

**Recipes and photos (legal)**
- Recipes themselves (ingredients, amounts, steps, times) aren't copyrightable and can be reused.
- Never use third-party **photos** or **stories**. Image URLs in the archive are reference only.
- A catalog recipe shows in the app only once its steps are rewritten
  (`instructions_copied_from_third_party: false`) and it has a photo listed as usable in
  `recipe_photos.json` in `DINNERDESK_CATALOG_DIR`. Kitchens' own recipes always show.
- Mark third-party steps with `instructions_copied_from_third_party`, `instructions_source`,
  and `instructions_reviewed`. Tag `tested` once Dinnerdesk has reviewed a recipe.

**Docs**
- When a feature's behavior changes, update [`docs/DESIGN.md`](docs/DESIGN.md) and its step in
  [`docs/TESTER_CHECKLIST.md`](docs/TESTER_CHECKLIST.md) in the same commit.
- Before a test round, update the checklist's date and build line, rewrite **Focus for this
  build**, and move anything newly built out of **Not built yet**.
- New issues go in [`docs/TODO.md`](docs/TODO.md) → Inbox, with screenshots in the matching
  private `dd_support/review/` folder.

**Tips:** help text that explains a feature is a *tip*. Mark it with a hidden
`data-tip="<area>.<name>"` attribute; `python3 scripts/list_tips.py` lists them all.

**Screenshots and exports:** keep them in private `dd_support`, outside this code repository.
See [repository organization](docs/REPOSITORY.md).

## Recipe archive

The private catalog directory is a readable JSON snapshot of the recipe library, not the app's
database. The following paths are relative to `DINNERDESK_CATALOG_DIR`, outside Git.

- `recipes/{id}.json`: full recipes (name, servings, cook time, ingredients, steps,
  cookware, source URL, tags, and the instruction flags above)
- `recipes_index.json`: `complete` (id + name) and `under_construction`
- `templates/<family>/recipes.json`: template family lists
- `sides.json`, `recipe_tags.json`: side names and known tags
- `recipe_photos.json`: photos we may use, and which recipe each belongs to

The original archive came from [Mealime](https://www.mealime.com/recipes). The scraper isn't in
this repo; respect Mealime's terms and scrape politely if it's used again.
