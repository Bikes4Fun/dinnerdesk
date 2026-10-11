import Foundation

/// Sign-in, account, and session calls. Typed requests go through `API`.
enum AuthAPI {
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

  /// Deletes the signed-in account (#65). The last member's household and kitchen go with it.
  static func deleteAccount(password: String) async throws {
    let _: Ok = try await API.send("auth/delete-account", method: "POST", body: ["password": password])
  }

  static func changePassword(current: String, new: String) async throws {
    let _: Ok = try await API.send(
      "auth/change-password",
      method: "POST",
      body: ["current_password": current, "new_password": new]
    )
  }
}

nonisolated struct AuthStatus: Decodable, Sendable {
  let required: Bool
  let authenticated: Bool
  let email: String?
  let admin: Bool?
}
