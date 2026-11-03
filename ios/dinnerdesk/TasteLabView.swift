import SwiftUI
import UIKit

// Native Taste Lab (#171). Same flow and rules as the web page (tastelab/web/app.js): swipe
// meals, judge suggested plans, swap a meal, change past votes. Votes are saved to the same
// /api/sessions snapshots, so the website, suggestions and Settings all see them. Filters are
// the household's Settings → Filters, edited with the native FiltersView.

// MARK: - Data

nonisolated struct LabRecipe: Decodable, Identifiable, Hashable {
  /// Taste Lab's id (the archive id as a string). Votes are saved under this id.
  let id: String
  /// The recipe's row id, for To try.
  let recipeId: Int?
  let name: String
  let mins: Int?
  let photo: String?
  let ingredients: [String]

  enum CodingKeys: String, CodingKey { case id, recipeId, name, mins, photo, ingredients }

  init(from decoder: Decoder) throws {
    let c = try decoder.container(keyedBy: CodingKeys.self)
    id = try c.decode(LabID.self, forKey: .id).value
    recipeId = try c.decodeIfPresent(Int.self, forKey: .recipeId)
    name = try c.decode(String.self, forKey: .name)
    mins = try c.decodeIfPresent(Int.self, forKey: .mins)
    photo = try c.decodeIfPresent(String.self, forKey: .photo)
    ingredients = try c.decodeIfPresent([String].self, forKey: .ingredients) ?? []
  }
}

/// Ids arrive as strings or numbers; Taste Lab compares them as strings.
nonisolated private struct LabID: Decodable {
  let value: String
  init(from decoder: Decoder) throws {
    let c = try decoder.singleValueContainer()
    if let s = try? c.decode(String.self) {
      value = s
    } else {
      value = String(try c.decode(Int.self))
    }
  }
}

nonisolated private struct LabCatalog: Decodable { let recipes: [LabRecipe] }

nonisolated private struct LabTaste: Decodable {
  struct Profile: Decodable {
    let diets: [String]?
    let allergens: [String]?
    let dislikes: [String]?
  }
  struct Vote: Decodable {
    let recipeId: LabID
    let liked: Bool
    let plan: Bool?
  }
  let signedIn: Bool?
  let profile: Profile?
  let votes: [Vote]?
}

nonisolated private struct LabSaved: Decodable { let ok: Bool? }

// MARK: - Engine

@MainActor @Observable
final class TasteLab {
  enum Screen { case loading, welcome, swipe, plan, done, empty, history, error }
  enum Phase: String { case free, plans }

  static let seedIDs = ["4664", "768"]
  static let freeMeals = 4
  /// Suggested plans to judge in one session before "You're set" (#13).
  static let planRounds = 3

  private(set) var screen: Screen = .loading
  private(set) var catalog: [LabRecipe] = []
  private(set) var signedIn = false
  private(set) var phase: Phase = .free
  private(set) var deck: [LabRecipe] = []
  private(set) var index = 0
  private(set) var plan: [LabRecipe] = []
  private(set) var round = 0
  private(set) var busy = false
  var error: String?

  // Swap sheet
  var swapFrom: String?
  private(set) var swapChoices: [LabRecipe] = []
  var swapPick: String?

  // Filters (Settings → Filters for this household)
  private var diets: [String] = ["omnivore"]
  private var allergens: [String] = []
  private var dislikes: [String] = []

  private struct Swipe {
    let recipeID: String
    var liked: Bool
    var name: String?
    var phase: String?
    var group: String?
  }
  private struct PlanVerdict {
    let recipeIDs: [String]
    let names: [String]
    let verdict: String
  }
  struct HistoryVote: Identifiable {
    let id: String
    var name: String?
    var liked: Bool
  }

  private var swipes: [Swipe] = []
  private var plans: [PlanVerdict] = []
  private(set) var history: [HistoryVote] = []
  private var historyBack: Screen = .welcome
  private var lastPlan: [String] = []
  private var prior = Set<String>()
  private var priorLikes = Set<String>()
  private var planDown = Set<String>()
  private var shown: [String: Int] = [:]
  private var planHits: [String: Int] = [:]
  private let sessionID = UUID().uuidString.lowercased()
  private var byID: [String: LabRecipe] = [:]

  // MARK: Loading

