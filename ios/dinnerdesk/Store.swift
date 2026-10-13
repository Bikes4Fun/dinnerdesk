import Combine
import Foundation

@MainActor
final class Store: ObservableObject {
  @Published var proposalError: String?
  @Published var proposal: Plan?
  // Loading a saved proposal must not interrupt launch or pull-to-refresh.
  @Published var showingProposal = false
  @Published private(set) var generatingProposal = false
  @Published var plan: Plan? {
    didSet {
      guard let plan else { return }
      ResponseCache.save(plan, as: "plans/current")
      // Prep follows the plan's meals, servings and cooked state.
      if Self.prepShape(oldValue) != Self.prepShape(plan) { Freshness.invalidate(Freshness.prep) }
    }
  }
  @Published var recipes: [RecipeSummary] = []
  /// Saved on every change (checking items off in the store), so a relaunch with no signal
  /// still shows the list as the person left it.
  @Published var grocery: [GroceryLine] = [] {
    didSet {
      guard let id = plan?.id else { return }
      ResponseCache.save(GroceryList(lines: grocery), as: "plans/\(id)/grocery")
    }
  }
  /// Household default servings, for recipes not yet on the plan.
  @Published private(set) var familyPortions: Int?
  /// Dinnerdesk admins can tag recipe steps as Prep.
  @Published private(set) var isAdmin = false
  @Published var stores: [ShopStore] = ShopStore.defaults
  @Published var aisles: [ShopAisle] = ShopAisle.defaults
  @Published var groupByStore = false
  @Published var showMeals = false
  @Published var hideChecked = true
  @Published var showAisleNums = false
  @Published var showEmoji = false
  @Published var prepTasks: [PrepTask] = []
  @Published var error: String?

  private var groceryPrefsLoaded = false
  private var paintedFromCache = false
  private var loadingAll = false
  /// Bumped when the account changes. A request started before then belongs to the previous
  /// kitchen, so its result is dropped instead of shown or saved.
  private var generation = 0
  private var prefetchTask: Task<Void, Never>?

  private static func prepShape(_ plan: Plan?) -> [String] {
    (plan?.slots ?? []).map { "\($0.id):\($0.recipeId):\($0.servings):\($0.cooked)" }
  }

  private func fail(_ error: Error) {
    guard !API.isCancellation(error) else { return }
    self.error = error.localizedDescription
  }

  var weekIds: Set<Int> {
    Set(plan?.slots.map(\.recipeId) ?? [])
  }

  func onWeek(_ recipeId: Int) -> Bool {
    weekIds.contains(recipeId)
  }

  /// Shows what's saved on the device right away, then refreshes from the server.
  /// `onlyIfStale` (launch, returning to the app) skips the server while the data is fresh;
  /// pull-to-refresh and recovering from a failed change always refetch.
  func loadAll(onlyIfStale: Bool = false) async {
    paintFromCache()
    // Launch and returning to the app can both ask at once; one request is enough.
    if onlyIfStale && loadingAll { return }
    if onlyIfStale && Freshness.isFresh(Freshness.plan) && Freshness.isFresh(Freshness.recipes) {
      await loadGrocery(onlyIfStale: true)
      return
    }
    let gen = generation
    loadingAll = true
    defer { if gen == generation { loadingAll = false } }
    error = nil
    do {
      async let planBox: Plan = API.get("plans/current", cache: true)
      async let recipeBox: RecipeList = API.get("recipes", query: ["limit": "400"], cache: true)
      let plan = try await planBox
      guard gen == generation else { return }
      self.plan = plan
      Freshness.mark(Freshness.plan)
      var pending: PendingSuggestion?
      do {
        let loaded: PendingSuggestion = try await API.get("suggestions/current", reportErrors: false)
        pending = loaded
      } catch {}
      guard gen == generation else { return }
      if let pending, pending.plan?.status == "suggested", pending.plan?.suggestedRecipeIds != nil { proposal = pending.plan }
      let recipeList = try await recipeBox
      guard gen == generation else { return }
      recipes = recipeList.recipes
      Freshness.mark(Freshness.recipes)
      await reloadGrocery()
      await loadGroceryPrefs(onlyIfStale: onlyIfStale)
      guard gen == generation else { return }
      prefetchTask?.cancel()
      prefetchTask = Task { await prefetchRecipes() }
    } catch {
      guard gen == generation else { return }
      fail(error)
    }
  }

