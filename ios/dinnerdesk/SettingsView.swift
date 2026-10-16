import SwiftUI
import WebKit
import UIKit
import PhotosUI

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
        NavigationLink {
          FeedbackView()
        } label: {
          ThemeIconRow(title: "Report a bug or suggest a feature", systemImage: "exclamationmark.bubble")
        }

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
        StarTip(id: "settings.gold-star")
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
    ("poultry", "Poultry"), ("red-meat", "Red meat"),
  ]
  static let avoids = [
    "fish", "cilantro", "mushrooms", "onions", "bell peppers", "olives", "goat cheese", "nuts",
    "beans", "tofu", "eggplant", "brussels sprouts", "coconut", "spicy",
  ]
  static let who = [("beginner", "Beginner"), ("family", "Family"), ("kids", "Kids"), ("entertaining", "Entertaining")]
  static let cuisines = [("italian", "Italian"), ("mexican", "Mexican"), ("asian", "Asian"), ("american", "American"), ("mediterranean", "Mediterranean")]
  static let proteins = [("chicken", "Chicken"), ("beef", "Beef"), ("pork", "Pork"), ("seafood", "Seafood"), ("turkey", "Turkey")]
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
  @State private var who: Set<String> = []
  @State private var cuisines: Set<String> = []
  @State private var proteinMore: Set<String> = []
  @State private var proteinLess: Set<String> = []
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
        Text("Diet, allergies, and avoids hide meals. Who, cuisine, and protein shape suggestions.")
          .font(Theme.subtitle).foregroundStyle(Theme.muted)
          .fixedSize(horizontal: false, vertical: true)

        filterBlock("Diet") {
          ForEach(Self.diets, id: \.self) { item in
            FilterChip(label: Self.dietLabels[item] ?? item.capitalized, on: diets.contains(item)) { toggleDiet(item) }
          }
        }

        filterBlock("Who it's for") {
          ForEach(Self.who, id: \.0) { item in
            FilterChip(label: item.1, on: who.contains(item.0)) {
              if who.contains(item.0) { who.remove(item.0) } else { who.insert(item.0) }
              save()
            }
          }
        }

        filterBlock("Cuisines to suggest") {
          ForEach(Self.cuisines, id: \.0) { item in
            FilterChip(label: item.1, on: cuisines.contains(item.0)) {
              if cuisines.contains(item.0) { cuisines.remove(item.0) } else { cuisines.insert(item.0) }
              save()
            }
          }
        }

        if diets.contains("omnivore") || diets.contains("pescatarian") {
          let choices = Self.proteins.filter { diets.contains("omnivore") || $0.0 == "seafood" }
          filterBlock("Offer more") {
            ForEach(choices, id: \.0) { item in
              FilterChip(label: item.1, on: proteinMore.contains(item.0)) {
                if proteinMore.contains(item.0) { proteinMore.remove(item.0) } else { proteinMore.insert(item.0); proteinLess.remove(item.0) }
                save()
              }
            }
          }
          filterBlock("Offer less") {
            ForEach(choices, id: \.0) { item in
              FilterChip(label: item.1, on: proteinLess.contains(item.0)) {
                if proteinLess.contains(item.0) { proteinLess.remove(item.0) } else { proteinLess.insert(item.0); proteinMore.remove(item.0) }
                save()
              }
            }
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
      if let w = filters["who"] as? [String] { who = Set(w) }
      if let c = filters["cuisines"] as? [String] { cuisines = Set(c) }
      if let p = filters["protein_more"] as? [String] { proteinMore = Set(p) }
      if let p = filters["protein_less"] as? [String] { proteinLess = Set(p) }
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
      "who": Self.who.map(\.0).filter { who.contains($0) },
      "cuisines": Self.cuisines.map(\.0).filter { cuisines.contains($0) },
      "protein_more": Self.proteins.map(\.0).filter { proteinMore.contains($0) },
      "protein_less": Self.proteins.map(\.0).filter { proteinLess.contains($0) },
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
  @EnvironmentObject private var store: Store
  @EnvironmentObject private var session: Session
  @State private var members: [HouseholdMember] = []
  @State private var householdName = ""
  @State private var inviteURL: URL?
  @State private var signingIn = false
  @State private var confirmEverywhere = false
  @State private var deletingAccount = false
  @State private var joinToken = ""
  @State private var homePassword = ""
  @State private var confirmLeave = false
  @State private var confirmJoin = false
  @State private var deletingHome = false
  @State private var successor: HouseholdMember?
  @State private var busy = false
  @State private var message: String?
  @State private var error: String?

  private var otherMembers: [HouseholdMember] { members.filter { $0.email != session.status?.email } }

  private var myRole: String? { members.first { $0.email == session.status?.email }?.householdRole }
  private var canManage: Bool { myRole == "owner" || myRole == "admin" }
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
          if session.status?.hasEmail == false {
            Text("This account has a username instead of an email, so there's no reset link. If you forget your password, the account can't be recovered.")
              .font(Theme.subtitle).foregroundStyle(Theme.muted)
              .fixedSize(horizontal: false, vertical: true)
          } else {
            Button { Task { await resetPassword() } } label: {
              Label("Reset password", systemImage: "key")
            }
            .disabled(busy)
            Text("Email a reset link to your signed-in address.")
              .font(Theme.subtitle).foregroundStyle(Theme.muted)
          }
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
            StarTip(id: "settings.invite-link")
          } else {
            Button("Invite someone to this household") { Task { await invite() } }
              .disabled(busy)
          }
          ForEach(otherMembers) { member in
            VStack(alignment: .leading) {
              Text(member.email).fixedSize(horizontal: false, vertical: true)
              Text(member.householdRole ?? "member").font(Theme.subtitle).foregroundStyle(Theme.muted)
              if myRole == "owner" {
                Button("Transfer ownership") { successor = member }
                Button(member.householdRole == "admin" ? "Remove admin role" : "Make admin") {
                  Task { await householdAction { try await KitchenAPI.setRole(member.id, role: member.householdRole == "admin" ? "member" : "admin") } }
                }
              }
            }
            .deleteDisabled(!canManage || member.householdRole == "owner")
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
          StarTip(id: "settings.sign-out-everywhere")
        }
        .themeRows()

        ThemeSection("Household membership") {
          Text("Leaving creates an empty solo household. Your account stays active. Shared plans and kitchen data stay with the household.").font(Theme.subtitle)
          Button("Leave household") { confirmLeave = true }.disabled(busy)
          TextField("Invite link or token", text: $joinToken).textInputAutocapitalization(.never).autocorrectionDisabled()
          Button("Join household") { confirmJoin = true }.disabled(busy || joinToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
          if canManage {
            Button("Delete household", role: .destructive) { deletingHome.toggle() }
            if deletingHome {
              Text("Permanently removes this kitchen and its plans. Everyone keeps their account and receives an empty solo household. Anonymous meal votes are retained.").font(Theme.subtitle)
              SecureField("Your password", text: $homePassword).textContentType(.password)
              Button("Confirm household deletion", role: .destructive) {
                Task { await householdAction { try await KitchenAPI.deleteHousehold(password: homePassword) } }
              }.disabled(busy || homePassword.isEmpty)
            }
          }
        }.themeRows()
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
    .confirmationDialog("Leave this household and start an empty solo household?", isPresented: $confirmLeave, titleVisibility: .visible) {
      Button("Leave household", role: .destructive) { Task { await householdAction { try await KitchenAPI.leaveHousehold() } } }
    }
    .confirmationDialog("Join this household? Your current solo kitchen will be removed; shared kitchens stay with their members.", isPresented: $confirmJoin, titleVisibility: .visible) {
      Button("Join household") { Task { await householdAction { try await KitchenAPI.joinHousehold(joinToken.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "/").last.map(String.init) ?? "") } } }
    }
    .alert("Transfer household ownership?", isPresented: Binding(get: { successor != nil }, set: { if !$0 { successor = nil } })) {
      Button("Transfer") { if let member = successor { Task { await householdAction { try await KitchenAPI.setRole(member.id, role: "owner") } } }; successor = nil }
      Button("Cancel", role: .cancel) { successor = nil }
    } message: { Text("The selected member becomes the creator. You become an admin.") }
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

  private func householdAction(_ action: () async throws -> Void) async {
    busy = true
    defer { busy = false }
    do {
      try await action()
      joinToken = ""
      homePassword = ""
      deletingHome = false
      ResponseCache.clear()
      await session.refresh()
      await loadMembers()
      await store.switchAccount()
      error = nil
      message = "Household updated."
    }
    catch { self.error = KitchenAPI.message(error) }
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
          Text("Anonymous meal votes are retained without account identifiers.").font(Theme.subtitle)
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

/// Bug reports and feature requests (#145). Ids match app/models.py FEEDBACK_KINDS.
enum FeedbackKind: String, CaseIterable, Identifiable {
  case bug, feature
  var id: String { rawValue }
  var label: String { self == .bug ? "Report a bug" : "Suggest a feature" }
  var help: String {
    self == .bug ? "Something broke or didn't work the way it should." : "Something you wish \(Copy.appName) did."
  }
  var prompt: String { self == .bug ? "What went wrong?" : "What would you like?" }
  var placeholder: String {
    self == .bug
      ? "What happened, and what did you expect? e.g. I checked off milk and it came back after a refresh."
      : "e.g. Let me plan lunches too, not just dinners."
  }
}

/// "Report a bug or suggest a feature". The server keeps it with the app build that sent it.
private struct FeedbackView: View {
  @State private var kind = FeedbackKind.bug
  @State private var note = ""
  @State private var sending = false
  @State private var sent: FeedbackKind?
  @State private var error: String?
  /// Up to 3 screenshots from Photos, shrunk to JPEG before sending.
  @State private var shots: [UIImage] = []
  @State private var picked: [PhotosPickerItem] = []
  private static let maxShots = 3

  private var trimmed: String { note.trimmingCharacters(in: .whitespacesAndNewlines) }

  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 12) {
        if let error { ErrorBanner(message: error) }
        if let sent {
          Text(sent == .bug ? "Thanks. We'll look into it." : "Thanks for the idea. We read every one.")
            .font(Theme.body).foregroundStyle(Theme.ink)
          Button("Send another") { self.sent = nil }
            .font(Theme.action)
            .frame(minHeight: 44)
        } else {
          Text("What's this about?").font(Theme.action).foregroundStyle(Theme.ink)
          ForEach(FeedbackKind.allCases) { option in
            Button { kind = option } label: {
              HStack(alignment: .top, spacing: 10) {
                Image(systemName: kind == option ? "largecircle.fill.circle" : "circle")
                  .foregroundStyle(kind == option ? Theme.accent : Theme.muted)
                VStack(alignment: .leading, spacing: 2) {
                  Text(option.label).font(Theme.body).foregroundStyle(Theme.ink)
                  Text(option.help).font(Theme.subtitle).foregroundStyle(Theme.muted)
                }
                Spacer()
              }
              .frame(minHeight: 44)
              .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityAddTraits(kind == option ? .isSelected : [])
          }
          Text(kind.prompt).font(Theme.action).foregroundStyle(Theme.ink)
          TextField(kind.placeholder, text: $note, axis: .vertical)
            .font(Theme.subtitle)
            .lineLimit(4...10)
            .padding(12)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
            .onChange(of: note) { _, value in if value.count > 2000 { note = String(value.prefix(2000)) } }
          screenshots
          Button {
            Task { await send() }
          } label: {
            Text(sending ? "Sending…" : "Send").font(Theme.action).foregroundStyle(Theme.bg)
              .frame(maxWidth: .infinity, minHeight: 50)
              .background(trimmed.isEmpty ? Theme.muted : Theme.ink, in: RoundedRectangle(cornerRadius: 14))
          }
          .buttonStyle(.plain)
          .disabled(trimmed.isEmpty || sending)
        }
      }
      .padding()
    }
    .background(Theme.bg)
    .navigationTitle("Bugs & ideas")
    .navigationBarTitleDisplayMode(.inline)
  }

  /// Thumbnails with a remove button, then "Add a screenshot" from Photos.
  private var screenshots: some View {
    VStack(alignment: .leading, spacing: 8) {
      if !shots.isEmpty {
        ScrollView(.horizontal, showsIndicators: false) {
          HStack(spacing: 10) {
            ForEach(Array(shots.enumerated()), id: \.offset) { index, image in
              Image(uiImage: image)
                .resizable().scaledToFill()
                .frame(width: 80, height: 110)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line))
                .overlay(alignment: .topTrailing) {
                  Button { shots.remove(at: index) } label: {
                    Image(systemName: "xmark.circle.fill").font(.system(size: 22))
                      .foregroundStyle(Theme.ink, Theme.surface)
                      .frame(width: 44, height: 44)
                  }
                  .buttonStyle(.plain)
                  .offset(x: 14, y: -14)
                  .accessibilityLabel("Remove screenshot \(index + 1)")
                }
                .accessibilityLabel("Screenshot \(index + 1)")
            }
          }
          .padding(.top, 14).padding(.trailing, 14)
        }
      }
      if shots.count < Self.maxShots {
        PhotosPicker(selection: $picked, maxSelectionCount: Self.maxShots - shots.count, matching: .images) {
          Label(shots.isEmpty ? "Add a screenshot (optional)" : "Add another screenshot", systemImage: "photo.badge.plus")
            .font(Theme.action).foregroundStyle(Theme.accent)
            .frame(minHeight: 44)
        }
        .onChange(of: picked) { _, items in
          Task { await load(items) }
        }
      }
    }
  }

  private func load(_ items: [PhotosPickerItem]) async {
    guard !items.isEmpty else { return }
    for item in items where shots.count < Self.maxShots {
      if let data = try? await item.loadTransferable(type: Data.self), let image = UIImage(data: data) {
        shots.append(image)
      }
    }
    picked = []
  }

  /// A JPEG data URL at most 2000px on its long side, well under the server's 5 MB limit.
  private static func dataURL(_ image: UIImage) -> String? {
    let longest = max(image.size.width, image.size.height)
    let scale = min(1, 2000 / max(longest, 1))
    let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
    let format = UIGraphicsImageRendererFormat.default()
    format.scale = 1
    let resized = UIGraphicsImageRenderer(size: size, format: format).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
    guard let jpeg = resized.jpegData(compressionQuality: 0.85) else { return nil }
    return "data:image/jpeg;base64," + jpeg.base64EncodedString()
  }

  private func send() async {
    sending = true
    defer { sending = false }
    do {
      let images = shots.compactMap(Self.dataURL)
      let _: Ok = try await API.send(
        "feedback", method: "POST",
        body: ["kind": kind.rawValue, "note": trimmed, "screen": "settings", "screenshots": images])
      error = nil
      note = ""
      shots = []
      sent = kind
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}

private struct PrivacyView: View {
  @State private var exportFile: URL?
  @State private var exporting = false
  @State private var exportError: String?

  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 12) {
        yourData
        Text(
          "Dinnerdesk is a meal planner for a household. This is what we store, and what we do with it."
        )
        section(
          "Account",
          """
          If you create an account we store your email (or the username you chose instead), a hash of your password (not the password), and your household name. A sign-in session lasts 30 days. You can sign out of this device, or every device, from Account & security.

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
          Download a copy of your data at the top of this page. Delete your account from Account & security after confirming your password. Your sign-ins and reset links are removed. If other members remain, a household creator must transfer ownership before deleting their account. The last member’s deletion also removes their solo kitchen. The household creator or a designated household admin can separately delete a household: its kitchen and plans are removed, but members keep their accounts and receive empty solo households. Leaving or being removed from a household also preserves your account. Meal votes may be retained without account, household, browser, or session identifiers, grouped as individual history or household history.
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

  /// "Download my data" (#64): everything stored for this household as one JSON file.
  private var yourData: some View {
    VStack(alignment: .leading, spacing: 8) {
      Text("Your data").font(Theme.title)
      Text("Get a copy of everything we store for your household: plans, grocery lists, pantry, filters, ratings, prep votes, Taste Lab answers and the recipes you added. Passwords and sign-in tokens are never included.")
        .foregroundStyle(Theme.muted)
      if let exportFile {
        ShareLink(item: exportFile) {
          Label("Save or share your data", systemImage: "square.and.arrow.up")
            .font(Theme.action).foregroundStyle(Theme.accent).frame(minHeight: 44)
        }
      } else {
        Button {
          Task { await download() }
        } label: {
          HStack(spacing: 8) {
            if exporting { ProgressView().controlSize(.small) }
            Text(exporting ? "Preparing…" : "Download my data")
          }
          .font(Theme.action).foregroundStyle(Theme.accent).frame(minHeight: 44)
        }
        .disabled(exporting)
      }
      if let exportError { Text(exportError).font(Theme.subtitle).foregroundStyle(Theme.accent) }
    }
    .padding(.bottom, 8)
  }

  private func download() async {
    exporting = true
    exportError = nil
    defer { exporting = false }
    do {
      let data = try await API.getData("household/export")
      let day = Date().formatted(.iso8601.year().month().day())
      let file = FileManager.default.temporaryDirectory.appendingPathComponent("dinnerdesk-data-\(day).json")
      try data.write(to: file, options: .atomic)
      exportFile = file
    } catch {
      exportError = "Couldn’t prepare your data. Please try again."
    }
  }

  private func section(_ title: String, _ body: String) -> some View {
    VStack(alignment: .leading, spacing: 6) {
      Text(title).font(Theme.title)
      Text(body).foregroundStyle(Theme.muted)
    }
    .padding(.top, 8)
  }
}
