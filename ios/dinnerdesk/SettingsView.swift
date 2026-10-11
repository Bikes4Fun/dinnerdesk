import SwiftUI
import WebKit
import UIKit

/// Settings: food filters, account & household, Taste Lab. Push it from a NavigationStack (More tab).
struct SettingsView: View {
  @EnvironmentObject private var session: Session

  var body: some View {
    List {
      Section {
        // NavigationLink {
        //   FiltersView()
        // } label: {
        //   ThemeIconRow(title: "Filters", systemImage: "slider.horizontal.3")
        // }
        NavigationLink {
          AccountView()
        } label: {
          ThemeIconRow(
            title: "Account & security",
            systemImage: "person.crop.circle",
            value: session.status?.email ?? "Guest"
          )
        }

        NavigationLink {
          PrivacyView()
        } label: {
          ThemeIconRow(title: "Privacy", systemImage: "hand.raised")
        }
        Link(destination: API.origin.appending(path: "support")) {
          ThemeIconRow(title: "Help & support", systemImage: "questionmark.circle")
        }
        .accessibilityHint("Opens the support page in Safari")

          if let url = URL(string: "https://dinnerdesk.computerscience.build") {
            Link(destination: url) {
              ThemeIconRow(title: "\(Copy.appName) on the web", systemImage: "safari")
            }
          }
          Link(destination: URL(string: "https://x.com/DinnerDesk")!) {
            ThemeIconRow(
              title: "Twitter", systemImage: "bubble.left.and.bubble.right", value: "@DinnerDesk")
          }
      }
      .themeRows()

      ThemeSection("About recipes & photos") {
        Text(Copy.text("settings.gold-star"))
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .accessibilityIdentifier("tip.settings.gold-star")
          .themeBareRow()
      }
    }
    .themeList()
    .navigationTitle("Settings")
    .largeNavigationTitle()
  }
}

/// What you eat: diet, allergies, things to avoid, cook time. Saved to household prefs.filters.
/// This is the only filter system: the website and Taste Lab edit the same lists
/// (app/domain/diet_filter.py; a test keeps these copies equal).
struct FiltersView: View {
  @EnvironmentObject private var store: Store
  static let diets = ["omnivore", "pescatarian", "vegetarian", "vegan", "gluten-free", "dairy-free"]
  /// Pick one of these. The others (gluten-free, dairy-free) combine with it.
  static let exclusiveDiets: Set<String> = ["omnivore", "pescatarian", "vegetarian", "vegan"]
  static let allergens = [
    ("soy", "Soy"), ("peanut", "Peanut"), ("tree-nuts", "Tree nuts"), ("dairy", "Dairy"), ("egg", "Egg"),
    ("gluten", "Gluten"), ("sesame", "Sesame"), ("fish", "Fish"), ("shellfish", "Shellfish"),
  ]
  static let avoids = [
    "fish", "cilantro", "mushrooms", "onions", "bell peppers", "olives", "goat cheese", "nuts",
    "beans", "tofu", "eggplant", "brussels sprouts", "coconut", "spicy",
  ]
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
  @State private var allergens: Set<String> = []
  @State private var avoids: Set<String> = []
  @State private var otherAllergens: [String] = []
  @State private var otherAvoids: [String] = []
  @State private var time = "any"
  @State private var loaded = false
  @State private var error: String?

  @State private var otherAllergenOpen = false
  @State private var otherAvoidOpen = false
  /// "Saving…" then "Saved" after each change (#85), so a tap never looks like it did nothing.
  enum SaveState { case idle, saving, saved }
  @State private var saveState = SaveState.idle
  @State private var saveCount = 0
  @State private var saveTask: Task<Void, Never>?

  static let dietLabels = [
    "omnivore": "Omnivore", "pescatarian": "Pescatarian", "vegetarian": "Vegetarian", "vegan": "Vegan",
    "gluten-free": "Gluten-free", "dairy-free": "Dairy-free",
  ]