  func boot(swipe: Bool) async {
    screen = .loading
    error = nil
    do {
      async let catalogCall: LabCatalog = API.get("catalog")
      async let tasteCall: LabTaste = API.get("taste")
      let (cat, taste) = try await (catalogCall, tasteCall)
      catalog = cat.recipes
      byID = Dictionary(cat.recipes.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
      apply(taste)
      if swipe { startFreeSwipes() } else { screen = .welcome }
    } catch {
      if API.isCancellation(error) { return }
      self.error = KitchenAPI.message(error)
      screen = .error
    }
  }

  /// After Edit filters: pick up the new filters and drop meals they now hide.
  func reloadFilters() async {
    guard let taste: LabTaste = try? await API.get("taste") else { return }
    applyProfile(taste.profile)
    deck = Array(deck.prefix(index)) + deck.dropFirst(index).filter { !blocked($0) }
    switch screen {
    case .swipe where index >= deck.count:
      if phase == .free { startFreeSwipes() } else { showPlan() }
    case .plan:
      showPlan(keep: plan.filter { !blocked($0) }.map(\.id))
    default: break
    }
  }

  private func apply(_ taste: LabTaste) {
    signedIn = taste.signedIn ?? false
    prior = []
    priorLikes = []
    history = []
    applyProfile(taste.profile)
    for vote in taste.votes ?? [] {
      let id = vote.recipeId.value
      if id.isEmpty { continue }
      if vote.plan != true { setHistory(id, name: nil, liked: vote.liked) }
      prior.insert(id)
      if vote.liked { priorLikes.insert(id) }
    }
  }

  private func applyProfile(_ profile: LabTaste.Profile?) {
    guard let profile else { return }
    let known = Set(FiltersView.diets)
    let picked = (profile.diets ?? []).filter { known.contains($0) }
    diets = picked.isEmpty ? ["omnivore"] : picked
    allergens = (profile.allergens ?? []).map { $0.lowercased() }.filter { !$0.isEmpty }
    dislikes = (profile.dislikes ?? []).map { $0.lowercased() }.filter { !$0.isEmpty }
  }

  // MARK: Filter rules (same words as tastelab/web/app.js)

  private static let keys: [String: [String]] = [
    "soy": ["soy", "soya", "tofu", "edamame", "tempeh", "miso"],
    "peanut": ["peanut"],
    "tree-nuts": ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "macadamia"],
    "dairy": ["milk", "butter", "cheese", "cream", "yogurt", "yoghurt", "parmesan", "feta", "mozzarella", "cheddar", "whey", "ghee"],
    "egg": ["egg"],
    "gluten": ["wheat", "flour", "bread", "pasta", "spaghetti", "linguine", "penne", "couscous", "panko", "breadcrumb", "soy sauce",
      "buns", " rolls", "pita", "naan", "bagel", "crouton", "cracker", "biscuit", "gnocchi", "fettuccine", "rotini",
      "rigatoni", "farfalle", "orzo", "macaroni", "lasagna", "ziti", "tortellini", "ravioli", "egg noodle",
      "lo mein", "ramen", "udon", "wonton", "barley", "bulgur", "farro", "semolina", "seitan", "hoisin",
      "teriyaki", "stir-fry sauce"],
    "sesame": ["sesame", "tahini"],
    "fish": ["salmon", "tuna", "cod", "halibut", "tilapia", "trout", "anchovy", "fish"],
    "shellfish": ["shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster", "scallop"],
    "cilantro": ["cilantro", "coriander"],
    "mushrooms": ["mushroom"],
    "onions": ["onion"],
    "bell peppers": ["bell pepper"],
    "olives": ["olive"],
    "goat cheese": ["goat cheese", "chèvre", "chevre"],
    "nuts": ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "peanut"],
    "beans": ["black bean", "kidney bean", "pinto bean", "white bean", "chickpea", "garbanzo", "lentil", "cannellini"],
    "tofu": ["tofu"],
    "eggplant": ["eggplant"],
    "brussels sprouts": ["brussels sprout", "brussel sprout"],
    "coconut": ["coconut"],
    "meat": ["chicken", "beef", "pork", "turkey", "lamb", "bacon", "sausage", "steak", "ham", "prosciutto"],
    "spicy": ["spicy", "jalapeño", "jalapeno", "sriracha", "chili flake", "cayenne", "hot sauce"],
  ]

  private var blobs: [String: String] = [:]

  private func text(_ r: LabRecipe) -> String {
    if let hit = blobs[r.id] { return hit }
    let ings = r.ingredients.filter { $0.range(of: "chicken or vegetable broth", options: .caseInsensitive) == nil }
    let blob = "\(r.name) \(ings.joined(separator: " | "))".lowercased()
    blobs[r.id] = blob
    return blob
  }

  private func hits(_ r: LabRecipe, _ words: [String]) -> Bool {
    let blob = text(r)
    return words.contains { word in
      if word == "egg" {
        return blob.range(of: "(^|[^a-z])eggs?([^a-z]|$)", options: .regularExpression) != nil
      }
      return blob.contains(word)
    }
  }

  private func words(_ id: String) -> [String] { Self.keys[id] ?? [id] }

  func blocked(_ r: LabRecipe) -> Bool {
    if allergens.contains(where: { hits(r, words($0)) }) { return true }
    let k = Self.keys
    let meat = k["meat"]!, fish = k["fish"]!, shellfish = k["shellfish"]!, dairy = k["dairy"]!
    if diets.contains("vegan"), hits(r, meat + fish + shellfish + dairy + k["egg"]! + ["honey"]) { return true }
    if diets.contains("vegetarian"), hits(r, meat + fish + shellfish) { return true }
    if diets.contains("pescatarian"), hits(r, meat) { return true }
    if diets.contains("gluten-free"), hits(r, k["gluten"]!) { return true }
    if diets.contains("dairy-free"), hits(r, dairy) { return true }
    return dislikes.contains { hits(r, words($0)) }
  }

  private func rejected(_ id: String) -> Bool {
    if planDown.contains(id) { return true }
    if swipes.contains(where: { $0.recipeID == id && !$0.liked }) { return true }
    return prior.contains(id) && !priorLikes.contains(id)
  }

  private func eligible() -> [LabRecipe] { catalog.filter { !blocked($0) && !rejected($0.id) } }
  private func stillOpen(_ r: LabRecipe) -> Bool { shown[r.id, default: 0] < 3 }
  private func openPool() -> [LabRecipe] { eligible().filter(stillOpen) }
  private func planPool() -> [LabRecipe] { openPool().filter { planHits[$0.id, default: 0] < 2 } }

  private func unswiped() -> [LabRecipe] {
    let swiped = Set(swipes.map(\.recipeID))
    return openPool().filter { !swiped.contains($0.id) && !prior.contains($0.id) }
  }

  private func bumpShown(_ rows: [LabRecipe]) {
    for r in rows { shown[r.id, default: 0] += 1 }
  }

  private func bumpPlans(_ rows: [LabRecipe]) {
    bumpShown(rows)
    for r in rows { planHits[r.id, default: 0] += 1 }
  }

  private func likedMeals() -> [LabRecipe] {
    var ids: [String] = Array(priorLikes)
    ids += swipes.filter(\.liked).map(\.recipeID)
    ids += plans.filter { $0.verdict == "up" }.flatMap(\.recipeIDs)
    var seen = Set<String>()
    return ids.filter { seen.insert($0).inserted }
      .compactMap { byID[$0] }
      .filter { !blocked($0) && !rejected($0.id) }
  }

  private func take(_ n: Int, _ lists: [[LabRecipe]], hold: [String] = []) -> [LabRecipe] {
    var seen = Set(hold)
    var out: [LabRecipe] = []
    for list in lists {
      for r in list.shuffled() {
        if out.count >= n { return out }
        if seen.contains(r.id) { continue }
        out.append(r)
        seen.insert(r.id)
      }
    }
    return out
  }

  private func pickPlan(_ n: Int, hold: [String]) -> [LabRecipe] {
    let last = Set(lastPlan)
    let pool = planPool()
    let fresh = pool.filter { !last.contains($0.id) }
    let likes = likedMeals().filter { planHits[$0.id, default: 0] < 2 }
    return take(n, [fresh, likes, pool], hold: hold)
  }

  var counts: (likes: Int, passes: Int) {
    var vote: [String: Bool] = [:]
    for id in prior { vote[id] = priorLikes.contains(id) }
    for s in swipes { vote[s.recipeID] = s.liked }
    let likes = vote.values.filter { $0 }.count
    return (likes, vote.count - likes)
  }

  var heroMeals: [LabRecipe] {
    var seen = Set<String>()
    var out: [LabRecipe] = []
    for r in Self.seedIDs.compactMap({ byID[$0] }) + catalog {
      if r.photo == nil || seen.contains(r.id) || blocked(r) { continue }
      seen.insert(r.id)
      out.append(r)
      if out.count == 3 { break }
    }
    return out
  }

  func recipe(_ id: String) -> LabRecipe? { byID[id] }

  // MARK: Saving

  private func record() -> [String: Any] {
    [
      "id": sessionID,
      "created_at": ISO8601DateFormatter().string(from: Date()),
      "profile": ["diets": diets, "allergens": allergens, "dislikes": dislikes],
      "swipes": swipes.map { s -> [String: Any] in
        var row: [String: Any] = ["recipe_id": s.recipeID, "liked": s.liked]
        if let name = s.name { row["name"] = name }
        if let phase = s.phase { row["phase"] = phase }
        row["group"] = s.group ?? NSNull()
        return row
      },
      "plans": plans.map {
        ["recipe_ids": $0.recipeIDs, "names": $0.names, "verdict": $0.verdict, "swap": [String]()]
      },
    ]
  }

  private func save() async throws {
    let _: LabSaved = try await API.send(
      "sessions", method: "POST", body: ["id": sessionID, "kind": "snapshot", "body": record()])
    error = nil
  }

  /// One action at a time, like the web page; a failure shows in the banner.
  private func run(_ work: @escaping () async throws -> Void) {
    guard !busy else { return }
    busy = true
    Task {
      defer { busy = false }
      do { try await work() } catch {
        if !API.isCancellation(error) { self.error = KitchenAPI.message(error) }
      }
    }
  }

  private func remember(_ id: String, liked: Bool) {
    prior.insert(id)
    if liked { priorLikes.insert(id) } else { priorLikes.remove(id) }
  }

  private func setHistory(_ id: String, name: String?, liked: Bool) {
    if let i = history.firstIndex(where: { $0.id == id }) {
      history[i].liked = liked
      if let name { history[i].name = name }
    } else {
      history.append(HistoryVote(id: id, name: name, liked: liked))
    }
  }

  // MARK: Actions

  func startFreeSwipes() {
    error = nil
    round = 0
    phase = .free
    deck = take(Self.freeMeals, [unswiped()])
    bumpShown(deck)
    index = 0
    screen = deck.isEmpty ? .empty : .swipe
  }

  func startPlans() {
    error = nil
    phase = .plans
    round = 0
    showPlan()
  }

  private func showPlan(keep: [String] = []) {
    let kept = keep.compactMap { byID[$0] }.filter { !blocked($0) && !rejected($0.id) }
    let added = pickPlan(4 - kept.count, hold: kept.map(\.id))
    bumpPlans(added)
    plan = Array((kept + added).prefix(4))
    lastPlan = plan.map(\.id)
    closeSwap()
    screen = plan.isEmpty ? .empty : .plan
  }

  func decide(_ liked: Bool) {
    guard !busy, screen == .swipe, index < deck.count else { return }
    let rec = deck[index]
    busy = true
    swipes.append(Swipe(recipeID: rec.id, liked: liked, name: rec.name, phase: phase.rawValue))
    index += 1
    Task {
      defer { busy = false }
      do {
        try await save()
      } catch {
        swipes.removeLast()
        index -= 1
        self.error = KitchenAPI.message(error)
        return
      }
      setHistory(rec.id, name: rec.name, liked: liked)
      remember(rec.id, liked: liked)
      if index >= deck.count {
        if phase == .free { screen = .done } else { showPlan() }
      }
    }
  }

  func judgePlan(_ verdict: String) {
    let ids = plan.map(\.id)
    run { [self] in
      plans.append(PlanVerdict(recipeIDs: ids, names: plan.map(\.name), verdict: verdict))
      do { try await save() } catch {
        plans.removeLast()
        throw error
      }
      for id in ids {
        let swiped = swipes.contains { $0.recipeID == id }
        if verdict == "down" {
          planDown.insert(id)
          if !swiped { remember(id, liked: false) }
        } else if !swiped {
          remember(id, liked: true)
        }
      }
      round += 1
      if verdict == "down" || (round < Self.planRounds && !planPool().isEmpty) {
        showPlan()
      } else {
        screen = .done
      }
    }
  }

  func finish() {
    run { [self] in
      try await save()
      screen = .done
    }
  }

  func openHistory() {
    historyBack = screen
    error = nil
    screen = .history
  }

  func changeHistory(_ id: String, liked: Bool) {
    guard let old = history.first(where: { $0.id == id }), old.liked != liked else { return }
    run { [self] in
      let previous = swipes
      var updated = swipes.first { $0.recipeID == id } ?? Swipe(recipeID: id, liked: liked, name: old.name)
      updated.liked = liked
      swipes = swipes.filter { $0.recipeID != id } + [updated]
      do { try await save() } catch {
        swipes = previous
        throw error
      }
      setHistory(id, name: nil, liked: liked)
      planDown.remove(id)
      remember(id, liked: liked)
    }
  }

  /// In-lab back: history returns where it came from; other screens go to the start page.
  /// Returns false on the start page so the caller leaves Taste Lab.
  func back() -> Bool {
    if swapFrom != nil {
      closeSwap()
      return true
    }
    switch screen {
    case .welcome, .loading, .error: return false
    case .history: screen = historyBack
    default: screen = .welcome
    }
    error = nil
    return true
  }

  // MARK: Swap

  private func swapPool() -> [LabRecipe] {
    let hold = Set(plan.map(\.id))
    return planPool().filter { !hold.contains($0.id) }
  }

  func openSwap(_ id: String) {
    let choices = Array(swapPool().shuffled().prefix(4))
    guard !choices.isEmpty else {
      error = "Nothing else fits these filters."
      return
    }
    error = nil
    swapFrom = id
    swapChoices = choices
    swapPick = nil
  }

  func moreSwaps() {
    let previous = Set(swapChoices.map(\.id))
    let choices = Array(swapPool().filter { !previous.contains($0.id) }.shuffled().prefix(4))
    if choices.isEmpty {
      error = "No more matching options. Go back and edit filters or choose your own meals in Recipes."
    } else {
      swapChoices = choices
      swapPick = nil
    }
  }

  func closeSwap() {
    swapFrom = nil
    swapChoices = []
    swapPick = nil
  }

  func applySwap() {
    guard let from = swapFrom, let pick = swapPick, let next = byID[pick] else { return }
    run { [self] in
      let previous = plan
      plan = plan.map { $0.id == from ? next : $0 }
      lastPlan = plan.map(\.id)
      bumpPlans([next])
      do { try await save() } catch {
        plan = previous
        lastPlan = previous.map(\.id)
        throw error
      }
      closeSwap()
    }
  }
}