  /// Signed in, out or as someone else: forget the previous kitchen and load this one.
  func switchAccount(load: Bool = true) async {
    generation += 1
    prefetchTask?.cancel()
    prefetchTask = nil
    loadingAll = false
    paintedFromCache = true  // the saved copy was just cleared
    error = nil
    proposalError = nil
    showingProposal = false
    // Grocery settings belong to the household too: back to defaults until the new one loads.
    stores = ShopStore.defaults
    aisles = ShopAisle.defaults
    groupByStore = false
    showMeals = false
    hideChecked = true
    showAisleNums = false
    showEmoji = false
    plan = nil
    proposal = nil
    recipes = []
    grocery = []
    prepTasks = []
    hiddenRecipes = nil
    familyPortions = nil
    isAdmin = false
    groceryPrefsLoaded = false
    if load { await loadAll() }
  }

  /// First paint from the device: the last plan, recipes, grocery list and prep.
  private func paintFromCache() {
    guard !paintedFromCache else { return }
    paintedFromCache = true
    if plan == nil, let saved: Plan = API.cached("plans/current") { plan = saved }
    if recipes.isEmpty, let saved: RecipeList = API.cached("recipes", query: ["limit": "400"]) {
      recipes = saved.recipes
    }
    if let plan {
      if grocery.isEmpty, let saved: GroceryList = API.cached("plans/\(plan.id)/grocery") { grocery = saved.lines }
      if prepTasks.isEmpty, let saved: PrepList = API.cached("plans/\(plan.id)/prep") { prepTasks = saved.tasks }
    }
    if let saved: Household = API.cached("household") { applyHousehold(saved) }
  }

  /// Full recipes and photos for planned meals, then favorites and To try, so cooking and
  /// shopping work with no signal. Only fetches what isn't saved or is over a week old.
  private func prefetchRecipes() async {
    var ids: [Int] = []
    var photos: [String?] = []
    for slot in plan?.slots ?? [] where !ids.contains(slot.recipeId) {
      ids.append(slot.recipeId)
      photos.append(slot.photoPath)
    }
    for recipe in recipes where (recipe.favorited || recipe.toTry) && !ids.contains(recipe.id) {
      ids.append(recipe.id)
      photos.append(recipe.photoPath)
    }
    let week: TimeInterval = 7 * 24 * 60 * 60
    let gen = generation
    for (id, photo) in zip(ids, photos) {
      if Task.isCancelled || gen != generation { return }
      let age = ResponseCache.age(of: ResponseCache.key("recipes/\(id)"))
      if age == nil || age! > week {
        let _: RecipeDetail? = try? await API.get("recipes/\(id)", reportErrors: false, cache: true)
      }
      #if os(iOS)
      await PhotoCache.prefetch(photo)
      #endif
    }
  }

  /// Signed-in status for admin-only controls, fetched once per launch.
  func loadAdmin() async {
    if Freshness.isFresh(Freshness.auth, within: .greatestFiniteMagnitude) { return }
    let gen = generation
    guard let status = try? await AuthAPI.status(), gen == generation else { return }
    isAdmin = status.admin == true
    Freshness.mark(Freshness.auth)
  }

  func searchRecipes(_ q: String) async {
    do {
      var query = ["limit": "400"]
      let trimmed = q.trimmingCharacters(in: .whitespacesAndNewlines)
      if !trimmed.isEmpty { query["q"] = trimmed }
      let box: RecipeList = try await API.get("recipes", query: query)
      recipes = box.recipes
    } catch {
      fail(error)
    }
  }

  private var hiddenRecipes: [RecipeSummary]?

  /// `onlyIfStale` (opening Recipes) reuses the list from earlier in this launch.
  func loadHiddenRecipes(onlyIfStale: Bool = false) async -> [RecipeSummary] {
    let query = ["limit": "400", "hidden": "true"]
    // The saved list keeps showing if the request fails (no signal).
    if hiddenRecipes == nil, let saved: RecipeList = API.cached("recipes", query: query) {
      hiddenRecipes = saved.recipes
    }
    if onlyIfStale, let hiddenRecipes, Freshness.isFresh(Freshness.hidden) { return hiddenRecipes }
    let gen = generation
    do {
      let box: RecipeList = try await API.get("recipes", query: query, cache: true)
      guard gen == generation else { return hiddenRecipes ?? [] }
      hiddenRecipes = box.recipes
      Freshness.mark(Freshness.hidden)
      return box.recipes
    } catch {
      fail(error)
      return hiddenRecipes ?? []
    }
  }

  func toggleFavorite(_ recipe: RecipeSummary) async {
    let on = !recipe.favorited
    recipes = recipes.map { $0.id == recipe.id ? $0.withFavorited(on) : $0 }
    do {
      let _: RecipeDetail = try await API.send(
        "recipes/\(recipe.id)/favorite",
        method: "PUT",
        body: ["on": on],
        cacheAs: "recipes/\(recipe.id)"
      )
    } catch {
      guard !API.isCancellation(error) else { return }
      let message = error.localizedDescription
      await loadAll()
      self.error = message
    }
  }

