import Foundation

/// Shared user-facing text. The words live in `shared/copy.json` at the repo root (also used by the website),
/// bundled into the app through the "shared" folder in the Xcode project. Edit text there, not in Swift.
/// `{app}` becomes the app name.
enum Copy {
  private static let table: [String: String] = {
    guard let url = Bundle.main.url(forResource: "copy", withExtension: "json"),
      let data = try? Data(contentsOf: url),
      let raw = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    else {
      fatalError("copy.json is missing or invalid in the app bundle")
    }
    return raw.compactMapValues { $0 as? String }
  }()

  static func validate() { precondition(table["app.name"] != nil, "Missing app.name in copy.json") }

  static var appName: String { text("app.name") }

  /// Text for an id like "settings.gold-star". A missing id shows the id itself, so it's easy to spot.
  static func text(_ id: String) -> String {
    guard let value = table[id] else { fatalError("Missing copy key: \(id)") }
    return value.replacingOccurrences(of: "{app}", with: table["app.name"]!)
  }
}