// MARK: - View

struct TasteLabView: View {
  /// Open straight to swiping (the Plan tab's "Improve suggestions").
  var swipe = false
  @State private var lab = TasteLab()
  @State private var editingFilters = false
  @Environment(\.dismiss) private var dismiss

  var body: some View {
    content
      .frame(maxWidth: .infinity, maxHeight: .infinity)
      .background(Theme.bg)
      .background(ContentPopBlocker())
      .navigationTitle(title)
      .navigationBarTitleDisplayMode(.inline)
      .navigationBarBackButtonHidden(inLab)
      .toolbar {
        if inLab {
          ToolbarItem(placement: .topBarLeading) {
            Button {
              if !lab.back() { dismiss() }
            } label: {
              Image(systemName: "chevron.backward")
            }
            .accessibilityLabel("Back")
          }
        }
      }
      .navigationDestination(isPresented: $editingFilters) { FiltersView() }
      .onChange(of: editingFilters) { _, open in
        if !open { Task { await lab.reloadFilters() } }
      }
      .task { if case .loading = lab.screen { await lab.boot(swipe: swipe) } }
      .sheet(isPresented: swapShown) { SwapSheet(lab: lab) }
  }

  private var inLab: Bool {
    switch lab.screen {
    case .welcome, .loading, .error: false
    default: true
    }
  }