  func setFavorite(id: Int, on: Bool) async -> RecipeDetail? {
    recipes = recipes.map { $0.id == id ? $0.withFavorited(on) : $0 }
    do {
      return try await API.send("recipes/\(id)/favorite", method: "PUT", body: ["on": on], cacheAs: "recipes/\(id)")
    } catch {
      fail(error)
      return nil
    }
  }

  func toggleTryLater(_ recipe: RecipeSummary) async {
    let on = !recipe.toTry
    recipes = recipes.map { $0.id == recipe.id ? $0.withToTry(on) : $0 }
    _ = await setTryLater(id: recipe.id, on: on)
  }

  func setTryLater(id: Int, on: Bool) async -> RecipeDetail? {
    recipes = recipes.map { $0.id == id ? $0.withToTry(on) : $0 }
    do {
      return try await API.send("recipes/\(id)/try", method: "PUT", body: ["on": on], cacheAs: "recipes/\(id)")
    } catch {
      fail(error)
      return nil
    }
  }

  func hideRecipe(_ id: Int) async {
    _ = await setHidden(id: id, on: true)
  }

  func setHidden(id: Int, on: Bool) async -> RecipeDetail? {
    Freshness.invalidate(Freshness.hidden)
    if on {
      recipes = recipes.filter { $0.id != id }
    }
    do {
      let next: RecipeDetail = try await API.send(
        "recipes/\(id)/hidden",
        method: "PUT",
        body: ["on": on],
        cacheAs: "recipes/\(id)"
      )
      if !on {
        await searchRecipes("")
      }
      return next
    } catch {
      guard !API.isCancellation(error) else { return nil }
      let message = error.localizedDescription
      await loadAll()
      self.error = message
      return nil
    }
  }

  func toggleWeek(_ recipe: RecipeSummary) async {
    if onWeek(recipe.id) {
      await removeFromWeek(recipeId: recipe.id)
    } else {
      await addToWeek(recipeId: recipe.id, servings: nil)
    }
  }

  func addToWeek(recipeId: Int, servings: Int?) async {
    do {
      let plan = try await currentPlan()
      var slots = plan.slots.map(\.asBody)
      var added: [String: Any] = [
        "recipe_id": recipeId,
        "meal_type": "dinner",
      ]
      if let servings {
        added["servings"] = servings
      }
      slots.append(added)
      self.plan = try await API.send(
        "plans/\(plan.id)/slots",
        method: "PUT",
        body: ["slots": slots]
      )
      await reloadGrocery()
    } catch {
      fail(error)
    }
  }

  func removeFromWeek(recipeId: Int) async {
    do {
      let plan = try await currentPlan()
      let slots = plan.slots.filter { $0.recipeId != recipeId }.map(\.asBody)
      self.plan = try await API.send(
        "plans/\(plan.id)/slots",
        method: "PUT",
        body: ["slots": slots]
      )
      await reloadGrocery()
    } catch {
      fail(error)
    }
  }

  func placeSlot(_ slot: PlanSlot, day: Int) async {
    await patchSlot(slot.id, ["day_index": day])
  }

  func unschedule(_ slot: PlanSlot) async {
    await patchSlot(slot.id, ["unschedule": true])
  }

  func toggleCooked(_ slot: PlanSlot) async {
    applyLocalSlot(id: slot.id) { $0.cooked.toggle() }
    await patchSlot(slot.id, ["cooked": !slot.cooked], reloadOnError: true)
  }

  func setServings(_ slot: PlanSlot, _ servings: Int) async {
    let next = min(50, max(1, servings))
    if next == slot.servings { return }
    applyLocalSlot(id: slot.id) { $0.servings = next }
    await patchSlot(slot.id, ["servings": next], refreshGrocery: true)
  }

  func setServingsForRecipe(_ recipeId: Int, _ servings: Int) async {
    let next = min(50, max(1, servings))
    let slots = (plan?.slots ?? []).filter { $0.recipeId == recipeId }
    guard !slots.isEmpty else { return }
    for slot in slots where slot.servings != next {
      applyLocalSlot(id: slot.id) { $0.servings = next }
      await patchSlot(slot.id, ["servings": next], refreshGrocery: false)
    }
    await reloadGrocery()
  }

