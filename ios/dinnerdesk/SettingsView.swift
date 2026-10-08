import SwiftUI
import WebKit

/// Settings: food filters, account & household, Taste Lab. Push it from a NavigationStack (More tab).
struct SettingsView: View {
  @EnvironmentObject private var session: Session

  var body: some View {
    List {
      Section {
        NavigationLink {
          FiltersView()
        } label: {
          KitchenIconRow(title: "Filters", systemImage: "slider.horizontal.3")
        }
        NavigationLink {
          AccountView()
        } label: {
          KitchenIconRow(
            title: "Account & security",
            systemImage: "person.crop.circle",
            value: session.status?.email ?? "Guest"
          )
        }
        NavigationLink {
          TasteLabView()
        } label: {
          KitchenIconRow(title: "Taste Lab", systemImage: "hand.draw")
        }
        Button {
          session.showTour = true
        } label: {
          KitchenIconRow(title: "Quick start tour", systemImage: "arrow.counterclockwise")
        }
        .accessibilityHint("Replays the first-run tour")
        NavigationLink {
          PrivacyView()
        } label: {
          KitchenIconRow(title: "Privacy", systemImage: "hand.raised")
        }
      }
      .kitchenRows()

      KitchenSection("About recipes & photos") {
        Text(Copy.text("settings.gold-star"))
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .accessibilityIdentifier("tip.settings.gold-star")
          .kitchenBareRow()
      }
    }
    .kitchenList()
    .navigationTitle("Settings")
    .largeNavigationTitle()
  }
}

/// What you eat: diet, things to avoid, cook time. Saved to household prefs.filters (same as the website).
struct FiltersView: View {
  @EnvironmentObject private var store: Store
  static let diets = ["omnivore", "pescatarian", "vegetarian", "vegan", "gluten-free", "dairy-free"]
  /// Pick one of these. The others (gluten-free, dairy-free) combine with it.
  static let exclusiveDiets: Set<String> = ["omnivore", "pescatarian", "vegetarian", "vegan"]
  static let avoids = ["fish", "shellfish", "peanuts", "cilantro", "spicy"]
  struct TimeOption: Identifiable {
    let id: String
    let label: String
  }

  static let times = [
    TimeOption(id: "any", label: "Any time"),
    TimeOption(id: "30", label: "30 min or less"),
    TimeOption(id: "45", label: "45 min or less"),
  ]

  @State private var diets: Set<String> = ["omnivore"]
  @State private var avoids: Set<String> = []
  @State private var time = "any"
  @State private var loaded = false
  @State private var error: String?

  var body: some View {
    List {
      if let error {
        ErrorBanner(message: error).kitchenBareRow()
      }
      KitchenSection("Diet") {
        ForEach(Self.diets, id: \.self) { item in
          CheckRow(label: item.capitalized, on: diets.contains(item)) {
            toggleDiet(item)
          }
        }
      }
      .kitchenRows()
      KitchenSection("Avoid") {
        CheckRow(label: "None", on: avoids.isEmpty) {
          avoids = []
          save()
        }
        ForEach(Self.avoids, id: \.self) { item in
          CheckRow(label: item.capitalized, on: avoids.contains(item)) {
            toggleAvoid(item)
          }
        }
      }
      .kitchenRows()
      KitchenSection("Cook time") {
        ForEach(Self.times) { option in
          CheckRow(label: option.label, on: time == option.id) {
            time = option.id
            save()
          }
        }
      }
      .kitchenRows()
    }
    .kitchenList()
    .navigationTitle("Filters")
    .navigationBarTitleDisplayMode(.inline)
    .task { await load() }
  }

  /// Tapping a diet. Omnivore, pescatarian, vegetarian and vegan rule each other out, so
  /// picking one switches to it. Gluten-free and dairy-free toggle on their own.
  static func toggled(_ diets: Set<String>, _ item: String) -> Set<String> {
    var next = diets
    if exclusiveDiets.contains(item) {
      next.subtract(exclusiveDiets)
      next.insert(item)
    } else if next.contains(item) {
      next.remove(item)
    } else {
      next.insert(item)
    }
    return next
  }

