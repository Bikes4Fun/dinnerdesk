import Foundation

/// "Uses pantry" for recipe search: the same rule as the website (web/src/pages/Recipes.jsx).
/// A recipe uses the pantry when two or more ingredients are things you have, or one when
/// that's at least 40% of a short ingredient list. Never-shop staples (salt, oil) don't count.
enum PantryMatch {
  static func have(_ items: [KitchenPantryItem]) -> Set<String> {
    Set(items.filter { $0.have && !$0.neverShop }.map { norm($0.name) }.filter { !$0.isEmpty })
  }

  static func uses(_ ingredients: [String], have: Set<String>) -> Bool {
    guard !have.isEmpty else { return false }
    let names = ingredients.map(norm).filter { !$0.isEmpty }
    guard !names.isEmpty else { return false }
    let hits = names.filter { hit($0, have) }.count
    return hits >= 2 || (hits >= 1 && Double(hits) / Double(names.count) >= 0.4)
  }

  private static func hit(_ ingredient: String, _ have: Set<String>) -> Bool {
    if have.contains(ingredient) { return true }
    return have.contains { p in
      p.count >= 3
        && (ingredient.hasPrefix(p + " ") || ingredient.hasSuffix(" " + p)
          || ingredient.contains(" " + p + " "))
    }
  }

  static func norm(_ text: String) -> String {
    let cleaned = text.lowercased().map { c -> Character in
      (c.isASCII && (c.isLetter || c.isNumber)) ? c : " "
    }
    return String(cleaned).split(separator: " ").joined(separator: " ")
  }
}