  private var swapShown: Binding<Bool> {
    Binding(get: { lab.swapFrom != nil }, set: { if !$0 { lab.closeSwap() } })
  }

  private var title: String {
    switch lab.screen {
    case .swipe: "Keep going"
    case .plan: "Suggested dinners"
    case .history: "Swipe history"
    case .empty: lab.phase == .free ? "No new meals to swipe" : "No meals match"
    default: "Taste Lab"
    }
  }

  @ViewBuilder private var content: some View {
    switch lab.screen {
    case .loading: ProgressView()
    case .error: errorView
    case .welcome: welcome
    case .swipe: swipeView
    case .plan: planView
    case .done: doneView
    case .empty: emptyView
    case .history: historyView
    }
  }

  // MARK: Screens

  private var errorView: some View {
    VStack(spacing: 12) {
      EmptyState(
        title: "Taste Lab didn't load", message: lab.error ?? "Something went wrong.",
        systemImage: "wifi.exclamationmark")
      LabButton("Try again") { Task { await lab.boot(swipe: swipe) } }
        .frame(maxWidth: 240)
    }
    .padding(20)
  }

  private var banner: some View {
    Group {
      if let error = lab.error { ErrorBanner(message: error) }
    }
  }

  private var links: some View {
    HStack(spacing: 20) {
      Button("Edit filters") { editingFilters = true }
      Button("Swipe history") { lab.openHistory() }
    }
    .font(Theme.subtitle.weight(.semibold))
    .foregroundStyle(Theme.accent)
    .frame(maxWidth: .infinity)
    .frame(minHeight: 44)
  }

