# Dinnerdesk design

What the app does and how it's built. This file describes how things work; it has no
checkboxes. Work still to do, ideas, and open questions live in [`TODO.md`](TODO.md).

- **Features** are in the same order as [`TESTER_CHECKLIST.md`](TESTER_CHECKLIST.md). When a rule
  here changes, update the matching tester step in the same commit.
- **Must** = required behavior. **Must not** = things it should never do. **Bug if** = what
  to look for when checking it.

**Position:** a meal planner first: it tells you what to eat next, then builds the grocery
list and prep. Nutrition may come later. It is not a food diary.

---

## Catalog vs this kitchen

**Catalog** is our recipe library. **This kitchen** is one household's plan, grocery list,
pantry, favorites, hides, filters, and any edits on top of catalog recipes.

- A cook tapping Save never writes the catalog. An in-place edit is a kitchen *overlay* on the
  same recipe id. Restore deletes the overlay and the catalog text comes back.
- Copy makes a new kitchen-owned recipe (`parent_recipe_id` = the catalog id) and leaves the
  original alone.
- The operator changes the catalog by publishing (editing seed/JSON and importing, or an explicit
  catalog write that isn't the normal Save button). Publishing changes what Restore returns. It
  must not wipe a kitchen's overlay.

**Bug if:** kitchen Save changes a `recipes` row where `household_id` is null, or a favorite,
hide, plan, pantry, or grocery action creates a new catalog recipe.

---

## Features

### 1. Accounts and Quick start

Email-and-password accounts with a session cookie. All normal features work signed out in a
private kitchen identified by a random guest cookie. Expired sign-in sessions fall back to guest
access. Creating an account keeps the guest kitchen and revokes its anonymous access. Forgot password works on the website and in the iOS app.

The Quick start tour is optional: a short what-to-eat survey (diet, avoids, cook time, the same
filters as Settings) and one screen each for Recipes, This week, Grocery, and Weekend prep.

- **Must:** offer Quick start or Skip on first visit; never block the app; replay from
  Settings and More.
- **Must not:** force the survey before browsing; bury Skip.
- **Bug if:** skipping brings the tour back on the next visit, or saving filters writes a
  catalog recipe.

### 2. Taste Lab

A short session that teaches the app what this household likes. Separate **Swipe meals**
and **Suggest plans** choices let cooks use either activity independently on iPhone and web.
Swiping skips the guided quiz/plan sequence and ends after its meal batch; reviewing plans
does not require swiping first. Filters remain editable in either activity. Both activities
are offered as optional next steps after a session.

The Taste Lab introduction separates its photo mosaic, heading, summary, activity buttons,
and privacy note with generous vertical spacing. These intro rules do not change swipe
cards or suggested-plan sizing. Small screens and larger text can scroll.

- **Must:** "Not for us" shows another plan, not a dead end. Swapping a meal in a sample plan
  offers choices, with **More options**. "None" clears allergies or avoids. When nothing is left,
  say so clearly and suggest what to change.
- **Must:** answers are saved to the signed-in account and used for suggestions. Only this
  household's answers count; another household's swipes are never used.
- **Bug if:** a meal outside the filters appears, or the decision buttons cover meal names.

### 3. Suggested meal plans

Plan → ⋯ → New meal plan → Suggest meals for me. Suggestions arrive as a **proposal** to
review, not a new plan.

- **Must:** the current plan and grocery list stay unchanged until the proposal is approved.
  Approving makes it the plan and rebuilds groceries. Declining keeps the current plan and offers
  another proposal.
- **Must:** review keeps headings and controls compact; explanatory suggestion text is
  omitted from the visible review (updated October 9).
- **Must:** review uses the app's own plain style, not Taste Lab's bordered cards: a rounded
  square photo with a white swap button in its corner, then the name and cook
  time. Approve plan (filled) and Suggest another (outlined) are equal full-width buttons, with
  Improve suggestions centered below.
- **Must:** swap any suggested meal from a picker with search. Choices respect the filters and
  exclude meals already on the proposal. Cancelling the picker changes nothing and records no
  dislike.
- **Must:** "Keep my selected meals and fill the rest" keeps the meals already chosen, marked
  "Your selection", and they can't be swapped.
- **Must:** a proposal closed without a decision can be reopened later, including after
  restarting the app.
- **Bug if:** a proposal replaces the plan before approval, or a 👎 meal is suggested.

**How meals are ranked** (strongest signal first; weights live in `app/domain/suggest.py`):

1. Hearted and marked cooked.
2. Marked To try.
3. A thumbs-up (Taste Lab or the plan), or a heart on a meal not yet cooked.
4. Part of a Taste Lab plan the household approved.

A pass or 👎 drops the meal. One to three liked meals can pull in others with similar
ingredients. Refusing a whole plan is a weaker signal than swapping one meal and approving the
rest. Diet and avoid filters are hard rules (see 5).

### 4. Your plan (This week)

This week's meals, scheduled on days or unscheduled. Grocery and prep follow this plan.

Family portions is the default serving count for recipes being browsed and meals newly
added or suggested. An explicit serving choice overrides it; meals already on the plan
keep their saved servings. Scaling uses the recipe's original yield, which is not rewritten
by this preference. Without a valid saved preference, use the recipe's own yield.

- **Must:** add, move, remove, or change servings on one meal without rebuilding the week.
  The slot keeps the same recipe id (this kitchen's overlay, if any).
- **Must:** unscheduled meals count toward groceries. Marking a meal cooked keeps it on the plan,
  faded, and moving it to another day keeps it cooked.
- **Must:** Edit mode handles servings, scheduling, selecting several meals (mark cooked or
  remove), and 👍/👎 per meal. 👍/👎 are hidden outside Edit mode. 👎 means never suggested again.
  iPhone selection sits on the right rather than occupying a column beside every photo.
  Schedule and voting share one row when they fit; servings use the next row. Narrow layouts
  and larger text stack controls, while vote explanations remain below the controls.
- **Must:** While editing, a visible **Done** sits in the plan header beside ⋯ (iPhone and
  website). Done leaves Edit mode and clears the selection; ⋯ → Finish editing does the same.
- **Must:** save the plan as a draft without replacing it. Starting a new plan moves the live
  week to history; nothing is deleted. Saved plans can be deleted, except the active plan.
  Each saved row shows its name (or "Week of …"), dates, meal count, status, first meals and
  when it was saved; delete is a visible button, not swipe-only.
- **Must not:** clone a catalog recipe because it was added to a day; blow away the rest of the
  week to change one day; mix last week's meals into this one.
- **Bug if:** removing a meal leaves its ingredients on the grocery list; moving a meal drops
  cooked; two slots of the same recipe show as two grocery lines.

### 5. Recipes

**Browse.** Always its own tab; never locked behind starting a plan. Rows (Suggestions,
favorites, To try, popular, and so on) are a daily shuffle; the full All recipes list is A–Z.
Hearts, To try, and hides belong to this kitchen.

- **Must:** search the name this kitchen sees (its renamed title, if any). Heart and To try never
  copy the recipe. Hide removes a recipe from browse, search, and suggestions; a hidden recipe
  already on the plan stays there. Add to plan keeps you on the recipe.
- **Must:** "Uses pantry" keeps recipes with two or more ingredients you have (or one that's at
  least 40% of a short list). Never-shop staples don't count. Same rule on iOS and the web.
- **Bug if:** heart, hide, or To try creates a copy; hide removes the recipe for everyone.

**Diet, allergy, and avoid filters** (Settings → Filters, the tour, and Taste Lab).

- **Must:** one filter system. All three screens read and write the household's
  `prefs.filters` (diets, allergens, avoids, time); each sends only the keys it shows and the
  server merges, so the tour can't wipe allergies. Taste Lab's old per-person filters were folded
  into the household's once and no longer apply on their own. Lists live in
  `app/domain/diet_filter.py`; a test keeps the web, iOS, and Taste Lab copies equal.
- **Must:** pick one of omnivore, pescatarian, vegetarian, or vegan; gluten-free and dairy-free
  add on. Allergies: soy, peanut, tree nuts, dairy, egg, gluten, sesame, fish, shellfish, Other,
  or None. Avoids: Taste Lab's full list plus spicy, Other, or None.
- **Must:** diets and avoids hide recipes in Recipes *and* in suggestions, matching the name and
  ingredients (including this kitchen's edits). Plant-based items such as peanut butter, coconut
  milk, or "vegan sausage" don't count as dairy or meat. Recipes this kitchen wrote always show.
  Cook time only steers suggestions.
- **Bug if:** a vegan kitchen sees meat, fish, eggs, or dairy in Recipes, or a filter set in Taste
  Lab doesn't show in Settings (or the other way round).

**Recipe page and Cook mode.** Overview is the photo and full ingredient list; Cook is numbered
steps. Both show this kitchen's overlay when there is one.

Recipe detail add controls reflect membership in the current plan: already included recipes
show "Remove from this plan". Successful adds/removals show a brief confirmation popup.
On iPhone the toolbar plus becomes a minus,
with a matching VoiceOver label; the add action is beside the heart rather than in the ⋯ menu.
Hide and To try remain available for recipes on the plan.

- **Must:** keep line breaks and `- ` bullets in a step; `Heading:` reads as a label. Show the
  amounts for each step under it. Show a Prep chip on tagged steps. Inline timers are disabled
  on iPhone and web: opening Cook does not parse durations or create countdown controls.
  Timer code is retained for a far-future revisit after performance and usability review.
- **Must not:** write the catalog because Cook was opened or Prep was toggled.

**Editing recipes.** Save edits in place for this kitchen (same id). Copy is opt-in. Restore is
available once an overlay exists. Editing covers name, servings, minutes, ingredients, each
step, and that step's amounts. Kitchen-owned recipes save to their own row.

- **Bug if:** after Save the recipe id changes, the catalog row changes, or Restore creates a
  third recipe; a later catalog publish silently deletes overlays.

### 6. Grocery list

Built from this plan's meals: one line per item, amounts combined, checked off in the store.

- **Must:** merge the same item (lime/limes, hyphen/space, aliases). Sum amounts and show which
  meals use each line. Keep pantry items on the list, marked owned. Keep never-shop staples
  (salt, oil) on the list and checked. Keep leading numbers in names (`2% milk`).
- **Must:** custom lines ("paper towels") never become catalog ingredients. Typeahead uses the
  grocery catalog only; Add item shows the single best match. Check marks survive a rebuild.
- **Must:** each item can be given a store and an aisle, and the choice is remembered. Aisles can
  be renamed, numbered, and reordered. The list can be filtered by store.
- **Must:** completed items can be shown or hidden from the bottom of the list. "You'll use
  this in…" lists only meals on the current plan. Using a substitute keeps the item page open.
- **Must:** share, email, or print what's left to buy, grouped by aisle, for the selected store.
- **Bug if:** a rebuild duplicates lines or drops amounts; black pepper is filed as produce.

### 7. My kitchen

Pantry, staples, substitutions, stores and aisles, and family portions, all reachable from More
→ My kitchen (not buried in Settings).

- **Must:** "Have this item" marks grocery lines owned; amounts are optional. Always-checked
  staples are a short list, not a second inventory.
- **Must:** a substitution (bone-in thighs → boneless) renames the grocery line for this kitchen
  only and can be removed; the catalog recipe stays as written.
- **Bug if:** checking "have" deletes the grocery line; a substitution renames the catalog
  ingredient.

### 8. Weekend prep

Chop, mix, and portion once for this plan's meals; cook fresh later. Not "cook Sunday, reheat
all week."

- **Must:** build from this plan only. A recipe with steps tagged Prep uses only those. Otherwise
  the app picks make-ahead sentences (knife work, grating, sauces, marinades), never anything that
  needs heat or happens at serving.
- **Must:** group by what's being prepped across meals (one potatoes row for two meals), or by a
  step's heading ("Make the tzatziki: …" → "Make tzatziki"). A dressing with no name stays with
  its own meal.
- **Must:** the screen is grouped into sections by what the food is: Vegetables; Aromatics, herbs
  & citrus; Protein; Cheese & dairy; Sauces & dressings; More prep. One row per item however many
  meals use it; never one row per meal. Sections collapse with an arrow and remember it.
- **Must:** a row is named for what the steps say to do, with the amount under it:
  "Peel and mince garlic · 14 cloves garlic", "Wash and thinly slice mushrooms". When meals cut it
  differently, the most common way wins. Opening a row shows each different step once, with the
  meals that use it as small links under it. No grey "For meal, meal" line.
- **Must:** a progress ring (done of total) and one bar per section at the top; tapping a bar
  jumps to that section.
- **Must:** check-off works like the grocery list: a done item leaves its section; "Show
  completed" brings done items back, faded, at the bottom of their section. Checking an item
  shows a bar with Undo and "Worth prepping ahead next time?" 👍/👎.
- **Must:** every item has 👍/👎 whether it's checked or not. 👎 asks why: better done day-of,
  didn't keep well, too small to bother, prep it differently, not a prep step. Votes and reasons
  are saved for review only (GET /dev/prep-feedback); they don't change what Prep shows yet.
  Tapping an item's name shows each meal's step and a link to the recipe.
- **Must not:** include last week's meals, leftovers, or "wash your hands"-type steps.
- **Bug if:** a recipe not on this plan appears; tagging Prep copies the recipe or edits the
  catalog.

### 9. Account and household

An invite link adds another account to the same household (plan, grocery list, pantry). A member
can be removed from Account & security, which ends their access. Password change, sign out, and
sign out everywhere live there too.

### 10. Across the whole app (UI principles)

- Phone-first; the website is the same app in a wider layout. Plan and Grocery are the daily
  screens; Recipes is always one tap away.
- Show amounts wherever groceries matter. Don't bury the pantry, editing, or filters.
- Photos: ours or the user's only, never Mealime's. A catalog recipe is listed only once its
  steps are rewritten and it has a photo we may use (`data/recipe_photos.json`).
  A photo made with AI (`"ai_generated": true`, or a file named `…_ai-generated.png`) gets a
  purple ★ tip on the recipe page saying so.
  A photo taken for a different recipe (its entry's `recipe_id` isn't this recipe's archive id,
  or `"shared_photo": true` with no `recipe_id`) gets a ★ tip saying it's from a similar recipe.
- Works at the largest text sizes: rows wrap or stack instead of breaking words; section headers
  stop pinning; menus and grids grow or drop to one column; nothing hides behind the tab bar.
- Never show state by color alone.
- Help text that explains a feature is a *tip* (purple ★), marked with `data-tip="<area>.<name>"`
  so `scripts/list_tips.py` can list them. Draw new tips with `StarTip(id:)` on iPhone and
  `<Tip id>` on the website: a purple ★ on the pale aubergine tint.
- Don't add menu items, tabs, or other navigation without an explicit product decision.
- Errors are in plain words, on the screen they belong to, and say how to recover.
- An `/api` request no route takes gets JSON (404 `not_found`, or 405 `method_not_allowed` with
  `allowed`) and a server log line naming the app build (`X-Dinnerdesk-App`), so a server/app
  version mismatch can be found from the log.
  Unavailable actions offer retry/support guidance rather than HTTP codes or instructions
  for the user to update the server. iPhone logs rejected request methods and paths for
  diagnosis, without logging request bodies or query values.

---

## Screens and flows

| Screen | Job |
|---|---|
| **Plan** (This week) | This week's meals; suggestions arrive as a proposal to review. |
| **Recipes** | Browse and search any time; open a recipe; add it to the plan. |
| **Grocery** | Built from the plan; check off in the store. |
| **Prep** | Make-ahead work combined across meals. A tab on larger phones, always under More. |
| **More** | My kitchen, Taste Lab, Settings, Account. |
| **Taste Lab** | Teach the app this household's tastes. |

**Main flow:** Recipes or Suggest meals → review and approve → schedule on days → grocery list
builds → shop → prep → cook.

**Not built yet:** template dinners (pick format, protein, base, sauce → generate a recipe) and
"make this a meal" (attach sides to any recipe). See [`TODO.md`](TODO.md) → Ideas.

---

## Architecture

### Stack

| Layer | Choice | Why |
|---|---|---|
| Phone app | Native iOS (SwiftUI) in `ios/` | The main app. Not a web wrapper. |
| Website | React (Vite) in `web/` | Same API; the wide layout. |
| API | Python FastAPI in `app/` | Matches the archive tooling; simple CRUD. |
| Database | PostgreSQL on Railway (`DATABASE_URL` required) | One managed database; no file fallback. |
| Auth | Email + password, session cookie, household invites | Guest household only when sign-in isn't required. |
| Email | Resend (password reset) | |
| Taste Lab site | `tastelab/` | Data-collection site, also served at `/tastelab`. |

### Data

- `data/` is the **archive**: a readable JSON snapshot of the recipe library, not the app's
  database. Import scripts load it into PostgreSQL.
- The live schema is `app/db/schema.sql`. `init_db` creates tables and adds missing columns
  on startup, so schema changes take effect on server restart.
- Beyond recipes, plans, grocery, pantry, and prep, the database holds: favorites, To try,
  hides, recipe overlays, substitutions, users, sessions, invites, password resets, remembered
  store/aisle per item (`grocery_places`), meal 👍/👎 (`household_meal_ratings`), prep step
  votes (`prep_step_feedback`), prep check-offs, and Taste Lab sessions, people, and events.
- Ingredient photos live outside Git (`GROCERY_PHOTO_DIR`); the repo holds only the name mapping.

### Code map

```
dinnerdesk/
  README.md              setup and running
  docs/                  DESIGN (this file), TODO, TESTER_CHECKLIST, PRIVACY,
                         reference notes, and screenshot folders ("… to do")
  app/                   FastAPI: routes.py, auth_routes.py, taste_lab.py
    db/                  schema.sql, database.py (init_db), seed.py, catalog.py
    domain/              pure logic: grocery, suggest, taste_rank, prep, search,
                         diet_filter, categories, …
  ios/                   SwiftUI app
  web/src/               React app (pages/, api.js)
  tastelab/              Taste Lab site
  data/                  recipe archive (JSON), templates, photo allow-list
  food/                  our recipe photos
  tests/                 pytest; database tests need TEST_DATABASE_URL
  scripts/               imports, tips list, one-off fixes
```

Domain code in `app/domain/` does no I/O, so it can be unit tested without a database.

### API

Routes live in `app/routes.py`, `app/auth_routes.py`, and `app/taste_lab.py`, all under
`/api`. The interactive API docs are turned off on the server. Errors are JSON
`{error, detail}`.

Unknown API paths return 404; unsupported methods on known paths return 405 with the
allowed methods. Diagnostics inspect included API routers as well as direct app routes,
exclude the website fallback, and log the requesting app build without crashing.

### Outside services

Build it ourselves by default, and prefer data tables we own (ingredients, nutrients, package
sizes) over live calls. Outside services only when a feature needs one: USDA FoodData Central for
nutrients, retailer programs for shop-my-list (notes in [grocery shopping research](TODO.md#grocery-shopping-research)),
HealthKit for nutrition sync.

---

## Decisions

- Native iOS and the website both ship; iOS is SwiftUI.
- Accounts are optional; guests have separate kitchens and a nonblocking data-loss warning.
- Suggestions are a proposal to approve, never an automatic replacement of the plan.
- Suggestion review prioritizes meal choices and decisions; explanatory copy is saved for tips.
- Diets and avoids are hard filters everywhere (Recipes and suggestions).
- Prep check marks follow the meal and step, so they survive regrouping.
- Template rules are still open: families are JSON lists of recipes, not a slot generator.

**Reference notes:** [grocery shopping research](TODO.md#grocery-shopping-research) (grocery retailer programs) · [`PRIVACY.md`](PRIVACY.md).

Plan removal confirms the selected meal count with singular/plural wording. On iPhone,
accessibility text sizes open a full-height, scrolling confirmation with reachable Cancel.

Suggested-plan review omits explanation text following the October 9 layout review.
Approved plans also omit suggestion commentary and internal decision/swap counts.

Embedded Taste Lab uses the host screen’s Taste Lab title and suppresses repeated branding;
inner headings still name the current step and Back still navigates within Taste Lab.

Taste Lab suggested meal names and swap headings wrap to their full length; cards grow
with the title and decision controls remain in the scrolling flow.

Taste Lab exhausted results use a prominent recovery panel explaining filters/passes and
linking to Edit filters; saved allergies and passes remain intact.

The iPhone recipe options control opens the shared scrolling menu sheet, with a 44-point
tap target, so long labels and accessibility text sizes remain reachable.

Grocery detail shows an ingredient photo only when available; missing/failed photos leave
no empty photo box. Individual food assets are supplied through GROCERY_PHOTO_DIR.

Substitution names move to stacked rows when the horizontal layout cannot fit; full
ingredient words remain readable at accessibility sizes.


### Screenshot review — October 9, 2026

- Custom allergies and avoids use ingredient search and explicit selected-food rows on
  iPhone and web Settings. Search includes catalog foods and recipe ingredients belonging
  to the shared catalog or this household; every query word must match. Typing alone does
  not save a restriction. Existing custom choices remain removable, and selected food
  names are stored intact, including commas, in the shared filters.
- Recipes search uses the cream surface and line border rather than a system white field.
- Meal-removal confirmation uses 20-point title, 17-point body/actions (scaled for Dynamic
  Type), and a content-sized sheet at standard text sizes. Accessibility sizes retain the
  scrolling full-height sheet. Cancel remains reachable.
- Account & security shows the signed-in identity once, offers Reset password by email,
  and lets the household name be edited. Other household members remain manageable;
  the current user's duplicate member row is omitted. Reset email is sent only on tapping
  the action, never just by visiting the screen.

### Recipe instruction attribution and suggestion review (Oct 9)

Recipes with existing Dinnerdesk-authored rewrite provenance, show “Instructions customized by Dinnerdesk” above Cook steps on iPhone and web. The importer retains the original rewrite source. This editorial label does not indicate kitchen testing. Private recipe revisions and original backups stay outside Git; publishing them requires the explicit catalog import.

Suggestion review uses one navigation heading, photo-corner circular swap buttons with recipe-specific accessibility labels, and adjacent approve/suggest-another actions where space permits. All food photos use shared square components with center-cropped fill across iOS, web, and Taste Lab. Photo shape stays square at every meal count and text size. Very short screens, additional meals, and accessibility text can scroll. Clients derive the visible note directly from existing `instructions_source` and `instructions_copied_from_third_party` provenance; there is no additional customization flag in the catalog or API. Improve suggestions is below the actions. The current-plan explanation is retained as a hidden `plan.proposal-keeps-current` tip on web.

Selected tabs use bold labels on iPhone and bold underlined labels on web, with aria-current
on web links. Selection remains visible without relying on accent color.

Plan ⋯ omits Review pending suggestions and Choose my own meals. New meal plan requests
four suggestions; Recipes remains the entry point for adding individual meals. Loading a
saved proposal must not open the review sheet automatically. A “Review saved suggestions”
button on the main Plan screen opens it explicitly; closing review preserves the proposal.

Prep completion uses PUT /prep/{id}/steps and task JSON as its sole store. Startup migrates
legacy per-step checks into task JSON before dropping the old table; completion follows
step identities when tasks regroup. Deploy API and app together: the duplicate PATCH step
endpoint is retired.

Plan list rows show full wrapping titles and a Schedule button outside editing. iPhone
photos retain their 160-point size; accessibility sizes stack the title/controls below the
photo rather than shrinking it. Web list thumbnails retain their existing dimensions.

Declining replaces the proposal in place: the review stays open and current plan/groceries
are not reloaded. A failed replacement leaves a retry action; the declined plan cannot be
approved or modified again.

The grocery “You’ll use this in…” heading uses the full content width and a secondary
heading font, wrapping naturally only when needed at large text sizes.

Selecting any primary tab returns to its main page and resets local navigation/search
state, whether switching from another tab or tapping the selected tab again. On iPhone,
reset the destination before selecting it; tab-bar taps and in-app tab links share this
behavior. For example, Grocery → garlic → Plan → Grocery must show the grocery list.
Saved data and the current meal plan remain intact. On web, primary navigation remounts
the destination screen without reloading the page.

Suggestion review shares Taste Lab’s bordered cards, coral swap badges, and aubergine approval styling. Integration of #31 preserves the later compact heading, square photo layout, circular swap controls, and declined-proposal retry state.

Screenshot follow-up: adding a fifth or later suggested meal keeps the four-meal photo
height calculation, with scrolling for extra rows. The replacement picker uses the cream
page background, rounded photos, dark meal names, and a visible search field. Empty
replacement results and filter-related plan errors link directly to Filters. Empty plans
group New meal plan and Add meals together in the center.

Odd-issue integration (October 9): pantry search supports keyboard selection and a clear control; the tab highlight stays within the system bar while selected labels retain bold type. Quick-start tour steps include screen illustrations. Guest Taste Lab answers persist by browser identity. Prep task names derive from recipe content. AI photo metadata controls a purple-star tip independently of instruction provenance.
