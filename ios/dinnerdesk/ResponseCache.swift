import CryptoKit
import Foundation
#if os(iOS)
import UIKit
#endif

/// Server responses kept on the device so screens paint instantly, work with a weak signal,
/// and don't refetch on every visit. Stores the raw JSON bytes of a GET (or of a write that
/// returns the same shape), so models only need to stay Decodable.
///
/// The cache is a convenience, never the source of truth: every read falls back to the
/// network, and `Store` revalidates once per launch and after pull-to-refresh.
enum ResponseCache {
  private static let accountKey = "dinnerdesk.cache.account"

  private static var directory: URL {
    FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
      .appending(path: "api", directoryHint: .isDirectory)
  }

  /// One key per path and query, independent of query order.
  static func key(_ path: String, query: [String: String] = [:]) -> String {
    let trimmed = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    guard !query.isEmpty else { return trimmed }
    let pairs = query.sorted { $0.key < $1.key }.map { "\($0.key)=\($0.value)" }
    return "\(trimmed)?\(pairs.joined(separator: "&"))"
  }

  static func data(for key: String) -> Data? {
    try? Data(contentsOf: file(key))
  }

  /// Bumped by `clear()`. A response requested before the cache was cleared (the previous
  /// account's) is never written into the new one.
  private(set) static var epoch = 0

  static func store(_ data: Data, for key: String, requestedAt requested: Int? = nil) {
    if let requested, requested != epoch { return }
    do {
      try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
      try data.write(to: file(key), options: .atomic)
    } catch {
      // A full disk or a cleared cache only costs a network request later.
    }
  }

  /// Save a value changed on this device (a checked grocery item, a moved meal) in the same
  /// shape the server sends, so the saved copy matches what the person last saw.
  static func save<T: Encodable>(_ value: T, as key: String) {
    if let data = try? encoder.encode(value) { store(data, for: key) }
  }

  private static let encoder: JSONEncoder = {
    let e = JSONEncoder()
    e.keyEncodingStrategy = .convertToSnakeCase
    return e
  }()

  /// Seconds since the saved copy was written, or nil when there is none.
  static func age(of key: String) -> TimeInterval? {
    let attributes = try? FileManager.default.attributesOfItem(atPath: file(key).path)
    guard let written = attributes?[.modificationDate] as? Date else { return nil }
    return Date().timeIntervalSince(written)
  }

  static func remove(_ key: String) {
    try? FileManager.default.removeItem(at: file(key))
  }

  /// Drop everything, e.g. when a different account signs in on this device.
  static func clear() {
    epoch += 1
    try? FileManager.default.removeItem(at: directory)
    #if os(iOS)
    PhotoCache.clear()
    #endif
  }

  /// Clear the cache when the signed-in account changes, so one kitchen never sees
  /// another's plan. `account` is the email, or nil for a guest.
  static func noteAccount(_ account: String?) {
    let current = account ?? "guest"
    let defaults = UserDefaults.standard
    if let previous = defaults.string(forKey: accountKey), previous != current {
      clear()
      Freshness.invalidateAll()
      NotificationCenter.default.post(name: .dinnerdeskAccountChanged, object: nil)
    }
    defaults.set(current, forKey: accountKey)
  }

  private static func file(_ key: String) -> URL {
    let digest = SHA256.hash(data: Data(key.utf8)).map { String(format: "%02x", $0) }.joined()
    return directory.appending(path: "\(digest).json")
  }
}

extension Notification.Name {
  /// A different account (or a guest) is now using the app; drop the previous one's data.
  static let dinnerdeskAccountChanged = Notification.Name("dinnerdeskAccountChanged")
}

/// Recipe and ingredient photos, kept in memory and on disk. Photo paths change when a photo
/// is replaced, so a cached file never needs revalidating.
#if os(iOS)
enum PhotoCache {
  private static let memory: NSCache<NSString, UIImage> = {
    let cache = NSCache<NSString, UIImage>()
    cache.countLimit = 300
    return cache
  }()

  private static var directory: URL {
    FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
      .appending(path: "photos", directoryHint: .isDirectory)
  }

  /// Already decoded and in memory: no disk or network work at all.
  static func memoryImage(for url: URL) -> UIImage? {
    memory.object(forKey: url.absoluteString as NSString)
  }