  private var welcome: some View {
    let counts = lab.counts
    let started = counts.likes + counts.passes > 0
    return ScrollView {
      VStack(alignment: .leading, spacing: 16) {
        HeroMosaic(meals: lab.heroMeals)
        Text(started ? "Pick up where you left off." : "What do you like to cook?")
          .font(Theme.tourTitle)
          .foregroundStyle(Theme.ink)
        Text(
          started
            ? "\(counts.likes) liked · \(counts.passes) passed. A pass won’t be suggested again."
            : "Swipe individual meals or review suggested dinner plans. Choose either to get started."
        )
        .font(Theme.body)
        .foregroundStyle(Theme.muted)
        banner
        if lab.catalog.isEmpty {
          Text("No meals with photos are ready to swipe yet.")
            .font(Theme.body).foregroundStyle(Theme.muted)
        } else {
          VStack(spacing: 10) {
            LabButton("Swipe meals") { lab.startFreeSwipes() }
            LabButton("Suggest plans", primary: false) { lab.startPlans() }
          }
        }
        links
        Text(
          lab.signedIn
            ? "Likes, passes, and filters are saved for your household and used to suggest meals."
            : "You can use every feature as a guest. Create an account in Settings to protect your data; reinstalling the app can lose access."
        )
        .font(Theme.subtitle)
        .foregroundStyle(Theme.muted)
      }
      .padding(20)
    }
  }

  private var swipeView: some View {
    VStack(spacing: 14) {
      Text("\(min(lab.index + 1, lab.deck.count)) / \(lab.deck.count)")
        .font(Theme.count)
        .foregroundStyle(Theme.muted)
        .monospacedDigit()
      banner
      SwipeStack(lab: lab)
        .frame(maxHeight: .infinity)
      HStack(spacing: 36) {
        CircleButton(systemImage: "xmark", tint: Theme.muted, label: "Pass") { lab.decide(false) }
        CircleButton(systemImage: "heart.fill", tint: Theme.accent, label: "Like") { lab.decide(true) }
      }
      .disabled(lab.busy)
      links
      Button("Done for now") { lab.finish() }
        .font(Theme.subtitle.weight(.semibold))
        .foregroundStyle(Theme.muted)
    }
    .padding(.horizontal, 20)
    .padding(.vertical, 12)
  }

