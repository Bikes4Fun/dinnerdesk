import Combine
import SwiftUI

/// Who is using the app: signed in, a guest, or not decided yet.
@MainActor
final class Session: ObservableObject {
  private static let guestKey = "dinnerdesk.guest"
  private static let feedbackTipKey = "dinnerdesk.feedbackTipSeen"
  private static let whatsNewSeenKey = "dinnerdesk.whatsNewSeen"

  // For a feature release or other major update, set a fresh ID and list only the changes
  // being announced. Keep that ID across routine builds, or set this to nil to retire it.
  private static let whatsNew: (id: String, changes: [String])? = nil

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
  private var whatsNewPending = false
  @Published var showWhatsNew = false
  var whatsNewChanges: [String] { Self.whatsNew?.changes ?? [] }
  /// How to send a TestFlight screenshot (FeedbackTipView). Set it from More to show it again.
  @Published var showFeedbackTip = false

  /// Give the TestFlight feedback tip priority over onboarding and release announcements.
  func checkTour() async {
    guard let status, !needsSignIn else { return }
    let key = "\(status.householdId ?? 0)"
    if tourCheckedFor != key {
      do {
        let prefs = try await KitchenAPI.prefs()
        tourCheckedFor = key
        tourPending = TourView.isDue(prefs)
        whatsNewPending = false
        if !tourPending, let announcement = Self.whatsNew, !announcement.changes.isEmpty {
          whatsNewPending = UserDefaults.standard.string(forKey: Self.whatsNewSeenKey) != announcement.id
        }
      } catch {
        guard !API.isCancellation(error) else { return }
        loadError = KitchenAPI.message(error)
      }
    }
    if !UserDefaults.standard.bool(forKey: Self.feedbackTipKey), await FeedbackTipView.isBeta() {
      showFeedbackTip = true
    } else {
      presentPendingTourOrAnnouncement()
    }
  }

  func feedbackTipClosed() {
    UserDefaults.standard.set(true, forKey: Self.feedbackTipKey)
    presentPendingTourOrAnnouncement()
  }

  private func presentPendingTourOrAnnouncement() {
    if tourPending {
      tourPending = false
      showTour = true
    } else if whatsNewPending {
      whatsNewPending = false
      showWhatsNew = true
    }
  }

  func whatsNewClosed() {
    if let announcement = Self.whatsNew {
      UserDefaults.standard.set(announcement.id, forKey: Self.whatsNewSeenKey)
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
  @State private var emailNoticeDismissed = false
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
            } else if let nudge = session.status?.emailNudge, !emailNoticeDismissed {
              VStack(alignment: .leading, spacing: 6) {
                Text("FYI: \(nudge) Fix it in More → Account & security.")
                  .font(Theme.subtitle).foregroundStyle(Theme.muted)
                  .fixedSize(horizontal: false, vertical: true)
                HStack {
                  Spacer()
                  Button("Dismiss") { emailNoticeDismissed = true }
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
    .sheet(isPresented: $session.showWhatsNew, onDismiss: { session.whatsNewClosed() }) {
      NavigationStack {
        ScrollView {
          VStack(alignment: .leading, spacing: 16) {
            ForEach(session.whatsNewChanges.indices, id: \.self) { index in
              Text(session.whatsNewChanges[index])
                .font(Theme.body)
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            }
          }
          .frame(maxWidth: .infinity, alignment: .leading)
          .padding(20)
        }
        .background(Theme.bg)
        .navigationTitle(Copy.text("tour.update.title"))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
          ToolbarItem(placement: .confirmationAction) {
            Button("Done") { session.showWhatsNew = false }
          }
        }
      }
      .tint(Theme.accent)
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
  @State private var agreedPrivacy = false
  @State private var showPrivacy = false

  init(isSheet: Bool = false) {
    self.isSheet = isSheet
  }

  private var canSubmit: Bool {
    !busy && email.trimmingCharacters(in: .whitespaces).count >= 3
      && password.count >= (mode == .signUp ? 8 : 1)
      && (mode == .signIn || agreedPrivacy)
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

        if mode == .signUp {
          Section {
            PrivacySummaryView(compact: true)
              .padding(.vertical, 6)
            Toggle(isOn: $agreedPrivacy) {
              Text(Copy.text("privacy.signup.checkbox")).font(Theme.subtitle).foregroundStyle(Theme.ink)
            }
            .toggleStyle(CheckboxToggleStyle())
            Button(Copy.text("privacy.agree.read")) { showPrivacy = true }
              .font(Theme.action)
              .foregroundStyle(Theme.accent)
          } header: {
            Text("Your privacy, in short")
          } footer: {
            if !agreedPrivacy { Text(Copy.text("privacy.signup.needed")) }
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
      .sheet(isPresented: $showPrivacy) {
        NavigationStack {
          PrivacyView().environmentObject(session)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { showPrivacy = false } } }
        }
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
          householdName: name.isEmpty ? "My household" : name,
          agreedPrivacy: agreedPrivacy
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
                "If \(email) has an account with a verified email, a reset link is on its way to that email. It works once, for 1 hour. After you set a new password, come back here and sign in."
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

/// A square checkbox for the privacy agreement: a switch reads as a setting, not an agreement.
struct CheckboxToggleStyle: ToggleStyle {
  func makeBody(configuration: Configuration) -> some View {
    Button { configuration.isOn.toggle() } label: {
      HStack(alignment: .top, spacing: 12) {
        Image(systemName: configuration.isOn ? "checkmark.square.fill" : "square")
          .font(.title2)
          .foregroundStyle(Theme.ink)
        configuration.label
          .multilineTextAlignment(.leading)
          .frame(maxWidth: .infinity, alignment: .leading)
      }
      .contentShape(Rectangle())
    }
    .buttonStyle(.plain)
    .frame(minHeight: 44)
    .accessibilityElement(children: .combine)
    .accessibilityAddTraits(configuration.isOn ? [.isButton, .isSelected] : .isButton)
  }
}
