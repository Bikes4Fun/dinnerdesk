# Dinnerdesk tester checklist

*Last updated: Oct 7, 2026 · Build: merged `main` + `prep-grocery-recipes` (includes suggested-plan work)*

*For the team: each section here matches a section of [`DESIGN.md`](DESIGN.md) → Features. When a feature changes, update both.*

Thanks for testing. Work through the sections in order; each one builds on the last. Check off what works, and write down anything that doesn't.

## Focus for this build

These changed most recently, so check them first and most carefully:

- **Weekend prep (section 8):** rebuilt. The same prep from several meals is now one task ("Prep potatoes" for two meals), you can check off each item, and closing a task really hides its details.
- **Diet and avoid filters (section 5):** they now hide recipes in Recipes, not just in suggestions. Pick one of omnivore / pescatarian / vegetarian / vegan. Fish and "None" are in the avoid list.
- **Grocery (section 6):** share or email the list, show/hide completed items from the bottom of the list, a simpler Add item sheet, clearer menu names.
- **Recipes (section 5):** timers on Cook steps, and a "Uses pantry" filter on iPhone.
- **Suggested plans (section 3):** review, swap, approve or decline a proposal; keep your own picks.
- **Larger text (sections 5, 6, 7, 10):** grocery rows, recipe cards, icon rows like "Aisle order", and section headers.

Everything else is a regression check: it worked before, so confirm it still does.

## Before you start

- Use the iPhone app if you can. A smaller iPhone is best.
- Do one pass at normal text size, then turn on **larger text** (Settings → Accessibility → Display & Text Size → Larger Text, slider near the top) and do it again. Many fixes in this build are for large text.
- Have a few minutes to cook-plan for real. Real choices find more problems than random taps.



## How to report a problem

For each problem, note:

1. Which section and step (e.g. "Plan 2.3").
2. What you did, what you expected, and what happened instead.
3. Your text size (normal or larger).
4. A screenshot, if you can.

"Confusing" is a valid report. You don't need to find a bug for it to be worth writing down.

---



## 1. Getting started

- [ ] Create an account with email and password.
- [ ] The Quick start tour appears. You can **Skip** it easily, and it doesn't come back next time you open the app.
- [ ] Replay the tour from More → Settings. It shows Recipes, This week, Grocery, and Weekend prep.
- [ ] Sign out and use **Forgot password**. The email arrives and the link lets you set a new password.



## 2. Taste Lab

Find it under More, or "Improve your results" on the Plan screen.