  private var planView: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 14) {
        Text("Plan \(min(lab.round + 1, TasteLab.planRounds)) of \(TasteLab.planRounds)")
          .font(Theme.count).foregroundStyle(Theme.muted)
          .frame(maxWidth: .infinity, alignment: .trailing)
        if lab.swapFrom == nil { banner }
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 12) {
          ForEach(lab.plan) { r in
            Button { lab.openSwap(r.id) } label: { PlanMealCard(recipe: r) }
              .buttonStyle(.plain)
              .accessibilityLabel("Swap \(r.name)")
              .overlay(alignment: .topLeading) {
                SaveForLater(recipeID: r.recipeId, name: r.name, small: true).padding(14)
              }
          }
        }
        HStack(spacing: 10) {
          LabButton("Not for us", systemImage: "hand.thumbsdown", primary: false) { lab.judgePlan("down") }
          LabButton("This plan works", systemImage: "hand.thumbsup") { lab.judgePlan("up") }
        }
        .disabled(lab.busy)
        links
        Button("Done for now") { lab.finish() }
          .font(Theme.subtitle.weight(.semibold))
          .foregroundStyle(Theme.muted)
          .frame(maxWidth: .infinity)
      }
      .padding(20)
    }
  }

  private var doneView: some View {
    let counts = lab.counts
    return VStack(alignment: .leading, spacing: 16) {
      Text("You're set.").font(Theme.tourTitle).foregroundStyle(Theme.ink)
      Text("\(counts.likes) liked · \(counts.passes) passed. When you make a meal plan, suggestions follow this.")
        .font(Theme.body).foregroundStyle(Theme.muted)
      banner
      LabButton("Keep swiping") { lab.startFreeSwipes() }
      LabButton("Suggest plans", primary: false) { lab.startPlans() }
      Button("Done") { dismiss() }
        .font(Theme.action).foregroundStyle(Theme.accent)
        .frame(maxWidth: .infinity, minHeight: 44)
      Spacer()
    }
    .padding(20)
  }

  private var emptyView: some View {
    let free = lab.phase == .free
    return ScrollView {
      VStack(alignment: .leading, spacing: 14) {
        banner
        Text(free ? "No new meals to swipe" : "No more matching dinners")
          .font(Theme.title).foregroundStyle(Theme.ink)
        Text(
          free
            ? "You’ve reached the end of new meals that fit your filters. Review suggested plans or edit filters to find more meals."
            : "You’ve reached the end of meals that fit your filters and passes. Edit your filters to look for more options, or return to Recipes to choose meals yourself."
        )
        .font(Theme.body).foregroundStyle(Theme.muted)
        if free { LabButton("Suggest plans", primary: false) { lab.startPlans() } }
        Text("Your allergies and passed meals stay saved.")
          .font(Theme.subtitle).foregroundStyle(Theme.muted)
        LabButton("Edit filters") { editingFilters = true }
      }
      .padding(20)
    }
  }

  private var historyView: some View {
    ScrollView {
      LazyVStack(alignment: .leading, spacing: 12) {
        Text("Change your likes and passes to improve future suggestions.")
          .font(Theme.subtitle).foregroundStyle(Theme.muted)
        banner
        if lab.history.isEmpty {
          EmptyState(
            title: "No swiped meals yet", message: "Swipe meals to start your history.",
            systemImage: "hand.draw")
        }
        ForEach(lab.history.reversed()) { vote in
          let recipe = lab.recipe(vote.id)
          let name = recipe?.name ?? vote.name ?? "Recipe no longer available"
          HStack(spacing: 12) {
            RecipePhoto(path: recipe?.photo)
            VStack(alignment: .leading, spacing: 8) {
              HStack(alignment: .top) {
                Text(name).font(Theme.rowTitle).foregroundStyle(Theme.ink).lineLimit(2)
                Spacer(minLength: 4)
                SaveForLater(recipeID: recipe?.recipeId, name: name, small: true)
              }
              HStack(spacing: 8) {
                Button { lab.changeHistory(vote.id, liked: true) } label: {
                  KitchenChip(text: "👍 Like", count: nil, selected: vote.liked)
                }
                .accessibilityLabel("Like \(name)")
                .accessibilityAddTraits(vote.liked ? .isSelected : [])
                Button { lab.changeHistory(vote.id, liked: false) } label: {
                  KitchenChip(text: "👎 Pass", count: nil, selected: !vote.liked)
                }
                .accessibilityLabel("Pass \(name)")
                .accessibilityAddTraits(vote.liked ? [] : .isSelected)
              }
              .buttonStyle(.plain)
              .disabled(lab.busy)
            }
          }
          .padding(12)
          .background(Theme.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
          .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Theme.line))
        }
      }
      .padding(20)
    }
  }
}

// MARK: - Pieces

private struct LabButton: View {
  let title: String
  var systemImage: String?
  var primary = true
  let action: () -> Void

  init(_ title: String, systemImage: String? = nil, primary: Bool = true, action: @escaping () -> Void) {
    self.title = title
    self.systemImage = systemImage
    self.primary = primary
    self.action = action
  }

  var body: some View {
    Button(action: action) {
      HStack(spacing: 8) {
        if let systemImage { Image(systemName: systemImage) }
        Text(title).lineLimit(1).minimumScaleFactor(0.8)
      }
      .font(Theme.action)
      .foregroundStyle(primary ? Theme.bg : Theme.ink)
      .frame(maxWidth: .infinity, minHeight: 50)
      .background(primary ? Theme.ink : Theme.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
      .overlay(
        RoundedRectangle(cornerRadius: 14, style: .continuous)
          .strokeBorder(primary ? Color.clear : Theme.line)
      )
    }
    .buttonStyle(.plain)
  }
}

private struct CircleButton: View {
  let systemImage: String
  let tint: Color
  let label: String
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      Image(systemName: systemImage)
        .font(.system(size: 26, weight: .bold))
        .foregroundStyle(tint)
        .frame(width: 68, height: 68)
        .background(Theme.surface, in: Circle())
        .overlay(Circle().strokeBorder(Theme.line))
        .shadow(color: Theme.ink.opacity(0.08), radius: 8, y: 3)
    }
    .buttonStyle(.plain)
    .accessibilityLabel(label)
  }
}

