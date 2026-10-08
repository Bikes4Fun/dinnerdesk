import Combine
import SwiftUI

/// Who is using the app: signed in, a guest, or not decided yet.
@MainActor
final class Session: ObservableObject {
  private static let guestKey = "dinnerdesk.guest"

  @Published var status: AuthStatus?
  @Published var loadError: String?
  /// The person chose "Continue as guest" on this device.
  @Published var guest = UserDefaults.standard.bool(forKey: Session.guestKey) {
    didSet { UserDefaults.standard.set(guest, forKey: Session.guestKey) }
  }

  /// Show the sign-in screen before the app?
  var needsSignIn: Bool {
    guard let status else { return false }
    if status.authenticated { return false }
    return status.required || !guest
  }

  var canContinueAsGuest: Bool { !(status?.required ?? false) }

  /// Show the quick start tour. Set it from anywhere (More, Settings) to replay the tour.
  @Published var showTour = false
  private var tourChecked = false

  /// First run: open the tour once if the household has never finished or skipped it.
  func checkTour() async {
    guard !tourChecked, !needsSignIn, status != nil else { return }
    do {
      let prefs = try await KitchenAPI.prefs()
      tourChecked = true
      if prefs["tour_done"] == nil { showTour = true }
    } catch { loadError = KitchenAPI.message(error) }
  }

  func refresh() async {
    do {
      status = try await KitchenAPI.status()
      loadError = nil
      if status?.authenticated == true { guest = false }
    } catch {
      loadError = KitchenAPI.message(error)
    }
  }

  func continueAsGuest() {
    guest = true
  }

  func signOut() async {
    do { try await KitchenAPI.logout() } catch {
      loadError = KitchenAPI.message(error)
      return
    }
    guest = false
    tourChecked = false
    await refresh()
  }
}

/// Wrap the app's tabs in this: shows sign-in first when needed, then `content`.
/// `content` is only built once signed in (or a guest), so its data loads for the right household.
struct AuthGate<Content: View>: View {
  @StateObject private var session = Session()
  @State private var blockingError: String?
  private let content: () -> Content

  init(@ViewBuilder content: @escaping () -> Content) {
    self.content = content
  }

  var body: some View {
    Group {
      if session.status == nil {
        VStack(spacing: 16) {
          if let err = session.loadError {
            Text(err)
              .multilineTextAlignment(.center)
              .foregroundStyle(Theme.muted)
            Button("Try again") { Task { await session.refresh() } }
              .buttonStyle(.borderedProminent)
              .tint(Theme.accent)
          } else {
            ProgressView()
          }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.bg)
      } else if session.needsSignIn {
        AuthView()
      } else {
        content()
          .overlay(alignment: .top) {
            if let error = session.loadError { ErrorBanner(message: error).padding() }
          }
          .task { await session.checkTour() }
      }
    }
    .onReceive(NotificationCenter.default.publisher(for: .dinnerdeskFailure)) { note in
      blockingError = note.object as? String
    }
    .fullScreenCover(isPresented: Binding(get: { blockingError != nil }, set: { _ in })) {
      VStack(alignment: .leading, spacing: 20) {
        Text("App stopped").font(Theme.bigTitle)
        Text(blockingError!).font(Theme.body).textSelection(.enabled)
        Text("Fix the error, then reopen the app.").foregroundStyle(Theme.muted)
      }
      .padding().frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
      .background(Theme.bg).interactiveDismissDisabled()
    }
    .fullScreenCover(isPresented: $session.showTour) {
      TourView()
        .environmentObject(session)
    }
    .environmentObject(session)
    .task { await session.refresh() }
  }
}

struct AuthView: View {
  enum Mode: String, CaseIterable, Identifiable {
    case signIn = "Sign in"
    case signUp = "Create account"
    var id: String { rawValue }
  }

  @EnvironmentObject private var session: Session
  @Environment(\.dismiss) private var dismiss
  /// True when shown as a sheet from Settings (adds a Cancel button).
  private let isSheet: Bool

  @State private var mode: Mode = .signIn
  @State private var email = ""
  @State private var password = ""
  @State private var householdName = ""
  @State private var busy = false
  @State private var error: String?
  @State private var forgot = false

  init(isSheet: Bool = false) {
    self.isSheet = isSheet
  }

  private var canSubmit: Bool {
    !busy && email.contains("@") && password.count >= (mode == .signUp ? 8 : 1)
  }