  func removeSlot(_ slot: PlanSlot) async {
    do {
      let next: Plan = try await API.send("slots/\(slot.id)", method: "DELETE")
      plan = next
      await reloadGrocery()
    } catch {
      guard !API.isCancellation(error) else { return }
      let message = error.localizedDescription
      await loadAll()
      self.error = message
    }
  }

  func markAllCooked() async {
    let pending = (plan?.slots ?? []).filter { !$0.cooked }
    for slot in pending {
      applyLocalSlot(id: slot.id) { $0.cooked = true }
      await patchSlot(slot.id, ["cooked": true], reloadOnError: true)
    }
  }

  /// The server rebuilds the list whenever the plan, pantry or stores change, so reading it
  /// is enough. `onlyIfStale` (opening the Grocery tab) uses the saved list while it's fresh;
  /// `rebuild` (pull-to-refresh) asks the server to rebuild it first.
  func loadGrocery(onlyIfStale: Bool = false, rebuild: Bool = false) async {
    // An empty list is a real answer too: freshness alone decides.
    if onlyIfStale && Freshness.isFresh(Freshness.grocery) {
      await loadGroceryPrefs(onlyIfStale: true)
      return
    }
    let gen = generation
    do {
      let plan = try await currentPlan()
      let list: GroceryList
      if rebuild {
        list = try await API.send("plans/\(plan.id)/grocery", method: "POST", cacheAs: "plans/\(plan.id)/grocery")
      } else {
        list = try await API.get("plans/\(plan.id)/grocery", cache: true)
      }
      guard gen == generation else { return }
      grocery = list.lines
      Freshness.mark(Freshness.grocery)
      await loadGroceryPrefs(onlyIfStale: !rebuild)
    } catch {
      fail(error)
    }
  }

  func toggleGrocery(_ line: GroceryLine) async {
    await patchGrocery(line, ["checked": !line.checked])
  }

  func setGroceryStore(_ line: GroceryLine, _ storeId: String) async {
    await patchGrocery(line, ["store": storeId])
  }

  func setGroceryAisle(_ line: GroceryLine, _ aisleId: String) async {
    await patchGrocery(line, ["aisle": aisleId])
  }

  func setGroceryQuantity(_ line: GroceryLine, _ quantity: String) async {
    await patchGrocery(line, ["quantity": quantity])
  }

  func patchGrocery(_ line: GroceryLine, _ body: [String: Any]) async {
    if let i = grocery.firstIndex(where: { $0.id == line.id }) {
      if let name = body["custom_text"] as? String { grocery[i].name = name }
      if let checked = body["checked"] as? Bool { grocery[i].checked = checked }
      if let quantity = body["quantity"] as? String { grocery[i].quantity = quantity }
      if let aisle = body["aisle"] as? String { grocery[i].aisle = aisle }
      if let store = body["store"] as? String { grocery[i].store = store }
    }
    do {
      let _: Ok = try await API.send(
        "grocery/lines/\(line.id)",
        method: "PATCH",
        body: body
      )
      if body["custom_text"] != nil { await reloadGrocery() }
    } catch {
      fail(error)
      await reloadGrocery()
    }
  }

  func markAllGroceryComplete() async {
    let ids = grocery.filter { !$0.checked && !$0.neverShop }.map(\.id)
    guard !ids.isEmpty else { return }
    for i in grocery.indices where ids.contains(grocery[i].id) {
      grocery[i].checked = true
    }
    do {
      for id in ids {
        let _: Ok = try await API.send(
          "grocery/lines/\(id)",
          method: "PATCH",
          body: ["checked": true]
        )
      }
    } catch {
      fail(error)
      await reloadGrocery()
    }
  }

  func setPantryFlags(name: String, have: Bool, neverShop: Bool) async {
    do {
      let _: PantryFlagRow = try await API.send(
        "pantry/items",
        method: "POST",
        body: [
          "name": name,
          "have": have,
          "never_shop": neverShop,
          "zone": "dry",
        ]
      )
      await reloadGrocery()
    } catch {
      fail(error)
    }
  }

  func addSubstitute(from: String, to: String) async {
    let dest = to.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !dest.isEmpty else { return }
    do {
      let _: OverrideBox = try await API.send(
        "overrides",
        method: "POST",
        body: ["from_name": from, "to_name": dest]
      )
      await reloadGrocery()
    } catch {
      fail(error)
    }
  }