/// Save a Taste Lab meal for later: adds it to the household's To try list (Recipes → To try).
private struct SaveForLater: View {
  let recipeID: Int?
  let name: String
  var small = false
  @EnvironmentObject private var store: Store
  /// Set after a tap, so the icon changes before the save returns (and for meals not in
  /// store.recipes yet).
  @State private var picked: Bool?
  @State private var saving = false

  private var on: Bool {
    picked ?? store.recipes.first { $0.id == recipeID }?.toTry ?? false
  }

  var body: some View {
    if let recipeID {
      Button {
        let next = !on
        picked = next
        saving = true
        Task {
          let saved = await store.setTryLater(id: recipeID, on: next)
          if saved == nil { picked = !next }
          saving = false
        }
      } label: {
        Image(systemName: on ? "bookmark.fill" : "bookmark")
          .font(.system(size: small ? 15 : 20, weight: .semibold))
          .foregroundStyle(on ? Theme.accent : Theme.ink)
          .frame(width: small ? 32 : 44, height: small ? 32 : 44)
          .background(Theme.surface.opacity(0.94), in: Circle())
          .shadow(color: Theme.ink.opacity(0.12), radius: 4, y: 1)
          .frame(minWidth: 44, minHeight: 44)
          .contentShape(Rectangle())
      }
      .buttonStyle(.plain)
      .disabled(saving)
      .accessibilityLabel(on ? "Saved to To try: \(name)" : "Save \(name) to To try")
      .accessibilityHint(on ? "Removes it from To try" : "Find it later in Recipes, To try")
    }
  }
}

/// A photo that fills whatever frame it's given (RecipePhoto is square).
private struct FillPhoto: View {
  let path: String?
  let name: String
  @State private var image: UIImage?

  var body: some View {
    GeometryReader { geo in
      Group {
        if let image {
          Image(uiImage: image).resizable().scaledToFill()
        } else {
          ZStack {
            Theme.line
            Text(String(name.prefix(1)))
              .font(Theme.recipeTitle)
              .foregroundStyle(Theme.muted)
          }
        }
      }
      .frame(width: geo.size.width, height: geo.size.height)
      .clipped()
    }
    .accessibilityHidden(true)
    .task(id: path) {
      guard let url = API.photoURL(path) else { return }
      if let hit = PhotoCache.memoryImage(for: url) {
        image = hit
        return
      }
      image = try? await PhotoCache.image(for: url)
    }
  }
}

private struct HeroMosaic: View {
  let meals: [LabRecipe]

  var body: some View {
    if !meals.isEmpty {
      HStack(spacing: 8) {
        FillPhoto(path: meals[0].photo, name: meals[0].name)
          .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        if meals.count > 1 {
          VStack(spacing: 8) {
            ForEach(meals.dropFirst()) { r in
              FillPhoto(path: r.photo, name: r.name)
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
          }
          .frame(maxWidth: 130)
        }
      }
      .frame(height: 220)
    }
  }
}

private struct SwipeCard: View {
  let recipe: LabRecipe
  var drag: CGFloat = 0

  var body: some View {
    // Same pieces as the plan cards: the shared square photo, then the name and time.
    VStack(alignment: .leading, spacing: 8) {
      RecipePhoto(path: recipe.photo, fill: true)
        .overlay(alignment: .topLeading) {
          SaveForLater(recipeID: recipe.recipeId, name: recipe.name, small: true).padding(8)
        }
        .overlay {
          ZStack {
            stamp("LIKE", color: Theme.ok).opacity(Double(min(1, max(0, drag / 90))))
              .rotationEffect(.degrees(-12))
            stamp("PASS", color: Theme.danger).opacity(Double(min(1, max(0, -drag / 90))))
              .rotationEffect(.degrees(12))
          }
          .allowsHitTesting(false)
        }
      Text(recipe.name)
        .font(Theme.mealName)
        .foregroundStyle(Theme.ink)
        .lineLimit(2, reservesSpace: true)
        .multilineTextAlignment(.leading)
      if let mins = recipe.mins {
        Text("\(mins) min").font(Theme.recipeCardServing).foregroundStyle(Theme.muted)
      }
    }
    .padding(10)
    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Theme.line))
    .shadow(color: Theme.ink.opacity(0.08), radius: 10, y: 4)
  }

  private func stamp(_ text: String, color: Color) -> some View {
    Text(text)
      .font(Theme.title)
      .foregroundStyle(color)
      .padding(.horizontal, 12)
      .padding(.vertical, 4)
      .background(Color.white.opacity(0.85), in: RoundedRectangle(cornerRadius: 8))
      .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(color, lineWidth: 3))
  }
}

private struct SwipeStack: View {
  let lab: TasteLab
  @State private var drag: CGFloat = 0
  @ScaledMetric(relativeTo: .body) private var textRoom: CGFloat = 96