  var body: some View {
    NavigationStack {
      Form {
        Section {
          VStack(alignment: .leading, spacing: 6) {
            Text(Copy.appName)
              .font(KitchenStyle.bigTitle)
              .foregroundStyle(Theme.ink)
            Text(Copy.text("app.tagline"))
              .foregroundStyle(Theme.muted)
          }
          .padding(.vertical, 8)
          .listRowBackground(Color.clear)
        }

        Section {
          Picker("Mode", selection: $mode) {
            ForEach(Mode.allCases) { Text($0.rawValue).tag($0) }
          }
          .pickerStyle(.segmented)
          .listRowBackground(Color.clear)
        }

        Section {
          TextField("Email", text: $email)
            .textContentType(.emailAddress)
            .keyboardType(.emailAddress)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
          SecureField("Password", text: $password)
            .textContentType(
              mode == .signUp ? UITextContentType.newPassword : UITextContentType.password)
          if mode == .signUp {
            TextField("Household name (optional)", text: $householdName)
          }
        } footer: {
          if mode == .signUp {
            Text("At least 8 characters.")
          } else {
            Button("Forgot password?") { forgot = true }
              .font(Theme.action)
              .foregroundStyle(Theme.accent)
              .padding(.top, 4)
          }
        }

        if let error {
          Section {
            ErrorBanner(message: error)
              .listRowInsets(EdgeInsets())
              .listRowBackground(Color.clear)
          }
        }

        Section {
          Button {
            Task { await submit() }
          } label: {
            HStack {
              Spacer()
              if busy { ProgressView() } else { Text(mode.rawValue).font(Theme.action) }
              Spacer()
            }
          }
          .disabled(!canSubmit)
          .listRowBackground(canSubmit ? Theme.accent : Theme.accent.opacity(0.4))
          .foregroundStyle(.white)
        }

        if session.canContinueAsGuest && !isSheet {
          Section {
            Button("Continue as guest") { session.continueAsGuest() }
              .font(Theme.action)
              .frame(maxWidth: .infinity)
              .foregroundStyle(Theme.accent)
          } footer: {
            Text("You can create an account later in Settings.")
          }
        }
      }
      .scrollContentBackground(.hidden)
      .background(Theme.bg)
      .toolbar {
        if isSheet {
          ToolbarItem(placement: .cancellationAction) {
            Button("Cancel") { dismiss() }
          }
        }
      }
      .onChange(of: mode) { _, _ in error = nil }
      .sheet(isPresented: $forgot) {
        ForgotPasswordView(email: email)
      }
    }
  }

  private func submit() async {
    busy = true
    error = nil
    defer { busy = false }
    let cleanEmail = email.trimmingCharacters(in: .whitespacesAndNewlines)
    do {
      if mode == .signIn {
        try await KitchenAPI.login(email: cleanEmail, password: password)
      } else {
        let name = householdName.trimmingCharacters(in: .whitespacesAndNewlines)
        try await KitchenAPI.signup(
          email: cleanEmail,
          password: password,
          householdName: name.isEmpty ? "My household" : name
        )
      }
      password = ""
      await session.refresh()
      if isSheet { dismiss() }
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}

/// Asks the server to email a reset link. The link opens the website to set a new password.
struct ForgotPasswordView: View {
  @Environment(\.dismiss) private var dismiss
  @State var email: String
  @State private var busy = false
  @State private var sent = false
  @State private var error: String?

  private var canSend: Bool {
    !busy && email.contains("@")
  }

  var body: some View {
    NavigationStack {
      Form {
        if sent {
          Section {
            VStack(alignment: .leading, spacing: 8) {
              Label("Check your email", systemImage: "envelope")
                .font(Theme.mealName)
                .foregroundStyle(Theme.ink)
              Text(
                "If \(email) has an account, a reset link is on its way. It works once, for 1 hour. After you set a new password, come back here and sign in."
              )
              .foregroundStyle(Theme.muted)
            }
            .padding(.vertical, 6)
          }
        } else {
          Section {
            TextField("Email", text: $email)
              .textContentType(.emailAddress)
              .keyboardType(.emailAddress)
              .textInputAutocapitalization(.never)
              .autocorrectionDisabled()
          } footer: {
            Text("We'll email you a link to set a new password.")
          }
          if let error {
            Section {
              ErrorBanner(message: error)
                .listRowInsets(EdgeInsets())
                .listRowBackground(Color.clear)
            }
          }
          Section {
            Button {
              Task { await send() }
            } label: {
              HStack {
                Spacer()
                if busy { ProgressView() } else { Text("Send reset link").bold() }
                Spacer()
              }
            }
            .disabled(!canSend)
            .listRowBackground(canSend ? Theme.accent : Theme.accent.opacity(0.4))
            .foregroundStyle(.white)
          }
        }
      }
      .scrollContentBackground(.hidden)
      .background(Theme.bg)
      .navigationTitle("Reset password")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button(sent ? "Done" : "Cancel") { dismiss() }
        }
      }
      .tint(Theme.accent)
    }
  }

  private func send() async {
    busy = true
    defer { busy = false }
    do {
      try await KitchenAPI.forgotPassword(
        email: email.trimmingCharacters(in: .whitespacesAndNewlines))
      sent = true
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}
