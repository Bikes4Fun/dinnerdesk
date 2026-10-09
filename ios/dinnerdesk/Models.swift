import Foundation

nonisolated struct Plan: Decodable, Sendable {
  let id: Int
  let title: String
  let startDate: String
  let days: Int
  let slots: [PlanSlot]
  let status: String?
  let suggestedRecipeIds: [Int]?
  let suggestionNote: String?
  let suggestionReasons: [String: [String]]?

  func withSlots(_ slots: [PlanSlot]) -> Plan {
    Plan(
      id: id, title: title, startDate: startDate, days: days, slots: slots,
      status: status, suggestedRecipeIds: suggestedRecipeIds, suggestionNote: suggestionNote, suggestionReasons: suggestionReasons)
  }
}

nonisolated struct PlanSlot: Decodable, Identifiable, Sendable {
  let id: Int
  let recipeId: Int
  let recipeName: String
  let photoPath: String?
  let cookingMinutes: Int?
  var dayIndex: Int?
  let mealType: String
  var servings: Int
  var cooked: Bool
  /// Household thumbs on this meal: 1 up, -1 down, nil/0 none.
  var rating: Int?

  var asBody: [String: Any] {
    var body: [String: Any] = [
      "id": id,
      "recipe_id": recipeId,
      "meal_type": mealType,
      "servings": servings,
    ]
    if let dayIndex {
      body["day_index"] = dayIndex
    }
    return body
  }
}

nonisolated struct RecipeList: Decodable, Sendable {
  let recipes: [RecipeSummary]
}

nonisolated struct RecipeSummary: Decodable, Identifiable, Sendable {
  let id: Int
  let name: String
  let servings: Int?
  let cookingMinutes: Int?
  let photoPath: String?
  var favorited: Bool
  var toTry: Bool
  let catalog: Bool
  let hidden: Bool
  let tags: [String]
  let ingredients: [String]

  enum CodingKeys: String, CodingKey {
    case id, name, servings, cookingMinutes, photoPath
    case favorited, toTry, catalog, hidden, tags, ingredients
  }

  init(from decoder: Decoder) throws {
    let c = try decoder.container(keyedBy: CodingKeys.self)
    id = try c.decode(Int.self, forKey: .id)
    name = try c.decode(String.self, forKey: .name)
    servings = try c.decodeIfPresent(Int.self, forKey: .servings)
    cookingMinutes = try c.decodeIfPresent(Int.self, forKey: .cookingMinutes)
    photoPath = try c.decodeIfPresent(String.self, forKey: .photoPath)
    favorited = try c.decode(Bool.self, forKey: .favorited)
    toTry = try c.decode(Bool.self, forKey: .toTry)
    catalog = try c.decode(Bool.self, forKey: .catalog)
    hidden = try c.decode(Bool.self, forKey: .hidden)
    tags = try c.decode([String].self, forKey: .tags)
    ingredients = try c.decode([String].self, forKey: .ingredients)
  }

  func withFavorited(_ on: Bool) -> RecipeSummary {
    var copy = self
    copy.favorited = on
    return copy
  }

  func withToTry(_ on: Bool) -> RecipeSummary {
    var copy = self
    copy.toTry = on
    return copy
  }

  var isExtra: Bool {
    if tags.contains("main_dish") || tags.contains("full_meal") { return false }
    return tags.contains(where: { $0 == "sauce" || $0 == "dressing" || $0 == "component" })
  }

  var isMeal: Bool { !isExtra }

  var prettyTags: String {
    tags.map { $0.replacingOccurrences(of: "_", with: " ") }.joined(separator: " · ")
  }
}

