import Combine
import SwiftUI

/// Who is using the app: signed in, a guest, or not decided yet.
@MainActor
final class Session: ObservableObject {
  private static let guestKey = "dinnerdesk.guest"
  private static let feedbackTipKey = "dinnerdesk.feedbackTipSeen"

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
    return !guest
  }

  var canContinueAsGuest: Bool { true }

  /// Show the quick start tour. Set it from anywhere (More, Settings) to replay the tour.
  @Published var showTour = false
  /// The household the tour was last checked for, so signing in from a guest kitchen checks again.
  private var tourCheckedFor: String?
  /// The tour is due but waits until the feedback tip is closed.
  private var tourPending = false
  /// How to send a TestFlight screenshot (FeedbackTipView). Set it from More to show it again.
  @Published var showFeedbackTip = false

  /// First run: the feedback tip once on this device (TestFlight only), then the tour once if the
  /// household hasn't finished or skipped the current version (TourView.version), or this device
  /// is on a new build.
  func checkTour() async {
    guard let status, !needsSignIn else { return }
    let key = "\(status.householdId ?? 0)"
    if tourCheckedFor != key {
      do {
        let prefs = try await KitchenAPI.prefs()
        tourCheckedFor = key
        if TourView.isDue(prefs) || TourView.isNewBuild {
          tourPending = true
        } else {
          // Nothing due: start counting from this build, so the next build opens the tour.
          TourView.noteBuild()
        }
      } catch {
        guard !API.isCancellation(error) else { return }
        loadError = KitchenAPI.message(error)
      }
    }
    if !UserDefaults.standard.bool(forKey: Self.feedbackTipKey), await FeedbackTipView.isBeta() {
      showFeedbackTip = true
    } else if tourPending {
      tourPending = false
      showTour = true
    }
  }

  /// The feedback tip was closed: remember it, then open the tour if it was waiting.
  func feedbackTipClosed() {
    UserDefaults.standard.set(true, forKey: Self.feedbackTipKey)
    if tourPending {
      tourPending = false
      showTour = true
    }
  }

  /// Everyone who creates an account sees the feedback tip again, even on a device that has.
  func accountCreated() {
    UserDefaults.standard.removeObject(forKey: Self.feedbackTipKey)
  }

  func refresh() async {
    do {
      let next = try await AuthAPI.status()
      // Clear saved plans and recipes before showing a different account's data.
      ResponseCache.noteAccount(next.authenticated ? "\(next.email ?? ""):\(next.householdId ?? 0)" : nil)
      WatchConnectivityManager.shared.publishSession()
      status = next
      loadError = nil
      if status?.authenticated == true { guest = false }
    } catch {
      guard !API.isCancellation(error) else { return }
      loadError = KitchenAPI.message(error)
    }
  }

  func continueAsGuest() {
    guest = true
  }

  func signOut() async {
    do { try await AuthAPI.logout() } catch {
      loadError = KitchenAPI.message(error)
      return
    }
    guest = false
    tourCheckedFor = nil
    await refresh()
  }

  /// After the server deleted the account its session is already gone, so skip logout.
  func accountDeleted() async {
    guest = false
    tourCheckedFor = nil
    await refresh()
  }
}

/// Wrap the app's tabs in this: shows sign-in first when needed, then `content`.
/// `content` is only built once signed in (or a guest), so its data loads for the right household.
struct AuthGate<Content: View>: View {
  @StateObject private var session = Session()
  @Environment(\.scenePhase) private var scenePhase
  @State private var guestNoticeDismissed = false
  @State private var showSignIn = false
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
          .safeAreaInset(edge: .top) {
            if session.status?.authenticated != true && !guestNoticeDismissed {
              VStack(alignment: .leading, spacing: 6) {
                Text("Guest data can be lost if you reinstall the app. Create an account to protect it.")
                  .font(Theme.subtitle).foregroundStyle(Theme.muted)
                HStack {
                  Button("Sign in or create account") { showSignIn = true }
                  Spacer()
                  Button("Dismiss") { guestNoticeDismissed = true }
                }.font(Theme.subtitle)
              }.padding().background(Theme.bg)
            }
          }
          // Signing up from a guest kitchen keeps the same household, so check again on close.
          .sheet(isPresented: $showSignIn, onDismiss: { Task { await session.checkTour() } }) {
            AuthView(isSheet: true).environmentObject(session)
          }
          .overlay(alignment: .top) {
            if let error = session.loadError { ErrorBanner(message: error).padding() }
          }
          .task(id: session.status?.householdId) { await session.checkTour() }
      }
    }
    .sheet(isPresented: $session.showFeedbackTip, onDismiss: { session.feedbackTipClosed() }) {
      FeedbackTipView()
    }
    .fullScreenCover(isPresented: $session.showTour) {
      TourView()
        .environmentObject(session)
    }
    .environmentObject(session)
    .task { await session.refresh() }
    .onChange(of: scenePhase) { _, next in
      if next == .active { Task { await session.refresh() } }
    }
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
    !busy && email.trimmingCharacters(in: .whitespaces).count >= 3
      && password.count >= (mode == .signUp ? 8 : 1)
  }

  /// Signing up with a username instead of an email.
  private var usernameOnly: Bool {
    mode == .signUp && !email.trimmingCharacters(in: .whitespaces).isEmpty && !email.contains("@")
  }

  var body: some View {
    NavigationStack {
      Form {
        Section {
          VStack(alignment: .leading, spacing: 6) {
            Text(Copy.appName)
              .font(Theme.bigTitle)
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
          TextField("Email or username", text: $email)
            .textContentType(.username)
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
            VStack(alignment: .leading, spacing: 6) {
              Text("At least 8 characters.")
              if usernameOnly {
                Text("No email means no password reset. If you forget your password, this account can't be recovered.")
                  .foregroundStyle(Theme.accent)
              }
            }
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
            Text("All features work as a guest. Create an account in Settings to protect your data; reinstalling the app or clearing its data can lose access.")
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
        try await AuthAPI.login(email: cleanEmail, password: password)
      } else {
        let name = householdName.trimmingCharacters(in: .whitespacesAndNewlines)
        try await AuthAPI.signup(
          email: cleanEmail,
          password: password,
          householdName: name.isEmpty ? "My household" : name
        )
        session.accountCreated()
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
      try await AuthAPI.forgotPassword(
        email: email.trimmingCharacters(in: .whitespacesAndNewlines))
      sent = true
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}
