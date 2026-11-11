import Foundation

// Phone app only (excluded from the watch target, like PantryMatch.swift, which it uses).

/// Search filter chips on the Recipes screen. Same keys and labels as web and Android.
nonisolated enum RecipeSearchFilter: String, CaseIterable, Identifiable, Sendable {
  case fav, tryLater, popular, quick, pantry, hidden, comingSoon, reviewed
  var id: String { rawValue }

  var label: String {
    switch self {
    case .fav: "Your favorites"
    case .tryLater: "To try"
    case .popular: "Popular"
    case .quick: "Quick"
    case .pantry: "Uses pantry"
    case .hidden: "Hidden"
    case .comingSoon: "Coming soon"
    case .reviewed: "Reviewed"
    }
  }
}

/// The recipe lists every Recipes screen shows, built one way. Web (recipeCollections.js) and
/// Android (RecipeCollections.kt) have the same class with the same members and rules.
/// Coming-soon recipes (our photo, steps not written yet) stay out of every themed list; they
/// have their own list and come last in `all`.
nonisolated struct RecipeCollections: Sendable {
  let ready: [RecipeSummary]
  let comingSoon: [RecipeSummary]
  let favorites: [RecipeSummary]
  let toTry: [RecipeSummary]
  let mine: [RecipeSummary]
  let meals: [RecipeSummary]
  let sauces: [RecipeSummary]
  let popular: [RecipeSummary]
  let simple: [RecipeSummary]
  /// At most 8 ingredients besides staples (salt, oil, water).
  let budget: [RecipeSummary]
  /// Uses what's in the kitchen's pantry (PantryMatch). Empty until the pantry is loaded.
  let pantry: [RecipeSummary]
  /// Every meal A–Z, then the coming-soon ones.
  let all: [RecipeSummary]

  /// Salt, oil and water don't count toward a recipe's ingredient count.
  static let staples: Set<String> = [
    "salt", "black pepper", "pepper", "olive oil", "extra virgin olive oil", "vegetable oil",
    "neutral cooking oil", "canola oil", "oil", "water", "cooking spray",
  ]

  static func isBudget(_ recipe: RecipeSummary) -> Bool {
    let n = recipe.ingredients.map(PantryMatch.norm).filter { !$0.isEmpty && !staples.contains($0) }.count
    return n > 0 && n <= 8
  }

  init(_ recipes: [RecipeSummary], pantryHave: Set<String> = []) {
    let byName: (RecipeSummary, RecipeSummary) -> Bool = {
      $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending
    }
    ready = recipes.filter { !$0.comingSoon }
    comingSoon = recipes.filter(\.comingSoon).sorted(by: byName)
    favorites = ready.filter(\.favorited)
    toTry = ready.filter(\.toTry)
    mine = ready.filter { !$0.catalog }
    meals = ready.filter(\.isMeal)
    sauces = ready.filter(\.isExtra)
    popular = meals.filter { $0.tags.contains("popular") }
    simple = meals.filter { ($0.cookingMinutes ?? 99) <= 20 }
    budget = meals.filter(Self.isBudget)
    pantry = meals.filter { PantryMatch.uses($0.ingredients, have: pantryHave) }
    all = meals.sorted(by: byName) + comingSoon
  }

  /// `rows` narrowed by the search filters that are on. `.hidden` picks the source list, so the
  /// screen handles that one.
  func filter(_ rows: [RecipeSummary], _ filters: Set<RecipeSearchFilter>, pantryHave: Set<String>)
    -> [RecipeSummary]
  {
    var out = filters.contains(.comingSoon) ? rows.filter(\.comingSoon) : rows
    if filters.contains(.fav) { out = out.filter(\.favorited) }
    if filters.contains(.reviewed) { out = out.filter(\.reviewed) }
    if filters.contains(.tryLater) { out = out.filter(\.toTry) }
    if filters.contains(.popular) { out = out.filter { $0.tags.contains("popular") } }
    if filters.contains(.quick) { out = out.filter { ($0.cookingMinutes ?? 99) <= 30 } }
    if filters.contains(.pantry) { out = out.filter { PantryMatch.uses($0.ingredients, have: pantryHave) } }
    return out
  }
}