- [x] Set your diet, allergies, and things you avoid.
- [x] Tap **None** under allergies or avoids. Anything you had selected clears.
- [x] Choose **Fish** as something you avoid. Fish meals (salmon, tuna, cod…) stop appearing. Note: dishes with fish sauce count as fish too.
- [x] Swipe through some meals: like some, pass on some.
- [x] On a suggested plan, tap **Not for us**. A different plan appears (not a "You're set" screen).
- [x] Tap a meal to swap it, then try **More options**. New choices appear, or a clear message says there are no more.
- [x] The "Not for us" / "This plan works" buttons don't cover any meal names.
- [x] Approve a plan. You see a completion screen.
- [x] Keep rejecting until nothing is left. You get a helpful message, not a dead end. [received a message but it was uninteresting font and i didn't read or notice it right away so it seemed like a glitch]



## 3. Suggested meal plans

Start from the Plan tab → ⋯ → New meal plan → Suggest meals for me.

**Suggestions don't take over your plan**

- [ ] Note what's on your plan and your grocery list.
- [ ] Ask for suggestions. A "Review your suggestions" screen appears.
- [ ] Your current plan and grocery list are unchanged until you approve.
- [ ] The note at the top briefly says why these meals were picked (e.g. "2 you've cooked · 3 match your tastes · 4 use your pantry").

**Swap one meal**

- [ ] Tap **Swap meal**. A replacement picker opens without changing the plan.
- [ ] Search by meal name or ingredient. Choices still respect Taste Lab filters and exclude meals already on this proposal.
- [ ] Cancel the picker. No meal changes and no negative preference feedback is recorded.
- [ ] Choose a replacement. Only that meal changes; the picker closes.
- [ ] Attempt an unavailable replacement after the plan has changed. A readable error appears without changing the plan.
- [ ] Swap the same spot several times. When options run out you get a helpful message.

**Approve or decline**

- [ ] Approve after a swap. The reviewed meals become your plan, and the grocery list updates to match.
- [ ] Make another suggested plan and **Decline** it. Your current plan stays intact and a new proposal appears.
- [ ] If nothing fits your filters, you're told what to change, not shown a success screen.

**Keep your own picks**

- [ ] Add 2–3 meals yourself from Recipes.
- [ ] Ask for suggestions with **Keep my selected meals and fill the rest** turned on.
- [ ] Your meals stay, marked "Your selection", and can't be swapped. Suggestions fill the rest.

**Come back to it later**

- [ ] Make a proposal, close it without deciding, then open ⋯ → **Review pending suggestions**. It's still there.
- [ ] Close the app completely, reopen it, and review the proposal again.



## 4. Your plan (This week)

- [ ] Each meal shows a photo, name, and servings. Names are readable, not chopped mid-word.
- [ ] Tap the circle on a photo to mark a meal cooked. It fades and moves down. Tap again to undo.
- [ ] ⋯ → **Edit plan**: change servings, schedule a meal on a day, select several meals and mark cooked or remove them.
- [ ] In Edit mode, 👍/👎 appear under each meal. Outside Edit mode they're hidden.
- [ ] In Edit mode, **Done** shows at the top beside ⋯. Tapping it leaves Edit mode and clears any selected meals.
- [ ] 👎 a meal, then make a new suggested plan. That meal is never suggested.
- [ ] ⋯ → **Grid view**: meals line up neatly in two columns, photos aligned. At the largest text sizes it shows as a list instead.
- [ ] ⋯ menu: every option is fully readable and reachable, even at large text (scroll if needed).
- [ ] ⋯ → **Save as draft**, then ⋯ → **Saved plans & history**: the draft is there and loads correctly.
- [ ] In Saved plans & history, approved and declined suggestions show the right meal count, decision, and number of swaps.
- [ ] Nothing at the bottom of the screen is hidden behind the tab bar.



## 5. Recipes

- [ ] A **Suggestions** row appears at the top. **See all** opens the full list.
- [ ] At large text, section titles like "Your favorites" aren't cut off. If "See all" doesn't fit, the title itself becomes the link (with an arrow).
- [ ] Search by recipe name or ingredient.
- [ ] Heart a recipe. It shows in Your favorites. Mark one **To try**.
- [ ] Hide a recipe. It disappears from browse, search, and suggestions. Unhide it from the hidden list.
- [ ] Open a recipe. Change servings; ingredient amounts change to match.
- [ ] Ingredient rows have thin lines between them, so it's clear which amount goes with which ingredient (especially at large text).
- [ ] Open the steps. Each step is numbered, and amounts for that step appear under it.
- [ ] **Edit** a recipe and save. Your change shows. **Restore** brings back the original.
- [ ] **Add to this plan** from a recipe page. It's added and you stay on the recipe.
- [ ] In Cook mode, a step that mentions a time ("simmer 10 minutes") has a timer button. Start it; it counts down and says "Time's up" at zero (with a buzz on iPhone). For a range like "3–4 minutes" it uses the shorter time.
- [ ] Search, then tap **Uses pantry**. Only recipes using things you have stay. (On iPhone this is new.)
- [ ] At the largest text size, search results show one recipe per row and the browse rows' cards are wider, so names aren't broken mid-word.

**What to eat filters** (More → Settings → What to eat, or the Quick start tour)
- [ ] Diet: picking vegan, vegetarian, pescatarian or omnivore switches to it; you can't pick two. Gluten-free and dairy-free add on.
- [ ] Choose **vegan**. Recipes with meat, fish, eggs or dairy disappear from Recipes, not just from suggestions. Peanut-butter or coconut-milk dishes still show.
- [ ] Avoid **fish**. Salmon, tuna, cod and fish-sauce dishes disappear. Tap **None** and they come back.
- [ ] Recipes you wrote yourself always show, whatever the filters.



## 6. Grocery list

- [ ] The list matches the meals on your plan. Each ingredient appears once, with amounts combined.
- [ ] Items you have in your pantry are still listed and marked as owned.
- [ ] Check items off. Add your own item (like "paper towels").
- [ ] Open an item. "You'll use this in…" lists only meals that are actually on your current plan.
- [ ] On an item, type a substitute and tap **Use this instead**. The screen stays open on the new item; you don't get kicked back to the list.
- [x] Change an item's store and aisle. The choice is remembered.
- [ ] Remove a meal from your plan. Its ingredients leave the grocery list. [what happens if the grocery is used by multiple recipes? does everything recalculate?]




- [ ] Check some items off. At the bottom of the list, **Show N completed** brings them back and **Hide completed** hides them again. It matches ⋯ → Show completed items.
- [ ] Pick a store whose items are all checked off. You see "Everything for … is checked off", not a blank screen.
- [ ] Tap **+**. Type "sugar": one suggestion appears (sugar, not sugar snap peas). **Add** in the top bar always works, even at large text.
- [ ] ⋯ → **Share list**. Messages, Mail and Notes are offered. The text lists only what's left to buy, grouped by aisle, for the store you picked. (Website: Share list and Email list.)
- [ ] The ⋯ menu says **Show meals under each item** and **Edit stores & aisles**.
- [ ] At the largest text size, each item's amount sits under its name.

## 7. My kitchen (More → My kitchen)

- [ ] **Family portions**: change the number. At large text, the − / + control moves to its own line instead of breaking the word "portions". [will the standard automatic recipe serving sizes change? what else does this do?]
- [ ] **Pantry**: add an item, mark "Have this item", set an amount. The screen background matches the rest of the app (cream, not grey).
- [ ] **Always checked off**: add salt or oil. It stays checked on the grocery list.
- [ ] **Substitutions**: add one (e.g. vegetable oil → canola oil). The grocery list uses the new name. Delete it again.
- [ ] **Stores & aisles**: tap a store to remove it. The store you tapped is the one offered for removal. The confirmation is easy to read.
- [ ] Reorder and rename aisles. [reording is not necesary and could be removed if it notably simplifies things]
- [ ] At large text, section headers scroll away normally instead of sticking and covering the screen.



## 8. Weekend prep

- [ ] With meals on your plan, Prep shows tasks named for the item or component, such as **Prep potatoes**, **Prep mashed potatoes**, **Grate mozzarella**, or **Make tzatziki**.
- [ ] Two meals needing the same prep share one task, with each meal's instructions underneath and their quantities combined.
- [ ] Repeated ingredient mentions within one task do not multiply quantities; broth, frozen peas, and eggs are not pulled into unrelated chopping tasks.
- [ ] A closed task shows its name, involved meals, and partial progress. Expand it to see quantities and steps; collapse it to hide them.
- [ ] Check one step: only that step changes, and folding stays as it was. Complete the last step: the whole task checks itself.
- [ ] Uncheck one step: the task becomes incomplete. Check or uncheck the whole task: all its steps follow.
- [ ] Refresh and reopen: checks persist. Rename a recipe or regroup its unchanged steps: their checks persist.
- [ ] Add or rewrite a prep step: that step starts incomplete; unchanged steps keep their checks.
- [ ] Suggested steps exclude cooking and serving. Explicitly tagged Prep steps still take priority.
- [ ] Each step asks “Useful to do ahead?” with thumbs up/down, separate from completion; ratings persist after refresh.


## 9. Account & household

- [ ] Invite someone with the share sheet. (invite link works)
- [ ] They join and see the same plan, grocery list, and pantry. (todo)
- [ ] Remove them from Account & security. They lose access. (need to see generated invite links and be able to cancel them)
- [ ] Change your password. (need to confirm new password matches. formatting is too bulky.)
- [ ] Settings → Privacy reads clearly.



## 10. Across the whole app

- [ ] The tab you're on is obvious without relying on color alone. A filled-icon experiment was reverted, so report it if the accent color is the only difference. `docs/color only representation of current page.png`
- [ ] Backgrounds look consistent (warm cream) from screen to screen.
- [ ] At the largest text size, nothing important is cut off, overlapping, or unreachable.
- [ ] Pull to refresh works on each tab.



## 11. Website (optional, lower priority)

- [ ] Sign in on the website. Your plan, grocery list, and pantry match the phone.
- [ ] Make a suggested plan on the website: review, swap, approve, and decline work the same way.
- [ ] Print the grocery list and the weekend prep list.

---



## Not built yet (no need to report)

- Nutrition, calories, and Apple Health
- Liking or disliking whole categories (curry, Mexican, comfort food…)
- Star ratings after cooking, importing recipes from a link
- Moving a prep task to a different day
- Android

## Overall impressions

- What did you like most?
- What was most confusing?
- Would you use this to plan a real week? What would stop you?



## Merged planning and prep verification

Candidate: merged `main` + `prep-grocery-recipes` · Oct 7, 2026 · deployment must be verified separately.

- [ ] Replay Quick start on web and iOS: the first how-to step is “Fewer dinner decisions,” explaining personalized suggestions and optional browsing.

- [ ] Verify the API and iOS app are deployed/built together. A stale server must show a readable compatibility message before generating a proposal.
- [ ] In normal and accessibility text sizes, review a proposal, open the swap picker, and expand a long prep task. Buttons remain reachable and titles do not overlap.
- [ ] Saved plans can be deleted from the library; the active plan is protected and deleting history does not erase recommendation evidence.
- [ ] Switch from a recipe detail or Taste Lab to another tab and back: the original tab shows its main screen.
- [ ] Whole-plan refusal is a weaker preference signal than swapping a meal and approving the rest; resizing/cancelling records no dislike.

Compatibility: the ranker still exports `KEYS`, `DIET_BLOCKS`, `AVOID_ALIAS`, `hits`, and `recipe_text` for the merged diet filter. Both PUT and PATCH Prep step requests use the same completion state.

## Private catalog migration

- Approve, decline and swap suggestions; confirm household state persists after restart.
- Configure external private catalog/photo paths locally; verify existing recipes, Taste Lab, templates and photos.
- Confirm restarting the API does not import recipes or overwrite catalog rows.
- Before Railway deployment, upload and verify the private asset package and configure both required paths.
- Check Git contains no production recipes, food photos, credentials or database exports.
