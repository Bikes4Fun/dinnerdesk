# Dinnerdesk

A household meal planner: suggests the week's dinners, builds the grocery list, and combines
make-ahead prep. iPhone app (SwiftUI), website (React), and a Python API on PostgreSQL.
Screenshots below are the iPhone app.

This proprietary portfolio repository presents the application code. The live app provides
viewing and testing. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).

## What it does

**Plan** is this week’s dinners. An empty week offers **New meal plan** (a proposal you approve
before it replaces the week) or **Add meals** from Recipes. Meals show as a list with Schedule,
or as a grid. The Plan badge counts meals not cooked yet.

| Empty week | This week’s meals |
|---|---|
| ![Empty plan with New meal plan and Add meals](docs/images/plan-empty.png) | ![Four dinners in a list, each with Schedule](docs/images/plan-list.jpg) |

| Grid | Plan menu |
|---|---|
| ![Same week as a two-column grid](docs/images/plan-grid.jpg) | ![Plan menu: New meal plan, Fill in this plan, Edit plan, Mark all cooked, Grid View, Save as draft, Saved plans and history](docs/images/plan-menu.png) |

**Fill in this plan** keeps meals already chosen and suggests only the open slots. The same
menu edits the week, marks every meal cooked, switches list and grid, saves a draft, or opens
saved plans and history. Nothing is deleted when you start a new plan; the live week moves
to history.

**Grocery** is built from the plan, grouped by aisle, and filtered by store. Check items off
while you shop. The badge counts items still to buy. **+** adds a line that is not a recipe
ingredient.

![Grocery list filtered to Costco, with produce, dairy, and pantry](docs/images/grocery.png)

**Weekend prep** is the make-ahead work for this plan: chop and batch now, cook fresh later.
A ring and one bar per section (vegetables, aromatics, protein, cheese, sauce, more) show
progress. Done items leave the list until **Show completed**.

![Weekend prep with 4 of 12 done and the vegetables section open](docs/images/prep.png)

**Recipes** is always its own tab: search, favorites, To try, and the household’s diet,
allergy, and avoid filters.

**Taste Lab** (More) learns what this household will cook. **Swipe meals** and **Suggest
plans** are separate. A pass is not suggested again. **Swipe history** can change a like to
a pass, or the other way. Likes, passes, and filters are saved for the household.

| Taste Lab | Swiping a meal |
|---|---|
| ![Taste Lab home: pick up where you left off, Swipe meals and Suggest plans](docs/images/taste-lab.jpg) | ![Swipe card for chicken kebabs, with pass and like](docs/images/taste-lab-swipe.jpg) |

**More** also opens My kitchen (pantry, staples, substitutions, stores and aisles, family
portions), Settings, and the Quick start tour. Prep is its own tab on larger phones and is
always under More. Guests can use the app without an account.

