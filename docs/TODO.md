# Dinnerdesk to-do

The working list: issues, fixes, ideas, and open questions. Implementation checkboxes live here; tester checks live in `TESTER_CHECKLIST.md`. How things are *supposed* to work is in [`DESIGN.md`](DESIGN.md).

**How to use it**

- Jot new issues in **Inbox** in any wording. Add the screenshot to the matching
  `docs/<area> to do/` folder and put its path on the line.
- Moving an item from Inbox to **Now** means it's clear and ready to work on. Add who has it:
  *(Claude)*, *(Codex)*, or *(you)*.
- When it's done, tick it and move it to **Done**. Trim Done now and then; Git keeps history.
- When a feature's behavior changes, update [`DESIGN.md`](DESIGN.md) and
  [`TESTER_CHECKLIST.md`](TESTER_CHECKLIST.md) in the same commit.

---

## Inbox

- Annotated screenshot review (Oct 9), branch `codex/annotated-screenshot-fixes`:
  fixed automatic suggestion presentation at launch, photo growth above four meals,
  replacement-picker styling, direct filter recovery links, and empty-plan action alignment.
  Remaining screenshot work, after checking existing implementations:
  - Compact Account & security; simplify household naming/invite layout.
  - Add breathing room to Taste Lab's returning-user screen; reconcile its cards/actions
    with the preferred earlier simple suggestion layout.
  - Verify generic ingredient photo configuration (the private gallery already has garlic).
  - Diagnose custom-food search failures and add clear saved/saving feedback; use filter chips.
  - Make family portions the default when browsing recipes and adding new meals.
  - Issue #36 follow-up (`codex/issue-36-tab-return-root`): destination reset now runs for
    every tab selection, including Grocery ingredient details. Verify across all tabs.
  - Move edit selection to the right and arrange Schedule/votes/servings into compact rows.
  - Decide whether Build from scratch opens Recipes or creates an empty plan.
  Sources: annotated PNGs in `docs/`, `my kitchen to do/`, `groceries page to do/`, and
  `suggestion meal plan to do/`. Keep these private screenshots out of Git.

- [ ] Taste Lab: when everything is rejected, the recovery message is easy to miss (plain font,
      looked like a glitch). Make it stand out. *(from your tester checklist notes)*