nonisolated struct RecipeDetail: Decodable, Identifiable, Sendable {
  let id: Int
  var name: String
  let servings: Int?
  let cookingMinutes: Int?
  let photoPath: String?
  /// The photo was made with AI; the recipe page says so (#33).
  let photoAI: Bool
  var favorited: Bool
  var toTry: Bool
  var hidden: Bool
  let catalog: Bool
  let tags: [String]
  var ingredients: [IngredientLine]
  var instructions: [InstructionStep]
  let instructionsSource: String?
  let instructionsCopiedFromThirdParty: Bool?
  var instructionsCustomized: Bool {
    instructionsSource == "dinnerdesk" && instructionsCopiedFromThirdParty == false
  }

  enum CodingKeys: String, CodingKey {
    case id, name, servings, cookingMinutes, photoPath, photoAi
    case favorited, toTry, hidden, catalog, tags, ingredients, instructions
    case instructionsSource, instructionsCopiedFromThirdParty
  }

  init(from decoder: Decoder) throws {
    let c = try decoder.container(keyedBy: CodingKeys.self)
    id = try c.decode(Int.self, forKey: .id)
    name = try c.decode(String.self, forKey: .name)
    servings = try c.decodeIfPresent(Int.self, forKey: .servings)
    cookingMinutes = try c.decodeIfPresent(Int.self, forKey: .cookingMinutes)
    photoPath = try c.decodeIfPresent(String.self, forKey: .photoPath)
    photoAI = try c.decodeIfPresent(Bool.self, forKey: .photoAi) ?? false
    favorited = try c.decode(Bool.self, forKey: .favorited)
    toTry = try c.decode(Bool.self, forKey: .toTry)
    hidden = try c.decode(Bool.self, forKey: .hidden)
    catalog = try c.decode(Bool.self, forKey: .catalog)
    tags = try c.decode([String].self, forKey: .tags)
    ingredients = try c.decode([IngredientLine].self, forKey: .ingredients)
    instructions = try c.decode([InstructionStep].self, forKey: .instructions)
    instructionsSource = try c.decodeIfPresent(String.self, forKey: .instructionsSource)
    instructionsCopiedFromThirdParty = try c.decodeIfPresent(Bool.self, forKey: .instructionsCopiedFromThirdParty)
  }

  var prettyTags: String {
    tags.map { $0.replacingOccurrences(of: "_", with: " ") }.joined(separator: " · ")
  }
}

nonisolated struct IngredientLine: Decodable, Identifiable, Sendable {
  var id: String { "\(ingredientId ?? 0)-\(name)-\(quantity ?? "")" }
  let name: String
  let quantity: String?
  let ingredientId: Int?
}

nonisolated struct InstructionStep: Decodable, Identifiable, Sendable {
  var id: String { displayText }
  let text: String?
  let step: String?
  var prep: Bool?
  let ings: String?
  var displayText: String { text ?? step ?? "" }

  func asBody() -> [String: Any] {
    var body: [String: Any] = [
      "text": displayText,
      "prep": prep ?? false,
    ]
    if let ings, !ings.isEmpty {
      body["ings"] = ings
    }
    return body
  }
}

nonisolated struct GroceryList: Decodable, Sendable {
  let lines: [GroceryLine]
}

nonisolated struct UsedMeal: Decodable, Identifiable, Hashable, Sendable {
  var id: String { "\(recipeId ?? 0)-\(name)" }
  let recipeId: Int?
  let name: String
  let photoPath: String?
  let cookingMinutes: Int?
  let quantity: String

  enum CodingKeys: String, CodingKey {
    case recipeId = "id"
    case name, photoPath, cookingMinutes, quantity
  }

  init(from decoder: Decoder) throws {
    let c = try decoder.container(keyedBy: CodingKeys.self)
    recipeId = try c.decodeIfPresent(Int.self, forKey: .recipeId)
    name = try c.decode(String.self, forKey: .name)
    photoPath = try c.decodeIfPresent(String.self, forKey: .photoPath)
    cookingMinutes = try c.decodeIfPresent(Int.self, forKey: .cookingMinutes)
    quantity = try c.decodeIfPresent(String.self, forKey: .quantity) ?? ""
  }
}

nonisolated struct GroceryLine: Decodable, Identifiable, Sendable {
  let id: Int
  var name: String
  var quantity: String
  var aisle: String
  var store: String
  var checked: Bool
  var neverShop: Bool
  var fromPantry: Bool
  let usedBy: [String]
  let usedIn: [UsedMeal]
  let ingredientPhotoPath: String?

  enum CodingKeys: String, CodingKey {
    case id, name, quantity, aisle, store, checked, neverShop, fromPantry, usedBy, usedIn,
      ingredientPhotoPath
  }

  init(from decoder: Decoder) throws {
    let c = try decoder.container(keyedBy: CodingKeys.self)
    id = try c.decode(Int.self, forKey: .id)
    name = try c.decode(String.self, forKey: .name)
    ingredientPhotoPath = try c.decodeIfPresent(String.self, forKey: .ingredientPhotoPath)
    quantity = try c.decodeIfPresent(String.self, forKey: .quantity) ?? ""
    aisle = try c.decodeIfPresent(String.self, forKey: .aisle) ?? "other"
    store = try c.decodeIfPresent(String.self, forKey: .store) ?? ""
    checked = try c.decodeIfPresent(Bool.self, forKey: .checked) ?? false
    neverShop = try c.decodeIfPresent(Bool.self, forKey: .neverShop) ?? false
    fromPantry = try c.decodeIfPresent(Bool.self, forKey: .fromPantry) ?? false
    usedBy = try c.decodeIfPresent([String].self, forKey: .usedBy) ?? []
    usedIn = try c.decodeIfPresent([UsedMeal].self, forKey: .usedIn) ?? []
  }
}