  var body: some View {
    // Keep the photo square: the card is as wide as the space allows, but no wider than the
    // height left after the name and time below the photo.
    GeometryReader { geo in
      let width = min(geo.size.width, max(180, geo.size.height - textRoom))
      cards
        .frame(width: width)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
  }

  private var cards: some View {
    ZStack {
      if lab.index + 1 < lab.deck.count {
        SwipeCard(recipe: lab.deck[lab.index + 1])
          .scaleEffect(0.95)
          .offset(y: 10)
          .allowsHitTesting(false)
          .accessibilityHidden(true)
      }
      if lab.index < lab.deck.count {
        let current = lab.deck[lab.index]
        SwipeCard(recipe: current, drag: drag)
          .id(current.id)
          .offset(x: drag, y: drag * 0.08)
          .rotationEffect(.degrees(Double(drag / 18)))
          .gesture(
            DragGesture()
              .onChanged { drag = $0.translation.width }
              .onEnded { value in
                let dx = value.translation.width
                if dx > 88 {
                  lab.decide(true)
                } else if dx < -88 {
                  lab.decide(false)
                }
                withAnimation(.spring(duration: 0.25)) { drag = 0 }
              }
          )
          // VoiceOver reads the name and time, reaches the save button, and uses the Like and
          // Pass buttons below the card instead of dragging.
          .accessibilityElement(children: .contain)
      }
    }
    .onChange(of: lab.index) { drag = 0 }
  }
}

private struct PlanMealCard: View {
  let recipe: LabRecipe

  var body: some View {
    VStack(alignment: .leading, spacing: 8) {
      RecipePhoto(path: recipe.photo, fill: true)
        .overlay(alignment: .topTrailing) {
          Image(systemName: "arrow.left.arrow.right")
            .font(.system(size: 13, weight: .bold))
            .foregroundStyle(Theme.ink)
            .padding(7)
            .background(Theme.surface.opacity(0.92), in: Circle())
            .padding(8)
            .accessibilityHidden(true)
        }
      Text(recipe.name)
        .font(Theme.recipeCardName)
        .foregroundStyle(Theme.ink)
        .lineLimit(2, reservesSpace: true)
        .multilineTextAlignment(.leading)
      if let mins = recipe.mins {
        Text("\(mins) min").font(Theme.recipeCardServing).foregroundStyle(Theme.muted)
      }
    }
    .padding(10)
    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Theme.line))
  }
}

private struct SwapSheet: View {
  @Bindable var lab: TasteLab

  var body: some View {
    NavigationStack {
      ScrollView {
        VStack(alignment: .leading, spacing: 10) {
          if let error = lab.error { ErrorBanner(message: error) }
          ForEach(lab.swapChoices) { r in
            let on = lab.swapPick == r.id
            Button { lab.swapPick = r.id } label: {
              HStack(spacing: 12) {
                RecipePhoto(path: r.photo)
                VStack(alignment: .leading, spacing: 2) {
                  Text(r.name).font(Theme.rowTitle).foregroundStyle(Theme.ink)
                    .multilineTextAlignment(.leading)
                  if let mins = r.mins {
                    Text("\(mins) min").font(Theme.subtitle).foregroundStyle(Theme.muted)
                  }
                }
                Spacer(minLength: 0)
                Image(systemName: on ? "checkmark.circle.fill" : "circle")
                  .font(.title3)
                  .foregroundStyle(on ? Theme.accent : Theme.line)
              }
              .padding(10)
              .background(Theme.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
              .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                  .strokeBorder(on ? Theme.accent : Theme.line, lineWidth: on ? 2 : 1)
              )
            }
            .buttonStyle(.plain)
            .accessibilityAddTraits(on ? .isSelected : [])
          }
        }
        .padding(20)
      }
      .safeAreaInset(edge: .bottom) {
        HStack(spacing: 10) {
          LabButton("More options", primary: false) { lab.moreSwaps() }
          LabButton("Save swap") { lab.applySwap() }
            .disabled(lab.swapPick == nil || lab.busy)
            .opacity(lab.swapPick == nil ? 0.5 : 1)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(Theme.bg)
      }
      .background(Theme.bg)
      .navigationTitle("Replace \(lab.swapFrom.flatMap { lab.recipe($0)?.name } ?? "this meal")")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button("Cancel") { lab.closeSwap() }
        }
      }
    }
    .presentationDetents([.medium, .large])
  }
}

/// iOS 26 pops the screen on a right swipe anywhere in the content, which eats the card's
/// like swipe. Keep only the edge swipe while Taste Lab is on screen.
private struct ContentPopBlocker: UIViewRepresentable {
  func makeUIView(context: Context) -> BlockerView { BlockerView() }
  func updateUIView(_ view: BlockerView, context: Context) {}

  final class BlockerView: UIView {
    private weak var nav: UINavigationController?

    override func didMoveToWindow() {
      super.didMoveToWindow()
      guard #available(iOS 26, *) else { return }
      if window == nil {
        nav?.interactiveContentPopGestureRecognizer?.isEnabled = true
        nav = nil
        return
      }
      var responder: UIResponder? = self
      while let next = responder?.next, !(next is UINavigationController) { responder = next }
      nav = responder?.next as? UINavigationController
      nav?.interactiveContentPopGestureRecognizer?.isEnabled = false
    }
  }
}