  static func image(for url: URL) async throws -> UIImage {
    if let hit = memoryImage(for: url) { return hit }
    let file = file(url)
    // Disk reads and decoding run off the main thread so scrolling a photo grid stays smooth.
    if let image = await Task.detached(priority: .userInitiated, operation: { PhotoCache.decoded(at: file) }).value {
      memory.setObject(image, forKey: url.absoluteString as NSString)
      return image
    }
    let (data, response) = try await URLSession.shared.data(from: url)
    try Task.checkCancellation()
    guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
      throw APIError.http((response as? HTTPURLResponse)?.statusCode ?? 0, "Photo request failed")
    }
    let folder = directory
    let image = await Task.detached(priority: .userInitiated, operation: { () -> UIImage? in
      guard let image = UIImage(data: data) else { return nil }
      try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
      try? data.write(to: file, options: .atomic)
      return image.preparingForDisplay() ?? image
    }).value
    guard let image else { throw APIError.http(http.statusCode, "Invalid photo data") }
    memory.setObject(image, forKey: url.absoluteString as NSString)
    return image
  }

  nonisolated private static func decoded(at file: URL) -> UIImage? {
    guard let data = try? Data(contentsOf: file), let image = UIImage(data: data) else { return nil }
    return image.preparingForDisplay() ?? image
  }

  /// Download a photo ahead of time (planned meals) without showing errors.
  static func prefetch(_ path: String?) async {
    guard let url = API.photoURL(path), memoryImage(for: url) == nil else { return }
    if FileManager.default.fileExists(atPath: file(url).path) { return }
    _ = try? await image(for: url)
  }

  static func clear() {
    memory.removeAllObjects()
    try? FileManager.default.removeItem(at: directory)
  }

  private static func file(_ url: URL) -> URL {
    let digest = SHA256.hash(data: Data(url.absoluteString.utf8)).map { String(format: "%02x", $0) }.joined()
    return directory.appending(path: digest)
  }
}

#endif

/// When each kind of data last came from the server in this launch. Screens skip the network
/// while their data is fresh; a write that changes the data marks it stale. Kept in memory
/// only, so every launch revalidates once.
enum Freshness {
  static let plan = "plan"
  static let recipes = "recipes"
  static let grocery = "grocery"
  static let prep = "prep"
  static let household = "household"
  static let hidden = "hidden"
  static let auth = "auth"

  /// Long enough that moving between tabs never refetches; short enough that a change made
  /// on another device shows up when the app is reopened later.
  static let window: TimeInterval = 10 * 60

  /// A saved recipe is shown without asking the server for this long. Edits made on this
  /// device replace or drop the saved copy right away.
  static let recipeAge: TimeInterval = 24 * 60 * 60

  private static var loaded: [String: Date] = [:]

  static func isFresh(_ key: String, within: TimeInterval = window) -> Bool {
    guard let at = loaded[key] else { return false }
    return Date().timeIntervalSince(at) < within
  }

  static func mark(_ key: String) { loaded[key] = Date() }

  static func invalidate(_ keys: String...) {
    for key in keys { loaded[key] = nil }
  }

  static func invalidateAll() { loaded.removeAll() }

  /// A successful write elsewhere in the app (Kitchen, Pantry, Settings) can change data the
  /// Store keeps. The Store updates its own state from the responses of its own writes
  /// (plan slots, grocery lines, prep), so those paths need nothing here.
  static func noteWrite(_ path: String, method: String) {
    let path = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    let parts = path.split(separator: "/").map(String.init)
    if path.hasPrefix("auth/") || path.hasPrefix("household/") {
      invalidateAll()
    } else if path == "household" {
      invalidate(household, grocery)
    } else if path.hasPrefix("pantry") || path.hasPrefix("overrides") || path.hasPrefix("grocery/places") {
      invalidate(grocery)
    } else if parts.first == "recipes" {
      // Reading a web page into a draft saves nothing.
      if parts.count == 2 && parts[1] == "import" { return }
      let flagOnly = parts.count == 3 && ["favorite", "try", "hidden", "rating", "dev-notes"].contains(parts[2])
      // Favorite, To try and Hide are applied to the Store's list as they're tapped.
      if !flagOnly {
        // Creating or editing a recipe changes names and ingredients shown in lists, the
        // plan, groceries and prep.
        invalidate(recipes, plan, grocery, prep)
        if parts.count >= 2 { ResponseCache.remove(ResponseCache.key("recipes/\(parts[1])")) }
      }
    }
  }
}