  /// Older saves could hold several of omnivore / vegetarian / vegan; keep the strictest.
  static func cleaned(_ saved: [String]) -> Set<String> {
    var next = Set(saved)
    let picked = ["vegan", "vegetarian", "pescatarian", "omnivore"].first { next.contains($0) }
    next.subtract(exclusiveDiets)
    if let picked { next.insert(picked) }
    return next
  }

  private func toggleDiet(_ item: String) {
    diets = Self.toggled(diets, item)
    save()
  }

  private func toggleAvoid(_ item: String) {
    if avoids.contains(item) { avoids.remove(item) } else { avoids.insert(item) }
    save()
  }

  private func load() async {
    do {
      let filters = try await KitchenAPI.prefs()["filters"] as? [String: Any] ?? [:]
      if let d = filters["diets"] as? [String], !d.isEmpty { diets = Self.cleaned(d) }
      if let a = filters["avoids"] as? [String] { avoids = Set(a) }
      if let t = filters["time"] as? String { time = t }
      loaded = true
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func save() {
    guard loaded else { return }
    let body: [String: Any] = [
      "diets": Self.diets.filter { diets.contains($0) },
      "avoids": Self.avoids.filter { avoids.contains($0) },
      "time": time,
    ]
    Task {
      do {
        try await KitchenAPI.savePrefs(["filters": body])
        // Recipes follow the filters, so refresh the list behind this screen.
        await store.searchRecipes("")
      } catch {
        self.error = KitchenAPI.message(error)
      }
    }
  }
}

private struct CheckRow: View {
  let label: String
  let on: Bool
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      HStack {
        Text(label).font(Theme.mealName).foregroundStyle(Theme.ink)
        Spacer()
        if on {
          Image(systemName: "checkmark").foregroundStyle(Theme.accent).fontWeight(.semibold)
        }
      }
    }
    .accessibilityAddTraits(on ? .isSelected : [])
  }
}

/// Sign in/out, password, household invites and members.
struct AccountView: View {
  @EnvironmentObject private var session: Session
  @State private var members: [HouseholdMember] = []
  @State private var currentPassword = ""
  @State private var newPassword = ""
  @State private var inviteURL: URL?
  @State private var signingIn = false
  @State private var confirmEverywhere = false
  @State private var busy = false
  @State private var message: String?
  @State private var error: String?

  private var signedIn: Bool { session.status?.authenticated == true }

  var body: some View {
    List {
      if let message {
        Text(message).foregroundStyle(KitchenStyle.ok).kitchenBareRow()
      }
      if let error {
        ErrorBanner(message: error).kitchenBareRow()
      }

      if signedIn {
        KitchenSection("Signed in") {
          KitchenIconRow(title: session.status?.email ?? "", systemImage: "person.crop.circle")
        }
        .kitchenRows()

        KitchenSection("Password") {
          SecureField("Current password", text: $currentPassword)
            .textContentType(.password)
          SecureField("New password (8+ characters)", text: $newPassword)
            .textContentType(.newPassword)
          Button("Change password") { Task { await changePassword() } }
            .disabled(busy || currentPassword.isEmpty || newPassword.count < 8)
        }
        .kitchenRows()

        KitchenSection("Household") {
          if let inviteURL {
            ShareLink(item: inviteURL) {
              Label("Share invite link", systemImage: "square.and.arrow.up")
            }
            Text(Copy.text("settings.invite-link"))
              .font(Theme.subtitle)
              .foregroundStyle(Theme.muted)
              .accessibilityIdentifier("tip.settings.invite-link")
          } else {
            Button("Invite someone to this household") { Task { await invite() } }
              .disabled(busy)
          }
          ForEach(members) { member in
            HStack {
              Text(member.email)
              if member.email == session.status?.email {
                Spacer()
                Text("You").foregroundStyle(Theme.muted)
              }
            }
            .deleteDisabled(member.email == session.status?.email)
          }
          .onDelete { offsets in
            let doomed = offsets.map { members[$0] }
            Task {
              for member in doomed { await remove(member) }
            }
          }
        }
        .kitchenRows()

        Section {
          Button("Sign out") { Task { await session.signOut() } }
          Button("Sign out everywhere", role: .destructive) { confirmEverywhere = true }
        } footer: {
          Text(Copy.text("settings.sign-out-everywhere"))
            .font(Theme.subtitle)
            .foregroundStyle(Theme.muted)
            .accessibilityIdentifier("tip.settings.sign-out-everywhere")
        }
        .kitchenRows()
      } else {
        Section {
          Text(
            "You're using \(Copy.appName) as a guest. Create an account to keep your plan and share it with your household."
          )
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .kitchenBareRow()
          Button("Sign in or create account") { signingIn = true }
            .font(Theme.mealName)
            .kitchenRows()
        }
      }
    }
    .kitchenList()
    .tint(Theme.accent)
    .navigationTitle("Account & security")
    .navigationBarTitleDisplayMode(.inline)
    .task { await loadMembers() }
    .sheet(isPresented: $signingIn, onDismiss: { Task { await loadMembers() } }) {
      AuthView(isSheet: true)
        .environmentObject(session)
    }
    .confirmationDialog(
      "Sign out on every device?", isPresented: $confirmEverywhere, titleVisibility: .visible
    ) {
      Button("Sign out everywhere", role: .destructive) { Task { await signOutEverywhere() } }
    }
  }