  /// Same look as Taste Lab's Filters screen: small caps headings and wrapping chips
  /// (aubergine when on), with None and Other chips for allergies and avoids.
  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 22) {
        if let error { ErrorBanner(message: error) }
        Text("We’ll hide meals that don’t fit. Same filters as Taste Lab.")
          .font(Theme.subtitle).foregroundStyle(Theme.muted)
          .fixedSize(horizontal: false, vertical: true)

        filterBlock("Diet") {
          ForEach(Self.diets, id: \.self) { item in
            FilterChip(label: Self.dietLabels[item] ?? item.capitalized, on: diets.contains(item)) { toggleDiet(item) }
          }
        }

        filterBlock("Allergies") {
          FilterChip(label: "None", on: allergens.isEmpty && otherAllergens.isEmpty) {
            allergens = []
            otherAllergens = []
            otherAllergenOpen = false
            save()
          }
          ForEach(Self.allergens, id: \.0) { item in
            FilterChip(label: item.1, on: allergens.contains(item.0)) {
              if allergens.contains(item.0) { allergens.remove(item.0) } else { allergens.insert(item.0) }
              save()
            }
          }
          ForEach(otherAllergens, id: \.self) { name in removableChip(name) { otherAllergens.removeAll { $0 == name }; save() } }
          FilterChip(label: "Other", on: otherAllergenOpen) { otherAllergenOpen.toggle() }
        } extra: {
          if otherAllergenOpen {
            OtherField(label: "Other allergies", selected: $otherAllergens) {
              let known = Self.allergens.map(\.0)
              allergens.formUnion(otherAllergens.filter { known.contains($0) })
              otherAllergens.removeAll { known.contains($0) }
              save()
            }
          }
        }

        filterBlock("I avoid") {
          FilterChip(label: "None", on: avoids.isEmpty && otherAvoids.isEmpty) {
            avoids = []
            otherAvoids = []
            otherAvoidOpen = false
            save()
          }
          ForEach(Self.avoids, id: \.self) { item in
            FilterChip(label: item, on: avoids.contains(item)) { toggleAvoid(item) }
          }
          ForEach(otherAvoids, id: \.self) { name in removableChip(name) { otherAvoids.removeAll { $0 == name }; save() } }
          FilterChip(label: "Other", on: otherAvoidOpen) { otherAvoidOpen.toggle() }
        } extra: {
          if otherAvoidOpen {
            OtherField(label: "Other foods to avoid", selected: $otherAvoids) {
              avoids.formUnion(otherAvoids.filter { Self.avoids.contains($0) })
              otherAvoids.removeAll { Self.avoids.contains($0) }
              save()
            }
          }
        }

        filterBlock("Cook time") {
          ForEach(Self.times) { option in
            FilterChip(label: option.label, on: time == option.id) {
              time = option.id
              save()
            }
          }
        }
      }
      .padding(.horizontal, 16)
      .padding(.vertical, 12)
      .frame(maxWidth: .infinity, alignment: .leading)
    }
    .background(Theme.bg)
    .navigationTitle("Filters")
    .navigationBarTitleDisplayMode(.inline)
    .toolbar {
      ToolbarItem(placement: .topBarTrailing) {
        Group {
          switch saveState {
          case .idle: EmptyView()
          case .saving:
            HStack(spacing: 6) { ProgressView().controlSize(.small); Text("Saving…") }
          case .saved:
            Label("Saved", systemImage: "checkmark").labelStyle(.titleAndIcon)
          }
        }
        .font(Theme.count).foregroundStyle(Theme.muted)
        .animation(.easeInOut(duration: 0.2), value: saveState)
        .accessibilityElement(children: .combine)
      }
    }
    .task { await load() }
  }

  private func filterBlock<Chips: View>(_ title: String, @ViewBuilder chips: () -> Chips) -> some View {
    filterBlock(title, chips: chips) { EmptyView() }
  }

  private func filterBlock<Chips: View, Extra: View>(
    _ title: String, @ViewBuilder chips: () -> Chips, @ViewBuilder extra: () -> Extra
  ) -> some View {
    VStack(alignment: .leading, spacing: 8) {
      Text(title.uppercased())
        .font(Theme.sectionHeader).tracking(1).foregroundStyle(Theme.muted)
        .accessibilityAddTraits(.isHeader)
      KitchenFlow(spacing: 6) { chips() }
      extra()
    }
  }

  /// An Other word you added: shown on, tap to remove it.
  private func removableChip(_ name: String, remove: @escaping () -> Void) -> some View {
    FilterChip(label: "\(name) ✕", on: true, action: remove)
      .accessibilityLabel("Remove \(name)")
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

  /// "kale, anchovies" → ["kale", "anchovies"], lowercased, no repeats.
  static func words(_ raw: String) -> [String] {
    var out: [String] = []
    for part in raw.split(separator: ",") {
      let word = part.trimmingCharacters(in: .whitespaces).lowercased()
      if !word.isEmpty && !out.contains(word) { out.append(word) }
    }
    return out
  }

  /// Chips in list order, then the Other words that aren't chips.
  static func saved(_ picked: Set<String>, known: [String], other: String) -> [String] {
    known.filter { picked.contains($0) } + words(other).filter { !known.contains($0) }
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
      if let a = filters["allergens"] as? [String] {
        let known = Self.allergens.map(\.0)
        allergens = Set(a.filter { known.contains($0) })
        otherAllergens = a.filter { !known.contains($0) }
      }
      if let a = filters["avoids"] as? [String] {
        avoids = Set(a.filter { Self.avoids.contains($0) })
        otherAvoids = a.filter { !Self.avoids.contains($0) }
      }
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
      "allergens": Self.allergens.map(\.0).filter { allergens.contains($0) } + otherAllergens,
      "avoids": Self.avoids.filter { avoids.contains($0) } + otherAvoids,
      "time": time,
    ]
    saveCount += 1
    let mine = saveCount
    saveState = .saving
    let previous = saveTask
    saveTask = Task {
      await previous?.value
      guard mine == saveCount else { return }
      do {
        try await KitchenAPI.savePrefs(["filters": body])
        error = nil
        if mine == saveCount {
          saveState = .saved
          UIAccessibility.post(notification: .announcement, argument: "Filters saved")
        }
        // Recipes follow the filters, so refresh the list behind this screen.
        await store.searchRecipes("")
        Task {
          try? await Task.sleep(for: .seconds(2))
          if mine == saveCount, saveState == .saved { saveState = .idle }
        }
      } catch {
        if mine == saveCount { saveState = .idle }
        self.error = KitchenAPI.message(error)
      }
    }
  }
}

