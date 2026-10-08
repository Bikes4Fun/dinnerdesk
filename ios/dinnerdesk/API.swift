import Foundation

enum API {
  static let origin = URL(string: "https://dinnerdesk.computerscience.build")!

  static func photoURL(_ path: String?) -> URL? {
    guard let path, !path.isEmpty else { return nil }
    if path.hasPrefix("http") { return URL(string: path) }
    let trimmed = path.hasPrefix("/") ? String(path.dropFirst()) : path
    return URL(string: trimmed, relativeTo: origin)?.absoluteURL
  }

  static func get<T: Decodable>(_ path: String, query: [String: String] = [:], reportErrors: Bool = true) async throws -> T {
    do {
      let (data, response) = try await URLSession.shared.data(from: url(path, query: query))
      logRejectedRequest(response, method: "GET", path: path)
      try throwIfBad(response, data: data)
      return try decoder.decode(T.self, from: data)
    } catch {
      if reportErrors { reportFailure(error) }
      throw error
    }
  }

  static func send<T: Decodable>(_ path: String, method: String, body: [String: Any]? = nil)
    async throws -> T
  {
    let data = try body.map { try JSONSerialization.data(withJSONObject: $0) }
    return try await sendData(path, method: method, body: data)
  }

  /// Encode typed request values before suspending for the network request.
  static func sendJSON<T: Decodable, Body: Encodable & Sendable>(
    _ path: String, method: String, body: Body
  ) async throws -> T {
    let data = try JSONEncoder().encode(body)
    return try await sendData(path, method: method, body: data)
  }

  private static func sendData<T: Decodable>(
    _ path: String, method: String, body: Data?
  ) async throws -> T {
    var request = URLRequest(url: url(path))
    request.httpMethod = method
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.httpBody = body
    do {
      let (data, response) = try await URLSession.shared.data(for: request)
      logRejectedRequest(response, method: method, path: path)
      try throwIfBad(response, data: data)
      return try decoder.decode(T.self, from: data)
    } catch {
      reportFailure(error)
      throw error
    }
  }

  /// Leaving a screen cancels its requests. That is not a failure to show the user.
  static func isCancellation(_ error: Error) -> Bool {
    if error is CancellationError { return true }
    if let url = error as? URLError, url.code == .cancelled { return true }
    let ns = error as NSError
    return ns.domain == NSURLErrorDomain && ns.code == NSURLErrorCancelled
  }

  static func reportFailure(_ error: Error) {
    guard !isCancellation(error) else { return }
    if case APIError.http = error { return }
    NotificationCenter.default.post(name: .dinnerdeskFailure, object: error.localizedDescription)
  }

  private static func url(_ path: String, query: [String: String] = [:]) -> URL {
    var parts = URLComponents(
      url: origin.appending(
        path: "api/\(path.trimmingCharacters(in: CharacterSet(charactersIn: "/")))"),
      resolvingAgainstBaseURL: false
    )!
    if !query.isEmpty {
      parts.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
    }
    return parts.url!
  }

  private static func throwIfBad(_ response: URLResponse, data: Data) throws {
    let code = (response as? HTTPURLResponse)?.statusCode ?? 0
    guard (200..<300).contains(code) else {
      throw APIError.http(code, String(data: data, encoding: .utf8) ?? "")
    }
  }

  // Keep method/path diagnostics out of the UI and omit bodies and query values.
  private static func logRejectedRequest(_ response: URLResponse, method: String, path: String) {
    guard let response = response as? HTTPURLResponse, response.statusCode == 405 else { return }
    NSLog("Dinnerdesk request rejected: %@ /api/%@ (405); allowed methods: %@",
          method, path, response.value(forHTTPHeaderField: "Allow") ?? "unspecified")
  }

  private static let decoder: JSONDecoder = {
    let d = JSONDecoder()
    d.keyDecodingStrategy = .convertFromSnakeCase
    return d
  }()
}

enum APIError: LocalizedError {
  case http(Int, String)
  var errorDescription: String? {
    switch self {
    case .http(let code, let body):
      if code == 404 || code == 405 { return "This action is currently unavailable. Please try again later. If it keeps happening, contact Dinnerdesk support." }
      if code == 401 { return "Please sign in again to continue." }
      if code == 403 { return "You don't have access to this action." }
      if code >= 500 { return "The server couldn't complete this action. Please try again shortly." }
      if let data = body.data(using: .utf8), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
        if let detail = object["detail"] as? String { return detail }
        if let detail = object["detail"] as? [String: Any], let message = detail["message"] as? String { return message }
        if let message = object["message"] as? String { return message }
      }
      return "Couldn't complete this action. Please try again."
    }
  }
}

extension Notification.Name {
  static let dinnerdeskFailure = Notification.Name("dinnerdeskFailure")
}
