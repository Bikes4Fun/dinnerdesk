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

  /// Deletes this account; shared-household creators must transfer ownership first.
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

  /// Emails a confirm link to the signed-in address, or to a new one (needs the password).
  /// The login only changes once that link is opened.
  static func verifyEmail(email: String = "", password: String = "") async throws {
    let _: Ok = try await API.send(
      "auth/verify-email", method: "POST", body: ["email": email, "password": password])
  }

  /// Removes the email: the account signs in with this username instead.
  static func useUsername(_ username: String, password: String) async throws {
    let _: Ok = try await API.send(
      "auth/use-username", method: "POST", body: ["username": username, "password": password])
  }
}

nonisolated struct AuthStatus: Decodable, Sendable {
  let required: Bool
  let householdId: Int?
  let authenticated: Bool
  let email: String?
  let hasEmail: Bool?
  let emailVerified: Bool?
  let admin: Bool?

  /// Why a signed-in account should verify (or add) an email, or nil once it's verified.
  var emailNudge: String? {
    guard authenticated, emailVerified != true else { return nil }
    return hasEmail == false
      ? "Your account has no email, so a forgotten password can't be reset."
      : "Your email isn't verified yet, so a password reset link might not reach you."
  }
}
