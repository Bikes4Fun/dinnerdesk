# Dinnerdesk to-do

The working list: issues, fixes, ideas, and open questions. This is the only file with
checkboxes. How things are *supposed* to work is in [`DESIGN.md`](DESIGN.md).

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

- [ ] Taste Lab: when everything is rejected, the recovery message is easy to miss (plain font,
      looked like a glitch). Make it stand out. *(from your tester checklist notes)*
- [ ] Use a purple ★ tip to tell users when a recipe photo is AI-generated (and, once
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
- [ ] Prep task names from real recipes are sometimes wrong: "Whisk garlic", "Prep off roots",
      "Grate on holes grater". *(Claude)*

### Plan and suggestions

- [ ] No obvious Done control when editing the plan.
      `docs/suggestion meal plan to do/no easy done editing button.png`
- [ ] Edit mode at large text: "Select all / 0 selected" and "Mark cooked / Remove" break
      mid-word; "4 servin…" is cut off; − and + spill outside their box.
      `docs/accessibility to do/Screenshot 2026-10-07 at 7.45.56 PM.png`
- [ ] Remove dialog says "Remove 1 meals?", and Cancel is cut off at the bottom.
      `docs/suggestion meal plan to do/accessiblity remove one meal cut off.png`
- [ ] "Won't be suggested again" should be a purple ★ tip.
      `docs/suggestion meal plan to do/move wont be suggested again to a purple stary tip and fix the over flow of -+ .png`
- [ ] Bring back the one-line "why these meals" summary; it was removed along with the per-meal
      commentary. Approving still writes "N meals · Approved · N swaps" into the plan; the plan
      should look the same whether meals were suggested or chosen.
      `docs/weekend prep to do/removed excess commentary but also removed the summary of why its a good plan.png`
- [ ] Saved plans and history: every row is "This week", dates repeat, and "History · 0 swaps"
      means nothing to users. Clearer rows, accessible delete, empty states.
      `docs/suggestion meal plan to do/history 0 swaps is data for us the user doesn't care.png`
      `docs/suggestion meal plan to do/saved and draft plans formatting.png`
- [ ] Plan list view: room for a Schedule button and more of the recipe name, without shrinking
      the photo.
- [ ] Suggested plans should look like Taste Lab's suggested plans.
- [ ] Declining a suggested plan shouldn't reload the whole page.

### Taste Lab

- [ ] Double header on every Taste Lab screen: the top bar says "Taste Lab" and a second
      "← Taste Lab" sits below it. `docs/quick start to do/Screenshot 2026-10-07 at 6.21.50 PM.png`
- [ ] Filters should fit on one iPhone 16 screen at standard text, without dropping options.
      `docs/quick start to do/taste lab filters should fit on one screen from an iphone 16 with standard font size. do not remove options but do consider layout/formatting..png`
- [ ] Meal names are cut at two lines when there's room for more.
      `docs/quick start to do/tastelab meal names don't need to cut off at two lines assuming they don't spill over the actual phone screen size.png`
- [ ] Show more plans before "You're set".
      `docs/quick start to do/tastelab should be showing more mealplan suggestions before youre set.png`

### Recipes

- [ ] Use "See all" or an arrow for section links, not both.
      `docs/recipes page to do/choose either see all or arrow not both.png`
- [ ] Browse cards break names mid-word at large text. A fix is on main; check it on a fresh
      build. Same screenshot as above.

### Grocery

- [ ] The "Pantry" note under an item should be a purple ★ tip. Aisle headers (PANTRY) should
      stay smaller than item names at large text.
      `docs/groceries page to do/add a purple stary tip to the _pantry_ note and resize aisle terms to remain smaller than title.png`
- [ ] Item page shows an empty box where the ingredient photo goes.
      `docs/groceries page to do/get images of individual foods.png`
- [ ] "You'll use this in…" wraps too early at large text.

### My kitchen

- [ ] Add-to-pantry search has two X buttons, and the keyboard can't move through results
      (tab, arrow up/down).
      `docs/my kitchen to do/add to pantry search has two x_s and doesn't allow tab arrow down up select.png`
      `docs/accessibility to do/Screenshot 2026-10-07 at 7.57.09 PM.png`
- [ ] Substitutions: names break mid-word at large text ("coconu t oil").
      `docs/accessibility to do/access your subs formatting issues.png`

### Weekend prep

- [ ] Redesign the Prep screen ("this design is awful"). Needs your direction first. Your
      screenshot shows the old "Chop vegetables & herbs" grouping, so check against a restarted
      server too. `docs/weekend prep to do/this design is awful.png`

### Whole app

- [ ] The current tab is shown by color only (the filled-icon fix was reverted).
      `docs/accessibility to do/color only representation of current page.png`
- [ ] The selected-tab highlight spills past the tab bar and clips the Grocery badge.
      `docs/accessibility to do/bottom nav highlight overlow when selected.png`
- [ ] Large-text pass on Pantry, the recipe page, Cook, Prep, and Settings (needs a device).
- [ ] Opening a tab again should show that tab's main page.

### Quick start tour

- [ ] Decide the order. Notes so far: start by showing suggestions, then groceries; end with
      Taste Lab; explain the purple ★ tips and that they fade after the first few uses.
      `docs/quick start to do/quick start to do .txt`
- [ ] Tour cards are blank below the text; each needs a picture of its screen.
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
- [ ] **Prep screen redesign** (see Weekend prep above).

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
      [`grocery-plan.md`](grocery-plan.md).
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

## Done (recent)

Older history is in Git and in [`DESIGN.md`](DESIGN.md), which describes everything that ships.

**Oct 7–8, 2026**
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
- [x] Cook-mode timers; "Uses pantry" filter on iPhone; recipe categories (groundwork).
- [x] Large text: ⋯ menus grow and scroll; plan grid falls back to a list; section headers stop
      pinning and keep side margins; Family portions, Aisle order, store removal, grocery rows,
      recipe cards, ingredient row lines; consistent cream background.
- [x] Thumbs on the plan only in Edit mode; one summary line instead of commentary under every
      meal.