nonisolated struct GroceryItemHits: Decodable, Sendable {
  nonisolated struct Item: Decodable, Sendable {
    var name: String
  }

  let items: [Item]
}

nonisolated struct PrepList: Decodable, Sendable {
  let tasks: [PrepTask]
}

nonisolated struct PrepTask: Decodable, Identifiable, Sendable {
  let id: Int
  let title: String
  let notes: String
  var done: Bool
  var meals: [PrepMeal]
  let quantities: [String]
  /// True when the app picked these steps (no step in the recipe was tagged Prep).
  let auto: Bool?
}

nonisolated struct PrepMeal: Decodable, Identifiable, Sendable {
  let id: Int
  let name: String
  let instructions: [String]
  var steps: [PrepStep]?
}

nonisolated struct PrepStep: Decodable, Identifiable, Sendable {
  var id: String { key }
  let key: String
  let text: String
  let auto: Bool?
  var rating: Int?
  /// Checked off on the Prep screen (each meal's step is its own item).
  var done: Bool?
}

nonisolated struct PrepItemResult: Decodable, Sendable {
  let done: Bool
}

nonisolated struct MealRating: Decodable, Sendable {
  let recipeId: Int
  let rating: Int
}

nonisolated struct ShopStore: Decodable, Identifiable, Hashable, Sendable {
  let id: String
  let name: String

  static let defaults: [ShopStore] = [
    ShopStore(id: "costco", name: "Costco"),
    ShopStore(id: "walmart", name: "Walmart"),
    ShopStore(id: "local", name: "Local grocer"),
    ShopStore(id: "farmers", name: "Farmers market"),
  ]
}

nonisolated struct ShopAisle: Decodable, Identifiable, Hashable, Sendable {
  let id: String
  let name: String
  var number: String

  enum CodingKeys: String, CodingKey {
    case id, name, number
  }

  init(id: String, name: String, number: String) {
    self.id = id
    self.name = name
    self.number = number
  }

  init(from decoder: Decoder) throws {
    let c = try decoder.container(keyedBy: CodingKeys.self)
    id = try c.decode(String.self, forKey: .id)
    name = try c.decode(String.self, forKey: .name)
    number = try c.decode(String.self, forKey: .number)
  }

  static let defaults: [ShopAisle] = [
    ShopAisle(id: "produce", name: "Produce", number: ""),
    ShopAisle(id: "dairy", name: "Dairy, Cheese & Eggs", number: ""),
    ShopAisle(id: "meat", name: "Meat & Seafood", number: ""),
    ShopAisle(id: "pantry", name: "Pantry", number: ""),
    ShopAisle(id: "other", name: "Other", number: ""),
  ]
}

nonisolated struct Household: Decodable, Sendable {
  nonisolated struct Prefs: Decodable, Sendable {
    nonisolated struct Grocery: Decodable, Sendable {
      let stores: [ShopStore]?
      let aisles: [ShopAisle]?
      let groupByStore: Bool?
      let showMeals: Bool?
      let hideChecked: Bool?
      let showAisleNums: Bool?
      let showEmoji: Bool?
    }

    let grocery: Grocery?
  }

  let prefs: Prefs?
}

// Only the saved-plan listing has a status discriminator. The current-plan
// endpoint supplies the active plan directly, without needing that metadata.
nonisolated struct SavedPlan: Decodable, Identifiable, Sendable {
  let id: Int
  let title: String
  let startDate: String
  let days: Int
  let slots: [PlanSlot]
  let status: String
  let decision: String?
  let changes: [SuggestionChange]?
  /// When the plan was saved (ISO 8601). Older servers don't send it.
  let createdAt: String?
}
nonisolated struct SuggestionChange: Decodable, Sendable { let from: Int; let to: Int; let at: String }
nonisolated struct PendingSuggestion: Decodable, Sendable { let plan: Plan? }
nonisolated struct RecipeSuggestions: Decodable, Sendable { let recipeIds: [Int] }

nonisolated struct PlanList: Decodable, Sendable { let plans: [SavedPlan] }

nonisolated struct SuggestionCapabilities: Decodable, Sendable { let version: Int; let review: Bool; let resize: Bool; let swap: Bool }

nonisolated struct SwapOption: Decodable, Identifiable, Sendable {
  let id: Int
  let name: String
  let cookingMinutes: Int?
  let photoPath: String?
}
nonisolated struct SwapOptions: Decodable, Sendable { let recipes: [SwapOption] }