  func addGroceryLine(name: String, quantity: String, store: String? = nil) async {
    let names = name.split(separator: ",").map {
      $0.trimmingCharacters(in: .whitespacesAndNewlines)
    }.filter { !$0.isEmpty }
    guard !names.isEmpty, let plan else { return }
    let storeId = store ?? ""
    do {
      for item in names {
        let line: GroceryLine = try await API.send(
          "plans/\(plan.id)/grocery/lines",
          method: "POST",
          body: [
            "name": item,
            "quantity": quantity.trimmingCharacters(in: .whitespacesAndNewlines),
            "store": storeId,
          ]
        )
        if let index = grocery.firstIndex(where: { $0.id == line.id }) {
          grocery[index] = line
        } else {
          grocery.append(line)
        }
      }
    } catch {
      fail(error)
    }
  }

  func uncheckAllGrocery() async {
    let ids = grocery.filter { $0.checked && !$0.neverShop }.map(\.id)
    guard !ids.isEmpty else { return }
    for i in grocery.indices where ids.contains(grocery[i].id) {
      grocery[i].checked = false
    }
    do {
      for id in ids {
        let _: Ok = try await API.send(
          "grocery/lines/\(id)",
          method: "PATCH",
          body: ["checked": false]
        )
      }
    } catch {
      fail(error)
      await reloadGrocery()
    }
  }