/// Comma-separated words that aren't in the list. Saves when you press Return or leave the field.
private struct OtherField: View {
  let label: String
  @Binding var selected: [String]
  let onCommit: () -> Void
  @State private var query = ""
  @State private var matches: [String] = []
  @State private var loading = false
  @State private var error: String?

  var body: some View {
    VStack(alignment: .leading, spacing: 10) {
      TextField("Search foods, e.g. bell peppers or ground", text: $query)
        .textInputAutocapitalization(.never)
        .autocorrectionDisabled()
        .font(Theme.body)
        .padding(12)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
        .accessibilityLabel("Search \(label.lowercased())")
      if loading { ProgressView() }
      if let error { Text(error).font(Theme.subtitle) }
      // Matches as chips (#85): tap one to add it; it moves up with the other picked chips.
      KitchenFlow(spacing: 6) {
        ForEach(matches.filter { !selected.contains($0) }, id: \.self) { name in
          FilterChip(label: "+ \(name)", on: false) {
            selected.append(name)
            onCommit()
          }
          .accessibilityLabel("Add \(name)")
        }
      }
      if !loading && error == nil && !query.isEmpty && matches.isEmpty {
        Text("No matching foods. Try another name.").font(Theme.subtitle)
      }
    }
    .task(id: query) {
      matches = []
      error = nil
      guard !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { loading = false; return }
      loading = true
      do {
        try await Task.sleep(for: .milliseconds(250))
        let box: KitchenItemSearch = try await API.get("filter-items", query: ["q": query], reportErrors: false)
        try Task.checkCancellation()
        matches = box.items.map(\.name)
        loading = false
      } catch {
        if !API.isCancellation(error) { self.error = "Couldn't search foods. Please try again."; loading = false }
      }
    }
  }
}

