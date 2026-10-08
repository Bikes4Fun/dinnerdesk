import Foundation

// Server calls for the Kitchen, sign-in and Settings screens.
// Typed calls go through `API`; household prefs are free-form JSON, so they use `KitchenAPI.json`.

enum KitchenAPI {
  // MARK: Free-form JSON (household prefs)

  static func json(_ path: String, method: String = "GET", body: [String: Any]? = nil) async throws
    -> [String: Any]
  {
    var request = URLRequest(url: API.origin.appending(path: "api/\(path)"))
    request.httpMethod = method
    if let body {
      request.setValue("application/json", forHTTPHeaderField: "Content-Type")
      request.httpBody = try JSONSerialization.data(withJSONObject: body)
    }
    do {
      let (data, response) = try await URLSession.shared.data(for: request)
      let code = (response as? HTTPURLResponse)?.statusCode ?? 0
      guard (200..<300).contains(code) else {
        throw APIError.http(
          code, String(data: data, encoding: .utf8) ?? "Invalid response encoding")
      }
      guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
        throw APIError.http(code, "Expected a JSON object from \(path)")
      }
      return object
    } catch {
      API.reportFailure(error)
      throw error
    }
  }

  /// Preserve the actual failure for diagnosis.
  static func message(_ error: Error) -> String {
    error.localizedDescription
  }

  static func isNotFound(_ error: Error) -> Bool {
    if case APIError.http(let code, _) = error { return code == 404 }
    return false
  }

  // MARK: Household prefs

  static func prefs() async throws -> [String: Any] {
    let household = try await json("household")
    guard let prefs = household["prefs"] as? [String: Any] else {
      NotificationCenter.default.post(
        name: .dinnerdeskFailure, object: "Missing or invalid household preferences")
      throw APIError.http(200, "Missing or invalid household preferences")
    }
    return prefs
  }

  /// Server merges top-level keys, so send only what changed.
  static func savePrefs(_ patch: [String: Any]) async throws {
    _ = try await json("household", method: "PUT", body: ["prefs": patch])
  }

  /// Change part of prefs.grocery without wiping the rest of it.
  static func saveGroceryPrefs(_ patch: [String: Any]) async throws {
    var grocery = try await prefs()["grocery"] as? [String: Any] ?? [:]
    for (key, value) in patch { grocery[key] = value }
    try await savePrefs(["grocery": grocery])
  }

  // MARK: Auth

  static func status() async throws -> AuthStatus { try await API.get("auth/status") }

  static func login(email: String, password: String) async throws {
    let _: Ok = try await API.send(
      "auth/login", method: "POST", body: ["email": email, "password": password])
  }

  static func signup(email: String, password: String, householdName: String) async throws {
    let _: Ok = try await API.send(
      "auth/signup",
      method: "POST",
      body: ["email": email, "password": password, "household_name": householdName]
    )
  }

  /// Emails a reset link if the address has an account. Same answer either way.
  static func forgotPassword(email: String) async throws {
    let _: Ok = try await API.send("auth/forgot-password", method: "POST", body: ["email": email])
  }

  static func logout() async throws {
    let _: Ok = try await API.send("auth/logout", method: "POST")
  }

  static func logoutEverywhere() async throws {
    let _: Ok = try await API.send("auth/logout-everywhere", method: "POST")
  }

  static func changePassword(current: String, new: String) async throws {
    let _: Ok = try await API.send(
      "auth/change-password",
      method: "POST",
      body: ["current_password": current, "new_password": new]
    )
  }

  static func members() async throws -> [HouseholdMember] {
    let box: HouseholdMembers = try await API.get("household/members")
    return box.members
  }

  static func createInvite() async throws -> URL {
    let invite: HouseholdInvite = try await API.send("household/invites", method: "POST")
    return API.origin.appending(path: "join/\(invite.token)")
  }

  static func removeMember(_ id: Int) async throws {
    let _: Ok = try await API.send("household/members/\(id)", method: "DELETE")
  }

  // MARK: Pantry and always-checked

  static func pantry() async throws -> [KitchenPantryItem] {
    let box: KitchenPantryList = try await API.get("pantry")
    return box.items
  }

  @discardableResult
  static func upsertPantry(name: String, have: Bool, neverShop: Bool) async throws
    -> KitchenPantryItem
  {
    try await API.sendJSON(
      "pantry/items",
      method: "POST",
      body: PantryUpsert(name: name, have: have, neverShop: neverShop, zone: "dry")
    )
  }

  @discardableResult
  static func patchPantry(
    id: Int, have: Bool? = nil, neverShop: Bool? = nil, quantity: String? = nil
  ) async throws -> KitchenPantryItem {
    return try await API.sendJSON(
      "pantry/items/\(id)", method: "PATCH",
      body: PantryPatch(have: have, neverShop: neverShop, quantity: quantity))
  }

  static func searchItems(_ query: String) async throws -> [String] {
    let box: KitchenItemSearch = try await API.get(
      "grocery-items", query: ["q": query, "limit": "12"])
    var names = box.items.map(\.name)
    if let custom = box.custom, !custom.isEmpty, !names.contains(custom) { names.append(custom) }
    return names
  }

  // MARK: Substitutions

  static func overrides() async throws -> [KitchenOverride] {
    let box: KitchenOverrideList = try await API.get("overrides")
    return box.items
  }

  static func addOverride(from: String, to: String) async throws -> [KitchenOverride] {
    let box: KitchenOverrideList = try await API.send(
      "overrides", method: "POST", body: ["from_name": from, "to_name": to]
    )
    return box.items
  }

  static func deleteOverride(_ id: Int) async throws -> [KitchenOverride] {
    let box: KitchenOverrideList = try await API.send("overrides/\(id)", method: "DELETE")
    return box.items
  }

  // MARK: Store and aisle per item

  static func placements() async throws -> [ItemPlacement] {
    let box: ItemPlaceList = try await API.get("grocery/places")
    return box.items.map {
      ItemPlacement(name: $0.name, store: $0.store ?? "", aisle: $0.aisle ?? "other", lineIds: [])
    }
  }

  static func setPlacement(_ item: ItemPlacement, store: String? = nil, aisle: String? = nil)
    async throws
  {
    var body: [String: Any] = ["name": item.name]
    if let store { body["store"] = store }
    if let aisle { body["aisle"] = aisle }
    _ = try await json("grocery/places", method: "PUT", body: body)
  }
}