  func suggestGroceryItems(_ q: String) async -> [String] {
    let trimmed = q.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return [] }
    do {
      let box: GroceryItemHits = try await API.get(
        "grocery-items",
        query: ["q": trimmed, "limit": "8"]
      )
      return box.items.map(\.name)
    } catch {
      fail(error)
      return []
    }
  }

  func persistGroceryPrefs() async {
    guard groceryPrefsLoaded else { return }
    let groceryPrefs: [String: Any] = [
      "stores": stores.map { ["id": $0.id, "name": $0.name] },
      "aisles": aisles.map { ["id": $0.id, "name": $0.name, "number": $0.number] },
      "groupByStore": groupByStore,
      "showMeals": showMeals,
      "hideChecked": hideChecked,
      "showAisleNums": showAisleNums,
      "showEmoji": showEmoji,
    ]
    do {
      let _: Household = try await API.send(
        "household",
        method: "PUT",
        body: ["prefs": ["grocery": groceryPrefs]],
        cacheAs: "household"
      )
    } catch {
      fail(error)
    }
  }

  func aisleName(_ id: String) -> String {
    aisles.first(where: { $0.id == id })?.name
      ?? id.replacingOccurrences(of: "_", with: " ").capitalized
  }

  func aisleTitle(_ id: String) -> String {
    guard let aisle = aisles.first(where: { $0.id == id }) else {
      return id.replacingOccurrences(of: "_", with: " ").capitalized
    }
    if !aisle.number.isEmpty {
      return "\(aisle.name) · Aisle \(aisle.number)"
    }
    return aisle.name
  }

  /// `onlyIfStale` (opening the Prep tab) skips the server unless the plan changed.
  func loadPrep(onlyIfStale: Bool = false) async {
    if onlyIfStale && Freshness.isFresh(Freshness.prep) { return }
    let gen = generation
    do {
      let plan = try await currentPlan()
      let box: PrepList = try await API.get("plans/\(plan.id)/prep", cache: true)
      guard gen == generation else { return }
      prepTasks = box.tasks
      Freshness.mark(Freshness.prep)
    } catch {
      fail(error)
    }
  }

  func togglePrep(_ task: PrepTask) async {
    let next = !task.done
    if let i = prepTasks.firstIndex(where: { $0.id == task.id }) {
      prepTasks[i].done = next
      // Checking a task checks every item in it.
      for m in prepTasks[i].meals.indices {
        for s in (prepTasks[i].meals[m].steps ?? []).indices {
          prepTasks[i].meals[m].steps?[s].done = next
        }
      }
    }
    do {
      let _: Ok = try await API.send("prep/\(task.id)", method: "PATCH", body: ["done": next])
      await loadPrep()
    } catch {
      fail(error)
      await loadPrep()
    }
  }

  /// Thumbs on a meal. A 👎 meal is never suggested again; a 👍 pulls similar meals in.
  func rateMeal(_ slot: PlanSlot, _ rating: Int) async {
    let before = slot.rating ?? 0
    setLocalRating(recipeId: slot.recipeId, rating)
    do {
      let _: MealRating = try await API.send(
        "recipes/\(slot.recipeId)/rating",
        method: "PUT",
        body: ["rating": rating]
      )
    } catch {
      setLocalRating(recipeId: slot.recipeId, before)
      fail(error)
    }
  }

  private func setLocalRating(recipeId: Int, _ rating: Int) {
    guard let plan else { return }
    self.plan = plan.withSlots(
      plan.slots.map { slot in
        var slot = slot
        if slot.recipeId == recipeId { slot.rating = rating }
        return slot
      })
  }

  /// Check off one item inside a prep task. The task is done once every item is.
  func togglePrepItem(taskId: Int, mealId: Int, step: PrepStep) async {
    guard let t = prepTasks.firstIndex(where: { $0.id == taskId }),
      let m = prepTasks[t].meals.firstIndex(where: { $0.id == mealId }),
      let s = prepTasks[t].meals[m].steps?.firstIndex(where: { $0.key == step.key })
    else { return }
    let next = !(step.done ?? false)
    prepTasks[t].meals[m].steps?[s].done = next
    prepTasks[t].done = prepTasks[t].meals.allSatisfy { meal in
      (meal.steps ?? []).allSatisfy { $0.done ?? false }
    }
    do {
      let result: PrepItemResult = try await API.send(
        "prep/\(taskId)/steps", method: "PUT",
        body: ["recipe_id": mealId, "key": step.key, "done": next])
      if let t = prepTasks.firstIndex(where: { $0.id == taskId }) { prepTasks[t].done = result.done }
    } catch {
      fail(error)
      await loadPrep()
    }
  }

  /// Was this a useful step to do ahead? Logged for review; it doesn't change what Prep shows.
  func ratePrepStep(taskId: Int, mealId: Int, step: PrepStep, _ rating: Int) async {
    let category = prepTasks.first(where: { $0.id == taskId })?.title ?? ""
    let before = step.rating ?? 0
    setLocalStepRating(taskId: taskId, mealId: mealId, key: step.key, rating)
    do {
      let _: Ok = try await API.send(
        "prep/feedback",
        method: "PUT",
        body: [
          "recipe_id": mealId,
          "key": step.key,
          "text": step.text,
          "category": category,
          "auto": step.auto ?? true,
          "rating": rating,
        ]
      )
    } catch {
      setLocalStepRating(taskId: taskId, mealId: mealId, key: step.key, before)
      fail(error)
    }
  }

  /// 👍/👎 on a whole prep item, with an optional reason and note for a 👎. Logged for review.
  /// A nil note keeps the one already saved.
  func ratePrepTask(_ taskId: Int, _ rating: Int, reason: String = "", note: String? = nil) async {
    guard let i = prepTasks.firstIndex(where: { $0.id == taskId }) else { return }
    let before = (prepTasks[i].rating, prepTasks[i].reason, prepTasks[i].reasonNote)
    let why = rating < 0 ? reason : ""
    let words = rating < 0 ? (note ?? prepTasks[i].reasonNote ?? "") : ""
    prepTasks[i].rating = rating
    prepTasks[i].reason = why
    prepTasks[i].reasonNote = words
    do {
      let _: Ok = try await API.send(
        "prep/\(taskId)/feedback", method: "PUT", body: ["rating": rating, "reason": why, "note": words])
    } catch {
      if let i = prepTasks.firstIndex(where: { $0.id == taskId }) {
        prepTasks[i].rating = before.0
        prepTasks[i].reason = before.1
        prepTasks[i].reasonNote = before.2
      }
      fail(error)
    }
  }

  /// Recipe steps that aren't in Weekend prep, for "Missing a prep step?". nil on failure.
  func loadMissingPrep() async -> [MissingPrepMeal]? {
    do {
      let plan = try await currentPlan()
      let box: MissingPrepList = try await API.get("plans/\(plan.id)/prep/missing")
      return box.meals
    } catch {
      fail(error)
      return nil
    }
  }

  /// Add a skipped recipe step to Weekend prep (or take it back), with an optional note.
  /// It shows in prep right away and is logged for review.
  func setMissingPrep(recipeId: Int, key: String, note: String, added: Bool) async -> Bool {
    do {
      let plan = try await currentPlan()
      let _: Ok = try await API.send(
        "plans/\(plan.id)/prep/missing", method: "PUT",
        body: ["recipe_id": recipeId, "key": key, "note": note, "added": added])
      await loadPrep()
      return true
    } catch {
      fail(error)
      return false
    }
  }

  private func setLocalStepRating(taskId: Int, mealId: Int, key: String, _ rating: Int) {
    guard let t = prepTasks.firstIndex(where: { $0.id == taskId }),
      let m = prepTasks[t].meals.firstIndex(where: { $0.id == mealId }),
      let s = prepTasks[t].meals[m].steps?.firstIndex(where: { $0.key == key })
    else { return }
    prepTasks[t].meals[m].steps?[s].rating = rating
  }

  func storeName(_ line: GroceryLine) -> String {
    stores.first(where: { $0.id == line.store })?.name
      ?? (line.store.isEmpty ? "Store" : line.store)
  }

  private func currentPlan() async throws -> Plan {
    if let plan { return plan }
    let gen = generation
    let loaded: Plan = try await API.get("plans/current", cache: true)
    guard gen == generation else { throw CancellationError() }
    plan = loaded
    Freshness.mark(Freshness.plan)
    return loaded
  }

  /// After a change to the plan: the server has already rebuilt the list, so read it.
  private func reloadGrocery() async {
    guard let plan else { return }
    let gen = generation
    do {
      let list: GroceryList = try await API.get("plans/\(plan.id)/grocery", cache: true)
      guard gen == generation else { return }
      grocery = list.lines
      Freshness.mark(Freshness.grocery)
    } catch {
      fail(error)
    }
  }

  private func patchGroceryFields(_ id: Int, _ body: [String: Any]) async {
    do {
      let _: Ok = try await API.send("grocery/lines/\(id)", method: "PATCH", body: body)
    } catch {
      fail(error)
      await reloadGrocery()
    }
  }

  func loadGroceryPrefs(onlyIfStale: Bool = false) async {
    if onlyIfStale && Freshness.isFresh(Freshness.household) && groceryPrefsLoaded { return }
    let gen = generation
    do {
      let hh: Household = try await API.get("household", cache: true)
      guard gen == generation else { return }
      applyHousehold(hh)
      // Only server data counts: saving grocery settings from a stale saved copy could
      // overwrite stores added on another device.
      groceryPrefsLoaded = true
      Freshness.mark(Freshness.household)
    } catch {
      fail(error)
      groceryPrefsLoaded = false
    }
  }

  private func applyHousehold(_ hh: Household) {
    familyPortions = hh.prefs?.familyPortions
    stores = hh.prefs?.grocery?.stores ?? ShopStore.defaults
    if let found = hh.prefs?.grocery?.aisles, !found.isEmpty {
      aisles = found
    } else {
      aisles = ShopAisle.defaults
    }
    if let v = hh.prefs?.grocery?.groupByStore { groupByStore = v }
    if let v = hh.prefs?.grocery?.showMeals { showMeals = v }
    if let v = hh.prefs?.grocery?.hideChecked { hideChecked = v }
    if let v = hh.prefs?.grocery?.showAisleNums { showAisleNums = v }
    if let v = hh.prefs?.grocery?.showEmoji { showEmoji = v }
  }

  private func patchSlot(
    _ id: Int,
    _ body: [String: Any],
    refreshGrocery: Bool = false,
    reloadOnError: Bool = true
  ) async {
    do {
      let next: PlanSlot = try await API.send("slots/\(id)", method: "PATCH", body: body)
      applySlot(next)
      if refreshGrocery { await reloadGrocery() }
    } catch {
      guard !API.isCancellation(error) else { return }
      let message = error.localizedDescription
      if reloadOnError {
        await loadAll()
      }
      self.error = message
    }
  }

  private func applySlot(_ next: PlanSlot) {
    guard let plan else { return }
    self.plan = plan.withSlots(plan.slots.map { $0.id == next.id ? next : $0 })
  }

  private func applyLocalSlot(id: Int, update: (inout PlanSlot) -> Void) {
    guard let plan else { return }
    var slots = plan.slots
    guard let i = slots.firstIndex(where: { $0.id == id }) else { return }
    update(&slots[i])
    self.plan = plan.withSlots(slots)
  }
}