/// Taste Lab's chip: soft aubergine tint, filled aubergine when on.
private struct FilterChip: View {
  let label: String
  let on: Bool
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      Text(label).font(Theme.chipLabel)
        .foregroundStyle(on ? Theme.bg : Theme.ink)
        .multilineTextAlignment(.leading)
        .fixedSize(horizontal: false, vertical: true)
        .padding(.horizontal, 13)
        .padding(.vertical, 9)
        .frame(minHeight: 40)
        .background(on ? Theme.ink : Theme.aubergineTint, in: Capsule())
    }
    .buttonStyle(.plain)
    .accessibilityAddTraits(on ? .isSelected : [])
  }
}

/// Sign in/out, password, household invites and members.
struct AccountView: View {
  @EnvironmentObject private var session: Session
  @State private var members: [HouseholdMember] = []
  @State private var householdName = ""
  @State private var inviteURL: URL?
  @State private var signingIn = false
  @State private var confirmEverywhere = false
  @State private var deletingAccount = false
  @State private var busy = false
  @State private var message: String?
  @State private var error: String?

  private var otherMembers: [HouseholdMember] { members.filter { $0.email != session.status?.email } }

  private var signedIn: Bool { session.status?.authenticated == true }

  var body: some View {
    List {
      if let message {
        Text(message).foregroundStyle(Theme.ok).themeBareRow()
      }
      if let error {
        ErrorBanner(message: error).themeBareRow()
      }

      if signedIn {
        ThemeSection("Signed in") {
          Label(session.status?.email ?? "", systemImage: "person.crop.circle")
            .font(Theme.body).foregroundStyle(Theme.ink)
            .fixedSize(horizontal: false, vertical: true)
        }
        .themeRows()

        ThemeSection("Password") {
          Button { Task { await resetPassword() } } label: {
            Label("Reset password", systemImage: "key")
          }
          .disabled(busy)
          Text("Email a reset link to your signed-in address.")
            .font(Theme.subtitle).foregroundStyle(Theme.muted)
        }
        .themeRows()

        ThemeSection("Household") {
          TextField("Household name", text: $householdName)
            .textContentType(.organizationName)
            .onChange(of: householdName) { _, name in if name.count > 80 { householdName = String(name.prefix(80)) } }
            .onSubmit { Task { await saveHouseholdName() } }
          Button("Save household name") { Task { await saveHouseholdName() } }
            .disabled(busy || householdName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

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
          ForEach(otherMembers) { member in
            Text(member.email).fixedSize(horizontal: false, vertical: true)
          }
          .onDelete { offsets in
            let doomed = offsets.map { otherMembers[$0] }
            Task { for member in doomed { await remove(member) } }
          }
        }
        .themeRows()

        Section {
          Button("Sign out") { Task { await session.signOut() } }
          Button("Sign out everywhere", role: .destructive) { confirmEverywhere = true }
        } footer: {
          Text(Copy.text("settings.sign-out-everywhere"))
            .font(Theme.subtitle)
            .foregroundStyle(Theme.muted)
            .accessibilityIdentifier("tip.settings.sign-out-everywhere")
        }
        .themeRows()

        Section {
          Button("Delete account", role: .destructive) { deletingAccount = true }
        } footer: {
          Text(otherMembers.isEmpty
            ? "Deletes your account and this household’s plans, pantry, grocery list and your own recipes. This can’t be undone."
            : "Deletes your account. The household stays for the other members.")
            .font(Theme.subtitle)
            .foregroundStyle(Theme.muted)
        }
        .themeRows()
      } else {
        Section {
          Text(
            "You're using \(Copy.appName) as a guest. Create an account to keep your plan and share it with your household."
          )
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .themeBareRow()
          Button("Sign in or create account") { signingIn = true }
            .font(Theme.mealName)
            .themeRows()
        }
      }
    }
    .themeList()
    .tint(Theme.accent)
    .navigationTitle("Account & security")
    .navigationBarTitleDisplayMode(.inline)
    .task { await loadMembers() }
    .sheet(isPresented: $signingIn, onDismiss: { Task { await loadMembers() } }) {
      AuthView(isSheet: true)
        .environmentObject(session)
    }
    .sheet(isPresented: $deletingAccount) {
      DeleteAccountSheet(alone: otherMembers.isEmpty) {
        deletingAccount = false
        Task { await session.accountDeleted() }
      }
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
      let household = try await KitchenAPI.json("household")
      householdName = household["name"] as? String ?? ""
      members = try await KitchenAPI.members()
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func resetPassword() async {
    guard let email = session.status?.email else { return }
    busy = true
    defer { busy = false }
    do {
      try await AuthAPI.forgotPassword(email: email)
      message = "Check your email for a password reset link."
      error = nil
    } catch { self.error = KitchenAPI.message(error) }
  }

  private func saveHouseholdName() async {
    let name = householdName.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !name.isEmpty else { return }
    busy = true
    defer { busy = false }
    do {
      _ = try await KitchenAPI.json("household", method: "PUT", body: ["name": name])
      householdName = name
      message = "Household name saved."
      error = nil
    } catch { self.error = KitchenAPI.message(error) }
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
      try await AuthAPI.logoutEverywhere()
    } catch {
      self.error = KitchenAPI.message(error)
    }
    await session.signOut()
  }
}

/// Password check before deleting the account (#65, App Store guideline 5.1.1(v)).
private struct DeleteAccountSheet: View {
  let alone: Bool
  let onDeleted: () -> Void
  @Environment(\.dismiss) private var dismiss
  @State private var password = ""
  @State private var busy = false
  @State private var error: String?

  var body: some View {
    NavigationStack {
      List {
        if let error { ErrorBanner(message: error).themeBareRow() }
        Section {
          Text(alone
            ? "This deletes your account and everything in this household: plans, pantry, grocery list, ratings and recipes you added. It can’t be undone."
            : "This deletes your account and your sign-ins. The household and its plans stay for the other members.")
            .font(Theme.body).foregroundStyle(Theme.ink)
            .fixedSize(horizontal: false, vertical: true)
          SecureField("Your password", text: $password)
            .textContentType(.password)
            .onSubmit { Task { await delete() } }
        }
        .themeRows()
        Section {
          Button("Delete account", role: .destructive) { Task { await delete() } }
            .disabled(busy || password.isEmpty)
        }
        .themeRows()
      }
      .themeList()
      .navigationTitle("Delete account")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
      }
    }
  }

  private func delete() async {
    guard !password.isEmpty, !busy else { return }
    busy = true
    defer { busy = false }
    do {
      try await AuthAPI.deleteAccount(password: password)
      onDeleted()
    } catch {
      self.error = KitchenAPI.message(error)
    }
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
          Guests use a private kitchen identified by a random device/browser cookie. All normal features work without an account. Reinstalling the app or clearing browser data can lose access to guest data. Create an account to protect it.
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
          Delete your account any time from Account & security. Your password is asked for first. If you are the last member, the household goes too: its plans, pantry, grocery list, ratings and the recipes you added. If others are still in the household, it stays for them. You can also remove other people from Account & security.
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
