import Combine
import Foundation

@MainActor
final class Store: ObservableObject {
  @Published var proposalError: String?
  @Published var proposal: Plan?
  // Loading a saved proposal must not interrupt launch or pull-to-refresh.
  @Published var showingProposal = false
  @Published var plan: Plan?
  @Published var recipes: [RecipeSummary] = []
  @Published var grocery: [GroceryLine] = []
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

  func loadAll() async {
    error = nil
    do {
      async let planBox: Plan = API.get("plans/current")
      async let recipeBox: RecipeList = API.get("recipes", query: ["limit": "400"])
      let plan = try await planBox
      self.plan = plan
      if let pending: PendingSuggestion = try? await API.get("suggestions/current", reportErrors: false), pending.plan?.status == "suggested", pending.plan?.suggestedRecipeIds != nil { proposal = pending.plan }
      recipes = try await recipeBox.recipes
      await reloadGrocery()
      await loadGroceryPrefs()
    } catch {
      fail(error)
    }
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

  func loadHiddenRecipes() async -> [RecipeSummary] {
    do {
      let box: RecipeList = try await API.get("recipes", query: ["limit": "400", "hidden": "true"])
      return box.recipes
    } catch {
      fail(error)
      return []
    }
  }

  func toggleFavorite(_ recipe: RecipeSummary) async {
    let on = !recipe.favorited
    recipes = recipes.map { $0.id == recipe.id ? $0.withFavorited(on) : $0 }
    do {
      let _: RecipeDetail = try await API.send(
        "recipes/\(recipe.id)/favorite",
        method: "PUT",
        body: ["on": on]
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
      return try await API.send("recipes/\(id)/favorite", method: "PUT", body: ["on": on])
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
      return try await API.send("recipes/\(id)/try", method: "PUT", body: ["on": on])
    } catch {
      fail(error)
      return nil
    }
  }

  func hideRecipe(_ id: Int) async {
    _ = await setHidden(id: id, on: true)
  }

  func setHidden(id: Int, on: Bool) async -> RecipeDetail? {
    if on {
      recipes = recipes.filter { $0.id != id }
    }
    do {
      let next: RecipeDetail = try await API.send(
        "recipes/\(id)/hidden",
        method: "PUT",
        body: ["on": on]
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
      await addToWeek(recipeId: recipe.id, servings: recipe.servings)
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

  func loadGrocery() async {
    do {
      let plan = try await currentPlan()
      let list: GroceryList = try await API.send("plans/\(plan.id)/grocery", method: "POST")
      grocery = list.lines
      await loadGroceryPrefs()
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
        body: ["prefs": ["grocery": groceryPrefs]]
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

  func loadPrep() async {
    do {
      let plan = try await currentPlan()
      let box: PrepList = try await API.get("plans/\(plan.id)/prep")
      prepTasks = box.tasks
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

  /// 👍/👎 on a whole prep item, with an optional reason for a 👎. Logged for review.
  func ratePrepTask(_ taskId: Int, _ rating: Int, reason: String = "") async {
    guard let i = prepTasks.firstIndex(where: { $0.id == taskId }) else { return }
    let before = (prepTasks[i].rating, prepTasks[i].reason)
    let why = rating < 0 ? reason : ""
    prepTasks[i].rating = rating
    prepTasks[i].reason = why
    do {
      let _: Ok = try await API.send(
        "prep/\(taskId)/feedback", method: "PUT", body: ["rating": rating, "reason": why])
    } catch {
      if let i = prepTasks.firstIndex(where: { $0.id == taskId }) {
        prepTasks[i].rating = before.0
        prepTasks[i].reason = before.1
      }
      fail(error)
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
    let loaded: Plan = try await API.get("plans/current")
    plan = loaded
    return loaded
  }

  private func reloadGrocery() async {
    guard let plan else { return }
    do {
      let list: GroceryList = try await API.send("plans/\(plan.id)/grocery", method: "POST")
      grocery = list.lines
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

  private func loadGroceryPrefs() async {
    do {
      let hh: Household = try await API.get("household")
      if let found = hh.prefs?.grocery?.stores {
        stores = found
      } else {
        stores = ShopStore.defaults
      }
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
      groceryPrefsLoaded = true
    } catch {
      fail(error)
      groceryPrefsLoaded = false
    }
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
    let count = max(1, proposal.slots.count)
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

  @discardableResult
  func newPlan(source: Int? = nil, meals: Int? = nil, keepCurrent: Bool = false) async -> Bool {
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
        showingProposal = true
      } else { plan = created; await loadGrocery() }
      error = nil
      return true
    } catch {
      fail(error)
      return false
    }
  }
}