struct Ok: Decodable {
  let ok: Bool
}

private struct PantryFlagRow: Decodable {
  let have: Bool
  let neverShop: Bool
}

private struct OverrideBox: Decodable {
  struct Item: Decodable {
    let id: Int
  }

  let items: [Item]
}

extension Store {
  func schedule(_ slot: PlanSlot, date: Date) async -> Bool {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.dateFormat = "yyyy-MM-dd"
    error = nil
    await patchSlot(slot.id, ["scheduled_date": f.string(from: date)], reloadOnError: false)
    return error == nil
  }

  func markCooked(ids: Set<Int>) async {
    for slot in (plan?.slots ?? []) where ids.contains(slot.id) && !slot.cooked {
      await patchSlot(slot.id, ["cooked": true])
    }
  }

  func removeSlots(ids: Set<Int>) async {
    for slot in (plan?.slots ?? []) where ids.contains(slot.id) { await removeSlot(slot) }
  }

  func saveDraft(title: String) async {
    guard let plan else { return }
    do {
      let _: Plan = try await API.send(
        "plans", method: "POST",
        body: [
          "title": title.isEmpty ? "Saved plan" : title, "draft": true, "source_plan_id": plan.id,
        ])
    } catch { fail(error) }
  }

  /// "Report a problem with this recipe": why, and the cook's note. True when sent.
  func reportRecipe(_ recipeId: Int, reason: String, note: String) async -> Bool {
    do {
      let _: Ok = try await API.send("recipes/\(recipeId)/report", method: "POST", body: ["reason": reason, "note": note])
      return true
    } catch {
      fail(error)
      return false
    }
  }