// MARK: - Models

nonisolated struct PantryUpsert: Encodable, Sendable {
  let name: String
  let have: Bool
  let neverShop: Bool
  let zone: String

  enum CodingKeys: String, CodingKey {
    case name, have, zone
    case neverShop = "never_shop"
  }
}

nonisolated struct PantryPatch: Encodable, Sendable {
  let have: Bool?
  let neverShop: Bool?
  let quantity: String?

  enum CodingKeys: String, CodingKey {
    case have, quantity
    case neverShop = "never_shop"
  }
}

nonisolated struct AuthStatus: Decodable, Sendable {
  let required: Bool
  let authenticated: Bool
  let email: String?
  let admin: Bool?
}

nonisolated struct HouseholdMember: Decodable, Identifiable, Sendable {
  let id: Int
  let email: String
  let joinedAt: String?
}

nonisolated struct HouseholdMembers: Decodable, Sendable {
  let members: [HouseholdMember]
}

nonisolated struct HouseholdInvite: Decodable, Sendable {
  let token: String
}

nonisolated struct KitchenPantryItem: Decodable, Sendable {
  let id: Int?
  let name: String
  let have: Bool
  let neverShop: Bool
  let quantity: String
  let store: String?
  let aisle: String?
}

nonisolated struct KitchenPantryList: Decodable, Sendable {
  let items: [KitchenPantryItem]
}

nonisolated struct KitchenItemHit: Decodable, Sendable {
  let name: String
}

nonisolated struct KitchenItemSearch: Decodable, Sendable {
  let items: [KitchenItemHit]
  let custom: String?
}