| Doc | What it's for |
|---|---|
| [`docs/ABOUT.md`](docs/ABOUT.md) | What Dinnerdesk does, for readers and users. Also at `/about` on the website. |
| [`docs/DESIGN.md`](docs/DESIGN.md) | How each feature works, screens, architecture, decisions |
| [`docs/TODO.md`](docs/TODO.md) | Which GitHub issue covers which area |
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
| `ADMIN_EMAIL` | The one account that can use the admin tools. Empty means no admin. |
| `AUTH_REQUIRED` | When off, everyone shares one guest household. |
| `SUPPORT_EMAIL` | Contact address shown on `/support` (the App Store support URL). Empty shows “not set up yet”. |

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
asset paths. See [private catalog and deployment](#private-catalog-and-deployment). PostgreSQL records
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
- One exception: when a cook imports a recipe into their own kitchen, the page's photo is copied
  for that kitchen only (never the catalog), and its link is kept as a fallback. Cooks can use
  their own photo instead; what they upload is their responsibility.
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
- New issues go on GitHub. [`docs/TODO.md`](docs/TODO.md) only maps areas to issue numbers.
  Screenshots stay in the matching private `dd_support/review/` folder.

**Tips:** help text that explains a feature is a *tip*, shown on a pale purple card with a
sparkle star beside what it explains. Use `<Tip id>` (web) or `StarTip(id:)` (iPhone);
`python3 scripts/list_tips.py` lists them all.

**Screenshots:** product screens in [`docs/images/`](docs/images/) illustrate this README and
[`docs/DESIGN.md`](docs/DESIGN.md). Review shots and exports stay in private `dd_support`.
See [private catalog and deployment](#private-catalog-and-deployment).

## Recipe archive

The private catalog directory is a readable JSON snapshot of the recipe library, not the app's
database. The following paths are relative to `DINNERDESK_CATALOG_DIR`, outside Git.

- `recipes/{id}.json`: full recipes (name, servings, cook time, ingredients, steps,
  cookware, source URL, tags, and the instruction flags above)
- `recipes_index.json`: `complete` (id + name) and `under_construction`
- `templates/<family>/recipes.json`: template family lists
- `sides.json`, `recipe_tags.json`: side names and known tags
- `recipe_photos.json`: photos we may use, and which recipe each belongs to

Private archive material is for reference and review. Publish our own instructions and
our/user-provided photos. Third-party apps inform workflow ideas; they are not implementation specifications.


## Private catalog and deployment

Keep real recipe JSON, photos, ingredient mappings, trained vectors, research, screenshots,
and exports outside Git in the private sibling `dd_support` directory. The ignored legacy
`data/`, `food/`, and `tastelab/data/` directories are not bundled demo content. PostgreSQL
stores imported recipes and household state independently; moving local files does not alter
its records. Use the environment settings in **Run** above for local catalog access.

The original separation preserved 153 files under `../dd_support/catalog/dinnerdesk/`.
Its `migration-manifest.json` records their paths and SHA-256 checksums. Keep a separate
backup: ignoring files is not a backup. Earlier screenshot cleanup records remain under
`dd_support/review/dinnerdesk/`.

### Railway private storage

Before deploying to a new environment:

1. Back up PostgreSQL and private assets using the existing operational process.
2. Upload private `data/` and `food/` to persistent storage outside the Git checkout and
   verify checksums against the migration manifest. A local support copy is not available
   to Railway.
3. Set `DINNERDESK_CATALOG_DIR` and `FOOD_DIR` to the uploaded directories. Retain existing
   database, authentication, mail, and `GROCERY_PHOTO_DIR` settings.
4. Deploy after the private paths exist. Startup initializes the schema and starts the API;
   it does not import recipes. Missing required asset directories fail configuration checks.
5. Verify recipes, photos, Taste Lab, pantry, and household plans. Database photo filenames
   resolve through the external photo directory and the `recipe_photos.json` allowlist.

Catalog updates are deliberate operator actions: `python -m app.db.catalog` updates records
by slug and commits to the configured database. The deprecated `DINNERDESK_IMPORT_CATALOG`
startup setting is no longer used.

**Recorded Railway setup, October 8, 2026:** the existing `weekplate-volume` mount at
`/web/public/food/` was reused; the PostgreSQL volume was unchanged. The folder
`dinnerdesk-catalog-2026-10-08` received 150 private catalog/photo files plus a SHA-256
manifest. Downloading the upload again verified all 150 checksums. Settings were saved
without triggering a deployment:

```text
DINNERDESK_CATALOG_DIR=/web/public/food/dinnerdesk-catalog-2026-10-08/data
FOOD_DIR=/web/public/food/dinnerdesk-catalog-2026-10-08/food
```

These are historical setup records, not confirmation of current deployment state. Existing
volume files and database records were not overwritten by that upload.

### Repository maintenance

The repository was recovered with a fresh history; it now has a configured GitHub remote.
Ignoring private files does not remove them from older or separate public histories. Review
any such history before publication. Keep `dd_support` private and backed up, review Python
dependency locking before releases, and verify third-party asset permissions from records.
Font licenses remain in their font directories and [third-party notices](THIRD_PARTY_NOTICES.md).

Use the existing core documents for future updates: this README for setup and operations,
`DESIGN.md` for implemented behavior, `TODO.md` for issues/proposals/research, and
`TESTER_CHECKLIST.md` for concise testing. Keep the privacy policy and legal notices separate.

### Admin recipe photo updates

In the recipe editor, choose a JPEG, PNG, or WebP photo (up to 5 MB and
25 megapixels). The preview is saved with the recipe. For catalog recipes, Save
replaces the catalog photo for everyone; Save as copy applies it only to the new
kitchen recipe. Uploads are normalized to JPEG with metadata removed and stored
in `FOOD_DIR`, which must be writable persistent storage. Back up that directory
alongside PostgreSQL. Catalog imports preserve photos uploaded by admins.