  /// "Report this suggestion": the cook's note, saved with why the plan was suggested. True when sent.
  func reportProposal(_ note: String) async -> Bool {
    guard let proposal else { return false }
    do {
      let _: Ok = try await API.send("plans/\(proposal.id)/report", method: "POST", body: ["note": note])
      return true
    } catch {
      proposalError = error.localizedDescription
      return false
    }
  }

  func reviewProposal(_ decision: String) async {
    guard let proposal else { return }
    proposalError = nil
    do {
      let reviewed: Plan = try await API.send("plans/\(proposal.id)/decision/\(decision)", method: "POST", body: [:])
      if decision == "approve" { showingProposal = false; self.proposal = nil; plan = reviewed; await loadGrocery() }
      else {
        self.proposal = reviewed
        await replaceDeclinedProposal()
      }
    } catch { proposalError = error.localizedDescription }
  }

  func replaceDeclinedProposal() async {
    guard let proposal else { return }
    let count = max(1, proposal.suggestedRecipeIds?.count ?? proposal.slots.count)
    let keep = proposal.slots.count > (proposal.suggestedRecipeIds?.count ?? proposal.slots.count)
    if !(await newPlan(meals: count, keepCurrent: keep)) {
      proposalError = error ?? "Couldn't find another plan. Try again or adjust Settings → Filters."
      error = nil
    }
  }

  func resizeProposal(_ count: Int) async {
    guard let proposal else { return }
    proposalError = nil
    do { self.proposal = try await API.send("plans/\(proposal.id)/resize", method: "POST", body: ["meal_count": count]) }
    catch { proposalError = error.localizedDescription }
  }

  func swapProposal(_ slot: PlanSlot, recipeId: Int? = nil) async {
    guard let proposal else { return }
    proposalError = nil
    do { self.proposal = try await API.send("plans/\(proposal.id)/swap/\(slot.id)", method: "POST", body: recipeId.map { ["recipe_id": $0] } ?? [:]) }
    catch { proposalError = error.localizedDescription }
  }

  /// Resume a saved/in-flight suggestion without issuing another request.
  func openSuggestions(keepCurrent: Bool = false) async {
    if generatingProposal { showingProposal = true; return }
    if let proposal, proposal.status == "suggested" {
      let kept = Set(proposal.slots.filter { !(proposal.suggestedRecipeIds ?? []).contains($0.recipeId) }.map(\.recipeId))
      let current = Set(plan?.slots.map(\.recipeId) ?? [])
      if (keepCurrent && kept == current) || (!keepCurrent && kept.isEmpty) {
        proposalError = nil
        showingProposal = true
        return
      }
    }
    let count = keepCurrent ? max(1, 4 - (plan?.slots.count ?? 0)) : 4
    await newPlan(meals: count, keepCurrent: keepCurrent)
  }

  @discardableResult
  func newPlan(source: Int? = nil, meals: Int? = nil, keepCurrent: Bool = false) async -> Bool {
    if meals != nil {
      if generatingProposal { showingProposal = true; return false }
      generatingProposal = true
      proposal = nil
      proposalError = nil
      showingProposal = true
    }
    defer {
      if meals != nil {
        generatingProposal = false
        if let error { proposalError = error }
      }
    }
    do {
      error = nil
      var body: [String: Any] = ["title": "This week"]
      if let source { body["source_plan_id"] = source }
      if let meals {
        do {
          let capabilities: SuggestionCapabilities = try await API.get("suggestions/capabilities", reportErrors: false)
          guard capabilities.version >= 2 && capabilities.review && capabilities.resize && capabilities.swap else {
            error = "Meal planning is being updated. Please try again after the server update."
            return false
          }
        }
        catch APIError.http(let code, _) where code == 404 || code == 405 {
          error = "Meal suggestions need the updated server. You can still use your current plan and choose meals yourself."
          return false
        }
        body["meal_count"] = meals
      }
      body["keep_current"] = keepCurrent
      let created: Plan = try await API.send("plans", method: "POST", body: body)
      if meals != nil {
        guard created.status == "suggested", created.suggestedRecipeIds != nil else {
          error = "The server returned an incompatible plan. Please update the server before requesting suggestions."
          return false
        }
        proposalError = nil
        proposal = created
      } else { plan = created; await loadGrocery() }
      error = nil
      return true
    } catch {
      fail(error)
      return false
    }
  }
}