nonisolated struct KitchenOverride: Decodable, Identifiable, Sendable {
  let id: Int
  let fromName: String
  let toName: String
}

nonisolated struct KitchenOverrideList: Decodable, Sendable {
  let items: [KitchenOverride]
}

nonisolated struct ItemPlace: Decodable, Sendable {
  let name: String
  let store: String?
  let aisle: String?
}

nonisolated struct ItemPlaceList: Decodable, Sendable {
  let items: [ItemPlace]
}

nonisolated struct KitchenPlanRef: Decodable, Sendable {
  let id: Int
}

nonisolated struct KitchenGroceryLine: Decodable, Sendable {
  let id: Int
  let name: String
  let store: String?
  let aisle: String?
}

nonisolated struct KitchenGroceryLines: Decodable, Sendable {
  let lines: [KitchenGroceryLine]
}

/// One grocery item and where it's bought. `lineIds` is only used on servers without saved places.
nonisolated struct ItemPlacement: Identifiable, Equatable, Sendable {
  var id: String { name.lowercased() }
  let name: String
  var store: String
  var aisle: String
  var lineIds: [Int]
}

nonisolated struct KitchenStore: Identifiable, Equatable, Sendable {
  let id: String
  var name: String
}

nonisolated struct KitchenAisle: Identifiable, Equatable, Sendable {
  let id: String
  var name: String
  var number: String
}

enum KitchenDefaults {
  static let stores: [KitchenStore] = [
    KitchenStore(id: "costco", name: "Costco"),
    KitchenStore(id: "walmart", name: "Walmart"),
    KitchenStore(id: "local", name: "Local grocer"),
    KitchenStore(id: "farmers", name: "Farmers market"),
  ]

  static let aisles: [KitchenAisle] = [
    KitchenAisle(id: "produce", name: "Produce", number: ""),
    KitchenAisle(id: "dairy", name: "Dairy, Cheese & Eggs", number: ""),
    KitchenAisle(id: "meat", name: "Meat & Seafood", number: ""),
    KitchenAisle(id: "pantry", name: "Pantry", number: ""),
    KitchenAisle(id: "other", name: "Other", number: ""),
  ]

  static func stores(from prefs: [String: Any]) -> [KitchenStore] {
    let raw = (prefs["grocery"] as? [String: Any])?["stores"] as? [[String: Any]] ?? []
    let list = raw.compactMap { item -> KitchenStore? in
      guard let id = item["id"] as? String, let name = item["name"] as? String else {
        preconditionFailure("Invalid store or aisle configuration")
      }
      return KitchenStore(id: id, name: name)
    }
    return (prefs["grocery"] as? [String: Any])?["stores"] != nil ? list : stores
  }

  static func aisles(from prefs: [String: Any]) -> [KitchenAisle] {
    let raw = (prefs["grocery"] as? [String: Any])?["aisles"] as? [[String: Any]] ?? []
    let list = raw.compactMap { item -> KitchenAisle? in
      guard let id = item["id"] as? String, let name = item["name"] as? String else {
        preconditionFailure("Invalid store or aisle configuration")
      }
      return KitchenAisle(id: id, name: name, number: item["number"] as? String ?? "")
    }
    return list.isEmpty ? aisles : list
  }

  static func json(_ stores: [KitchenStore]) -> [[String: Any]] {
    stores.map { ["id": $0.id, "name": $0.name] }
  }

  static func json(_ aisles: [KitchenAisle]) -> [[String: Any]] {
    aisles.map { ["id": $0.id, "name": $0.name, "number": $0.number] }
  }

  static func slug(_ name: String) throws -> String {
    let lowered = name.lowercased()
    var out = ""
    var lastDash = false
    for ch in lowered {
      if ch.isLetter || ch.isNumber {
        out.append(ch)
        lastDash = false
      } else if !lastDash, !out.isEmpty {
        out.append("-")
        lastDash = true
      }
    }
    while out.hasSuffix("-") { out.removeLast() }
    guard !out.isEmpty else { throw APIError.http(400, "A name must contain a letter or number") }
    return out
  }
}