- [x] Use a purple ★ tip to tell users when a recipe photo is AI-generated (and, once
      `shared_photo` exists, when it's borrowed from a similar recipe). Needs a way to mark
      AI photos in `data/recipe_photos.json`, e.g. `"ai_generated": true`.
- [ ] Recipe ⋯ menu only flashes when tapped; may be large text only.
      `docs/when elips on recipes is clicked it only flashes may be an issue onyl in large font.png`
- [ ] *(Later)* Review how the More tab is nested: Weekend prep, My kitchen (portions, pantry,
      always checked off, substitutions, stores & aisles), Taste Lab, Hidden recipes, Quick start
      tour, Settings, web, Twitter. Decide what belongs together and what's one tap too deep.

## Now

### Broken or urgent

- [ ] Plan ⋯: remove "Review pending suggestions" and "Choose my own meals". They were added
      without being asked for.
- [x] Settings filters and Taste Lab filters are two separate systems. With Settings almost
      empty, suggestions still failed ("No matching suggestions") because of Taste Lab's filters.
      Make them one system, and make Settings → What to eat match or exceed Taste Lab (allergies,
      the full avoid list, Other).
      `docs/quick start to do/tastelab filters and settings filters seem to be seperate bc i have settings filters set to basically nothign.png`
      `docs/quick start to do/filters screen in settings is lacking basically everything it should math or exceed tastelab filters system.png`
- [ ] Raw error text on screen: "HTTP 405 Method Not Allowed" on This week. Errors should be in
      plain words, on the screen they belong to, with how to recover.
      `docs/suggestion meal plan to do/no easy done editing button.png`
- [ ] Recipe page ⋯ offers "Add to this plan" for a meal that's already on the plan.
      `docs/recipes page to do/this meal is already in a plan.png`
- [x] Taste Lab keeps asking about meals already answered (cheesy broccoli and rice always comes
      first). A skipped meal may come back; a liked or passed one shouldn't.
- [ ] Prep check-off: two routes (PUT and PATCH `/prep/{id}/steps`) and two iPhone functions do
      the same job, and the old `prep_step_done` table is left over. Keep one of each.
- [x] Prep task names from real recipes are sometimes wrong: "Whisk garlic", "Prep off roots",
      "Grate on holes grater". *(Claude)*

### Plan and suggestions

- [ ] No obvious Done control when editing the plan.
      `docs/suggestion meal plan to do/no easy done editing button.png`
- [x] Edit mode at large text: "Select all / 0 selected" and "Mark cooked / Remove" break
      mid-word; "4 servin…" is cut off; − and + spill outside their box.
      `docs/accessibility to do/Screenshot 2026-10-07 at 7.45.56 PM.png`
- [ ] Remove dialog says "Remove 1 meals?", and Cancel is cut off at the bottom.
      `docs/suggestion meal plan to do/accessiblity remove one meal cut off.png`
- [x] "Won't be suggested again" should be a purple ★ tip.
      `docs/suggestion meal plan to do/move wont be suggested again to a purple stary tip and fix the over flow of -+ .png`
- [ ] Bring back the one-line "why these meals" summary; it was removed along with the per-meal
      commentary. Approving still writes "N meals · Approved · N swaps" into the plan; the plan
      should look the same whether meals were suggested or chosen.
      `docs/weekend prep to do/removed excess commentary but also removed the summary of why its a good plan.png`
- [x] Saved plans and history: every row is "This week", dates repeat, and "History · 0 swaps"
      means nothing to users. Clearer rows, accessible delete, empty states.
      `docs/suggestion meal plan to do/history 0 swaps is data for us the user doesn't care.png`
      `docs/suggestion meal plan to do/saved and draft plans formatting.png`
- [ ] Plan list view: room for a Schedule button and more of the recipe name, without shrinking
      the photo.
- [x] Suggested plans should look like Taste Lab's suggested plans.
- [ ] Declining a suggested plan shouldn't reload the whole page.

### Taste Lab

- [ ] Double header on every Taste Lab screen: the top bar says "Taste Lab" and a second
      "← Taste Lab" sits below it. `docs/quick start to do/Screenshot 2026-10-07 at 6.21.50 PM.png`
- [ ] Filters should fit on one iPhone 16 screen at standard text, without dropping options.
      `docs/quick start to do/taste lab filters should fit on one screen from an iphone 16 with standard font size. do not remove options but do consider layout/formatting..png`
- [ ] Meal names are cut at two lines when there's room for more.
      `docs/quick start to do/tastelab meal names don't need to cut off at two lines assuming they don't spill over the actual phone screen size.png`
- [x] Show more plans before "You're set".
      `docs/quick start to do/tastelab should be showing more mealplan suggestions before youre set.png`

### Recipes

- [x] Use "See all" or an arrow for section links, not both.
      `docs/recipes page to do/choose either see all or arrow not both.png`
- [ ] Browse cards break names mid-word at large text. A fix is on main; check it on a fresh
      build. Same screenshot as above.

### Grocery

- [x] The "Pantry" note under an item should be a purple ★ tip. Aisle headers (PANTRY) should
      stay smaller than item names at large text.
      `docs/groceries page to do/add a purple stary tip to the _pantry_ note and resize aisle terms to remain smaller than title.png`
- [ ] Item page shows an empty box where the ingredient photo goes.
      `docs/groceries page to do/get images of individual foods.png`
- [ ] "You'll use this in…" wraps too early at large text.

### My kitchen

- [x] Add-to-pantry search has two X buttons, and the keyboard can't move through results
      (tab, arrow up/down).
      `docs/my kitchen to do/add to pantry search has two x_s and doesn't allow tab arrow down up select.png`
      `docs/accessibility to do/Screenshot 2026-10-07 at 7.57.09 PM.png`
- [ ] Substitutions: names break mid-word at large text ("coconu t oil").
      `docs/accessibility to do/access your subs formatting issues.png`

### Weekend prep

- [x] Redesign the Prep screen ("this design is awful"): sections by food type, ring + section
      bars, collapsible sections, grocery-style check-off, 👍/👎 with reasons on every item. #21

### Whole app

- [ ] The current tab is shown by color only (the filled-icon fix was reverted).
      `docs/accessibility to do/color only representation of current page.png`
- [x] The selected-tab highlight spills past the tab bar and clips the Grocery badge.
      `docs/accessibility to do/bottom nav highlight overlow when selected.png`
- [ ] Large-text pass on Pantry, the recipe page, Cook, Prep, and Settings (needs a device).
- [ ] Opening a tab again should show that tab's main page.

### Quick start tour

- [ ] Decide the order. Notes so far: start by showing suggestions, then groceries; end with
      Taste Lab; explain the purple ★ tips and that they fade after the first few uses.
      `docs/quick start to do/quick start to do .txt`
- [x] Tour cards are blank below the text; each needs a picture of its screen.
      `docs/quick start to do/need screenshot of recipes page.png`

### Checks before a release *(Codex)*

- [ ] Walk the suggestion flow: four meals, resize, swap, decline, approve, pending plan.
- [ ] Layouts: small screens, larger text, long names, menus, confirmation sheets.
- [ ] Refusals, swaps, later approvals, and dislikes change suggestions differently.
- [ ] Release checklist: server and app compatibility, regressions, remaining manual checks.

---

## Decisions needed

- [ ] **Category likes and dislikes** (curry, Mexican, comfort classics…). What does a dislike do:
      hide everywhere, or only stop suggesting? What does a like do: rank higher, a "More …" row
      in Recipes, or both? Is the category list right? Groundwork: `app/domain/categories.py`.
- [ ] **Sample week for guests.** Meals picked so far: Sesame Chicken & Broccoli, Chicken Kebabs
      with Tzatziki, Italian Stuffed Zucchini Boats (beef), Tomato Mushroom & Olive Penne (quick),
      Dijon Pork Chops (quick). Still to decide: who gets it (the guest household, new accounts,
      or both), whether it's labeled "Sample week" until they make their own plan, and whether
      pork counts as the red meat (or swap the zucchini boats for tuna penne).
- [x] **Prep screen redesign** (see Weekend prep above).

---

## Ideas (not started)

Roughly most useful first within each group. Not a roadmap.

**Planning and suggestions**
- [ ] Scroll several suggested plans; add one meal from a plan the way the recipe carousel does.
- [ ] While building a plan from scratch, show the meals already in it (a small strip with a
      clear close). Brainstorm the layout first.
- [ ] Finishing a plan built from scratch opens a review page like plan editing.
- [ ] Review and edit Taste Lab swipe history.
- [ ] Taste Lab question: "How would you describe your tastes and preferences?"
- [ ] Rate a meal with stars and optional feedback after it's checked off.
- [ ] Suggest a menu from what's in the pantry; reverse search (fridge ingredients → recipes).
- [ ] Smart plan tunable by budget, pantry use, diet, cook time, leftovers, package use-up;
      prefer ~10–30 minute meals.
- [ ] Reusable menus / favorites rotation (pin go-to meals).
- [ ] Drag meals onto days (scheduling is a date picker today).
- [ ] On the plan, a small carousel for adding a meal (today, Add meals opens Recipes).
- [ ] Turn on swapping recipes for low-carb versions (cheesy broccoli chicken without the rice).
- [ ] More diets and allergies (keto / low-carb, Whole30, AIP, a longer allergy list).

**Recipes and cooking**
- [ ] Attach sides or components to any meal; "customize this meal" (protein, salad, bread,
      sides; groceries merge).
- [ ] Gather near-identical sides, sauces, and salads across recipes into shared components (one
      grocery line, one batch of prep).
- [ ] Short-order templates (pick format → protein / base / veg / sauce → generate a recipe);
      save builds as user recipes; template photo from the nearest sibling. Sheet pan family; pot
      roast as a template candidate.
- [ ] Templates may suggest defaults (quesadilla → offer pico) but never lock choices.
- [ ] Instruction detail: basic vs detailed.
- [ ] Import from a URL (and report bad imports); crawl bookmarked links; TikTok, Instagram, PDF,
      or photo import.
- [ ] Brand-agnostic box mixes and premade sides ("boxed mac & cheese" + milk/butter).
- [ ] Leftover and waste-minimizing tags.
- [ ] Print recipes and event sheets.
- [ ] General cooking education.

**Grocery and prep**
- [ ] Shop-my-list / online order hooks (Instacart, Walmart, Kroger, Amazon). Notes in
      [grocery shopping research](#grocery-shopping-research).
- [ ] Package-aligned scaling (prefer ½ / 1 / 2× retail packs) and a standard package-size table.
- [ ] Cross-meal perishable planning ("night 3 finishes the bag"); expiry dates → cook-soon
      suggestions.
- [ ] Drag a prep task to another day; tell batch leftovers apart from ingredient prep.
- [ ] Cost estimates (estimated vs entered).

**Nutrition and health**
- [ ] Nutrient labels from ingredients and amounts; per-meal macros before you commit.
- [ ] Personal calorie and macro targets; recipes matched to targets; macro gap fill ("need ~30g
      protein").
- [ ] Household portions with per-person macros and preferences; spicy vs mild, veg vs meat on
      one plan.
- [ ] Log one serving to Apple Health when a meal is checked off (Health Connect on Android);
      direct tracker APIs only where a partner deal exists. Settings shows this as coming soon.
- [ ] Fitness goals and a simple intake forecast; light progress tracking (not a food diary).
- [ ] Optional MyPlate / FoodData Central live APIs (no bulk mirror without a license).

**People and sharing**
- [ ] Partner / family sync; optional Calendar or Keep.
- [ ] Reviews, comments, and other cooks' photos on the recipe page (Settings → Social switches
      already exist). User-submitted photos; share customizations.
- [ ] Event planner: date, guests, occasion, catering portions, mains and many sides, a separate
      grocery list, a prep timeline, sharing with co-hosts; seasonal plan packs.
- [ ] First-launch note about recipe photos (once per account, needs a "seen" flag). Draft:
      > We're new, and we're building this app as we use and test it in our own lives. The
      > recipes here are gathered and customized from reliable sources, but we don't own the
      > rights to photos of the actual dishes. Until we've double-checked each recipe and
      > photographed it ourselves, some recipes use generic or AI-generated photos. You can help
      > by reviewing recipes you try, sharing your own photos, and liking or disliking photos and
      > reviews other people submit. If you submit a photo, it may be used as that recipe's
      > featured photo.

**Business**
- [ ] Fair free tier; pay for storage and sync costs. Trial or money-back option.
- [ ] Sync or export with other apps (e.g. Umami).
- [ ] Offline browse (plan, recipes, grocery).

**Recipe library (operator)**
- [ ] Review and normalize archive ingredient names into a canonical list (Settings → Ingredient
      review; first pass in `data/ingredients_review.json`). Don't auto-merge bone-in and
      boneless.
- [ ] Third-party instruction review workflow (`instructions_copied_from_third_party`,
      `instructions_reviewed`).
- [ ] Upload app-only favorites (not on mealime.com; tag `favorite` + `incomplete`): BLT salad
      with chicken and avocado; brussels sprouts mashed potato and sausage bowl; buffalo shrimp
      tacos with creamy napa; cauliflower chickpea salad with arugula and pine nuts; chicken
      zucchini meatballs with rice, cucumber, tomato; coconut chicken tenders with Thai sauce;
      creamy Tuscan soup with potatoes, pork, kale (zuppa toscana); grilled peri peri chicken
      thighs with pickled cucumber; lemony chicken piccata with asparagus; pan-fried pork chop with
      green onion butter and cheesy roasted asparagus; penne with basil cottage cheese sauce,
      spinach, tomatoes; steak and potatoes with romaine and creamy Dijon; sticky maple Dijon wings
      with Caesar salad.
- [ ] Finish stub recipes tagged `american_standard` or `side` (write them, or use only a clear
      Mealime match).
- [ ] Mealime / MyPlate / Allrecipes bulk scrape. Don't run until go-ahead.
- [ ] Pro Mealime sync if an auth token appears.

---

## Pending proposals

These remain design choices, not implemented features.

### Proposed quick start order — issue #24

Awaiting the user's choice before changing the tour.

After welcome and household filters, show:

1. Suggestions: start with four meals matched to the household.
2. Review and approve: swap meals; the current plan stays until approval.
3. Grocery: combined amounts and pantry items.
4. Weekend prep: prepare shared ingredients ahead.
5. Recipes: browse and add your own meals; explain purple ★ help tips.
6. Taste Lab: likes and passes improve future suggestions, with an optional entry button.

Keep Skip available throughout, and offer Start planning as well as the optional Taste Lab
entry at the end. Use the same order/copy on iPhone and web.

The existing notes ask for tips to fade after the first few uses. No tip-visit tracking is
currently implemented, so the tour must not promise automatic fading until that behavior
is built. Screenshot content is tracked separately in issue #25.

### Category preference proposal — issue #38

Awaiting the user's choice before adding category preferences.

Proposed behavior:

- Dislike stops suggesting a category while leaving its recipes browsable.
- Like boosts the category in suggestions; it does not guarantee a meal on every plan.
- Neutral has no effect. Each category has one state: Like, Neutral, or Dislike.
- Allergies and dietary filters always take priority over category likes.
- If a recipe belongs to several categories, a dislike takes priority over a like.
- Store choices in household preferences, shared by Settings and Taste Lab.
- Do not add a new Recipes carousel until separately requested.

Existing category labels for review: Curry & Indian; Mexican & Tex-Mex; Asian stir-fries &
noodles; Italian & pasta; Mediterranean; Comfort classics; Healthy & light; Soups & stews.

Alternative: disliked categories also disappear from browsing. This makes it harder to find
an occasional exception and needs a clear explanation/reset control before implementing.

Implementation after approval: add persisted tri-state choices, apply the ranker rules,
share controls on app/web, and verify overlapping categories and allergy precedence with tests.

### More navigation proposal — issue #40

Awaiting the user's choice before reorganizing navigation.

Keep these daily tools one tap from More:

- Weekend prep
- My kitchen (Family portions, Pantry, Always checked off, Substitutions, Stores & aisles)
- Taste Lab
- Hidden recipes

Group separately:

- Preferences & account: Settings (Filters, Account & security, Privacy).
- Help & links: Quick start tour, Dinnerdesk on the web, Twitter.

Use the same group labels/order on iPhone and web, and keep all existing destinations.
No additional nested screen is needed. My kitchen remains one hub rather than spreading
its five tools across More. Taste Lab remains one tap away.

Review points: whether Hidden recipes belongs with daily tools or preferences; whether
Twitter should remain in the app; whether Weekend prep still needs both its tab and More
entry on phones that have space for the Prep tab.

---

## Far future

- [ ] Inline Cook-mode timers on iPhone and web. Commented out October 9 after a Cook-tab crash and reported slowness. Revisit only after measuring rendering performance and deciding how timers should be presented. Retained parser code and its regression test are groundwork, not an active feature.

## Done (recent)

Older history is in Git and in [`DESIGN.md`](DESIGN.md), which describes everything that ships.

**Oct 7–8, 2026**
- [x] Plan Edit mode has a visible Done in the header on iPhone (it was only in the ⋯ menu). #3
- [x] Suggestions arrive as a proposal: review, swap (with search), approve or decline; keep your
      own picks; reopen a pending proposal. Suggestions row in Recipes.
- [x] Taste Lab: "Not for us" shows a new plan; More options when swapping; None and Fish in
      filters; decision buttons no longer cover names.
- [x] Diets are pick-one; diets and avoids hide recipes in Recipes as well as suggestions; Fish and
      None in Settings and the tour.
- [x] Prep combined across meals by what's prepped; check off each item; folding hides details.
- [x] Grocery: share or email the list; show/hide completed from the list; simpler Add item;
      clearer menu names. "You'll use this in" shows only meals on this plan; substitutions keep
      the item open.
- [x] "Uses pantry" filter on iPhone; recipe categories (groundwork).
- [x] Large text: ⋯ menus grow and scroll; plan grid falls back to a list; section headers stop
      pinning and keep side margins; Family portions, Aisle order, store removal, grocery rows,
      recipe cards, ingredient row lines; consistent cream background.
- [x] Thumbs on the plan only in Edit mode; one summary line instead of commentary under every
      meal.


**October 9, 2026 — annotated screenshot fixes (visual verification pending)**
- [x] Custom allergies/avoids offer explicit ingredient search selections, preserving saved names.
- [x] Recipes search uses the app's warm surface color.
- [x] Removal confirmation has consistent typography and a compact standard-text sheet.
- [x] Account & security uses a reset action, editable household name, and one signed-in identity.


## Grocery shopping research

Historical application/research notes; verify availability and requirements before acting.

Track grocery conversions and earn commissions (Mealime-style). Register with the networks that run each retailer program. Related app goal: in-app shop-my-list in `TODO.md` → Ideas.

Instacart Developer Platform ([IDP](https://company.instacart.com/business/developers)) can send users to Instacart checkout and pay affiliate commissions, but **new applications are closed** (no waitlist). Recheck that page later.

### 1. Walmart Affiliate Program (via Impact.com)

Walmart partner/creator tracking runs through Impact.

- Applied for an **Impact.com publisher account** to access Walmart affiliate/API opportunities, but the application was **denied**.
- Created a **Walmart Affiliate account/application**, but it is **not approved yet**.
- Walmart approval may depend on having an approved Impact account, so this route is currently blocked/pending.
- Sign-up pages: [Walmart Affiliate Program](https://www.walmart.com/affiliate-program) and [Impact.com](https://impact.com/).
- Likely requirements: live domain, working prototype or wireframe, privacy policy (`PRIVACY.md`; also at `/privacy` in the app).
- If/when Impact approval becomes available: search **Walmart Retail Campaign** in the marketplace and apply.

### 2. Kroger Developer Account (direct API)

Kroger lets you sign up and test catalog / link-building APIs immediately.

- Sign up: [Kroger Developer Portal](https://developer.kroger.com/) (top right).
- Dashboard → **My Apps** → **Create New App** for Client ID and Client Secret.
- Use those credentials for product search in local development.

### 3. Albertsons Companies Partner Program (CJ Affiliate)

Albertsons (Safeway, Vons, Jewel-Osco, others) tracks affiliates through CJ.

- Sign up for a publisher account at [CJ.com](https://www.cj.com/).
- After the profile is verified: advertiser directory → **Albertsons Companies**.
- Apply as a meal-planning app that sends high-intent grocery buyers to their sites.

### Approval (app not fully live yet)

Networks often want a public URL before approving an app.

- Put up a one-page site (Carrd, Webflow, Squarespace): app name, logo, screenshots/mockups, brief description, privacy policy, and contact information. Use that as the website on applications.
- Having a functional public prototype may improve approval chances compared with applying while the app is still mostly in development.
- Application copy, e.g.: *We are building a utility meal-planning mobile application. We use an in-app WebView workflow to direct users to local grocery checkout screens to purchase recipe ingredients, generating high-volume, high-intent cart conversions for your retail banner.*


## Even issue implementation record — October 8, 2026

Historical record of the cumulative issue pass. These changes have since been integrated
into `main`; the listed local feature branches were deleted after verifying their ancestry.
The proposals remain unimplemented, and device/browser checks are in the tester checklist.

| Issue | Branch | Result |
|---|---|---|
| #4 | `codex/issue-4-recipe-plan-state` | Actual plan membership; add/remove controls and brief confirmation |
| #6 | `codex/issue-6-remove-dialog` | Singular/plural wording; full-height accessibility confirmation |
| #8 | `codex/issue-8-suggestion-summary` | Review explanation; no internal commentary on active plans |
| #10 | `codex/issue-10-taste-lab-header` | Suppress repeated Taste Lab branding when embedded |
| #12 | `codex/issue-12-taste-lab-names` | Full suggested names and swap headings |
| #14 | `codex/issue-14-taste-lab-recovery` | Prominent exhausted-results recovery panel |
| #16 | `codex/issue-16-recipe-menu` | Shared scrolling iPhone recipe options sheet; device reproduction still needed |
| #18 | `codex/issue-18-grocery-photo` | Omit missing/failed ingredient photo boxes; supplying photos remains an asset task |
| #20 | `codex/issue-20-substitution-layout` | Stack substitution names when space is limited |
| #22 | `codex/issue-22-selected-tab` | Bold selected labels; web underline and aria-current |
| #24 | `codex/issue-24-tour-order` | [Tour order proposal](#proposed-quick-start-order--issue-24), pending choice |
| #26 | `codex/issue-26-plan-menu` | Remove unrequested chooser menu and unused chooser code |
| #28 | `codex/issue-28-prep-completion` | One PUT endpoint, one JSON store, legacy migration; updated API/app must ship together |
| #30 | `codex/issue-30-plan-list-layout` | Full names and Schedule without shrinking photos |
| #32 | `codex/issue-32-decline-in-place` | Retain review during replacement; failure supports retry |
| #34 | `codex/issue-34-grocery-heading` | Full-width secondary usage heading |
| #36 | `codex/issue-36-tab-reselection` | Same-tab selection returns to root |
| #38 | `codex/issue-38-category-preferences` | [Category proposal](#category-preference-proposal--issue-38), pending choice |
| #40 | `codex/issue-40-more-navigation` | [More grouping proposal](#more-navigation-proposal--issue-40), pending choice |

At the time of that pass, 197 Python tests passed in a dedicated database, the unsigned
simulator build and web production build passed, and Taste Lab JavaScript syntax checks
passed. Test isolation resets Taste Lab's cached initializer between fresh schemas.
These are historical results, not validation of the current build. Issue #2's original
HTTP 405 trigger remains unresolved; request diagnostics are in place.