  private func loadMembers() async {
    guard signedIn else { return }
    do {
      members = try await KitchenAPI.members()
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func changePassword() async {
    busy = true
    defer { busy = false }
    do {
      try await KitchenAPI.changePassword(current: currentPassword, new: newPassword)
      currentPassword = ""
      newPassword = ""
      message = "Password changed."
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func invite() async {
    busy = true
    defer { busy = false }
    do {
      inviteURL = try await KitchenAPI.createInvite()
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func remove(_ member: HouseholdMember) async {
    members.removeAll { $0.id == member.id }
    do {
      try await KitchenAPI.removeMember(member.id)
    } catch {
      self.error = KitchenAPI.message(error)
      await loadMembers()
    }
  }

  private func signOutEverywhere() async {
    do {
      try await KitchenAPI.logoutEverywhere()
    } catch {
      self.error = KitchenAPI.message(error)
    }
    await session.signOut()
  }
}

/// Taste Lab stays a web page (the swipe engine lives on the server); shown in a web view.
struct TasteLabView: View {
  var swipe = false
  @State private var loading = true
  @State private var failed: String?

  var body: some View {
    ZStack {
      TasteLabWebView(
        url: Self.pageURL(swipe: swipe),
        loading: $loading,
        failed: $failed
      )
      .ignoresSafeArea(.container, edges: .bottom)
      if loading && failed == nil {
        ProgressView()
      }
      if let failed {
        VStack(spacing: 12) {
          EmptyState(
            title: "Taste Lab didn't load", message: failed, systemImage: "wifi.exclamationmark")
          Button("Try again") {
            self.failed = nil
            loading = true
          }
          .font(Theme.action)
          .foregroundStyle(Theme.bg)
          .padding(.horizontal, 22)
          .padding(.vertical, 12)
          .background(Theme.ink, in: RoundedRectangle(cornerRadius: 12))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.bg)
      }
    }
    .background(Theme.bg)
    .navigationTitle("Taste Lab")
    .navigationBarTitleDisplayMode(.inline)
  }

  private static func pageURL(swipe: Bool) -> URL {
    let base = API.origin.appending(path: "tastelab/")
    guard var parts = URLComponents(url: base, resolvingAgainstBaseURL: false) else { return base }
    var items = [URLQueryItem(name: "chrome", value: "app")]
    if swipe { items.append(URLQueryItem(name: "swipe", value: "1")) }
    parts.queryItems = items
    return parts.url ?? base
  }
}

private struct TasteLabWebView: UIViewRepresentable {
  let url: URL
  @Binding var loading: Bool
  @Binding var failed: String?

  func makeCoordinator() -> Coordinator {
    Coordinator(parent: self)
  }

  func makeUIView(context: Context) -> WKWebView {
    let view = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
    view.navigationDelegate = context.coordinator
    view.isOpaque = false
    view.backgroundColor = UIColor(Theme.bg)
    view.scrollView.backgroundColor = UIColor(Theme.bg)
    view.underPageBackgroundColor = UIColor(Theme.bg)
    context.coordinator.load(view)
    return view
  }

  func updateUIView(_ view: WKWebView, context: Context) {
    context.coordinator.parent = self
    // "Try again" clears the failure and sets loading; reload once when that happens.
    if loading, failed == nil, context.coordinator.needsRetry {
      context.coordinator.needsRetry = false
      context.coordinator.load(view)
    }
  }

  final class Coordinator: NSObject, WKNavigationDelegate {
    var parent: TasteLabWebView
    var needsRetry = false

    init(parent: TasteLabWebView) {
      self.parent = parent
    }

    /// URLSession keeps the sign-in cookie. The web view will not send it unless we copy it over.
    func load(_ view: WKWebView) {
      let url = parent.url
      let store = view.configuration.websiteDataStore.httpCookieStore
      let cookies = Self.sessionCookies(for: url)
      let group = DispatchGroup()
      for cookie in cookies {
        group.enter()
        store.setCookie(cookie) { group.leave() }
      }
      group.notify(queue: .main) {
        view.load(URLRequest(url: url))
      }
    }

    private static func sessionCookies(for url: URL) -> [HTTPCookie] {
      let host = url.host?.lowercased() ?? ""
      return (HTTPCookieStorage.shared.cookies ?? []).filter { cookie in
        let domain = cookie.domain.lowercased().trimmingCharacters(
          in: CharacterSet(charactersIn: "."))
        return host == domain || host.hasSuffix(".\(domain)")
      }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
      parent.loading = false
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
      needsRetry = true
      parent.loading = false
      parent.failed = error.localizedDescription
    }

    func webView(
      _ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!,
      withError error: Error
    ) {
      needsRetry = true
      parent.loading = false
      parent.failed = error.localizedDescription
    }
  }
}

private struct PrivacyView: View {
  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 12) {
        Text(
          "Dinnerdesk is a meal planner for a household. This is what we store, and what we do with it."
        )
        section(
          "Account",
          """
          If you create an account we store your email, a hash of your password (not the password), and your household name. A sign-in session lasts 30 days. You can sign out of this device, or every device, from Account & security.

          Forgot-password emails are sent by Resend. We store a hash of the reset link, not the link. The link works once, for one hour. We answer the same way whether or not that email has an account.

          If you subscribe to the email newsletter, we store that choice with your household and may email you DinnerDesk Deals. Turn it off anytime from Settings.
          """)
        section(
          "Your kitchen",
          """
          Plans, grocery lists, pantry, recipe edits, favorites, hides, to-try marks, filters, and store or aisle choices are stored for your household. Taste Lab stores the meals you like or pass, plus diet, allergy, and dislike choices. When you are signed in, those answers are tied to your account and used to suggest meals. Thumbs up or down on a planned meal, and on a prep step, are stored for your household and used to choose future meal suggestions. Prep step votes are kept so we can improve prep suggestions.

          Someone you invite joins that same household and can see and change it. Invite links expire after 7 days. You can remove a member from Account & security. Removing them ends their access.
          """)
        section(
          "Without an account",
          """
          If sign-in is not required, the app uses one shared guest household on the server. Anything added there is not private to you. Create an account for a household of your own.
          """)
        section(
          "What we don’t collect",
          """
          We don’t sell your data. We don’t take payment, location, or health data. Nutrition-tracker sync is not built. We don’t run ads or analytics.

          Recipe photos in the app are ones we have marked as ours to use. We don’t collect photos, reviews, or comments from cooks yet.
          """)
        section(
          "Deleting data",
          """
          There is no delete-account button yet. Remove other people from your household in Account & security. To delete an account and that household’s kitchen, ask the person who runs this Dinnerdesk.
          """)
      }
      .font(Theme.body)
      .foregroundStyle(Theme.ink)
      .padding(16)
      .frame(maxWidth: .infinity, alignment: .leading)
    }
    .background(Theme.bg)
    .navigationTitle("Privacy")
    .navigationBarTitleDisplayMode(.inline)
  }

  private func section(_ title: String, _ body: String) -> some View {
    VStack(alignment: .leading, spacing: 6) {
      Text(title).font(Theme.title)
      Text(body).foregroundStyle(Theme.muted)
    }
    .padding(.top, 8)
  }
}
