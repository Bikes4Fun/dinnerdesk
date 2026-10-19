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
  /// Set by the Quick start tour: the main button says this and calls onDone instead of
  /// going back, and the tour's own Back and Skip take the toolbar.
  var doneTitle: String? = nil
  var onDone: (() async -> Void)? = nil
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
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
  static let who = [("beginner", "Beginner"), ("family", "Family"), ("kids", "Kid-friendly"), ("entertaining", "Entertaining")]
  static let cuisines = [
    ("italian", "Italian"), ("mexican", "Mexican"), ("american", "American"), ("chinese", "Chinese"),
    ("thai", "Thai"), ("indian", "Indian"), ("japanese", "Japanese"), ("mediterranean", "Mediterranean"),
    ("korean", "Korean"), ("vietnamese", "Vietnamese"), ("greek", "Greek"), ("middle-eastern", "Middle Eastern"),
    ("french", "French"), ("spanish", "Spanish"), ("southern", "Southern"), ("cajun", "Cajun & Creole"),
    ("caribbean", "Caribbean"), ("latin-american", "Latin American"),
  ]
  static let proteins = [
    ("chicken", "Chicken"), ("beef", "Beef"), ("pork", "Pork"), ("salmon", "Salmon"), ("shrimp", "Shrimp"),
    ("tofu", "Tofu"), ("turkey", "Turkey"), ("white-fish", "White fish"), ("lamb", "Lamb"), ("sausage", "Sausage"),
    ("tempeh", "Tempeh"), ("beans", "Beans & lentils"), ("eggs", "Eggs"), ("scallops", "Scallops"),
  ]
  /// Proteins each diet can eat; omnivore gets them all.
  static let proteinDiets: [String: Set<String>] = [
    "pescatarian": ["salmon", "shrimp", "white-fish", "scallops", "tofu", "tempeh", "beans", "eggs"],
    "vegetarian": ["tofu", "tempeh", "beans", "eggs"],
    "vegan": ["tofu", "tempeh", "beans"],
  ]
  struct TimeOption: Identifiable {
    let id: String
    let label: String
  }

  static let times = [
    TimeOption(id: "any", label: "Any time"),
    TimeOption(id: "20", label: "20 min or less"),
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
  /// "Saving…" then "Saved" after each change (#85), so a tap never looks like it did nothing.
  enum SaveState { case idle, saving, saved }
  @State private var saveState = SaveState.idle
  @State private var saveCount = 0
  @State private var saveTask: Task<Void, Never>?
  @State private var saveFailed = false

  static let dietLabels = [
    "omnivore": "Omnivore", "pescatarian": "Pescatarian", "vegetarian": "Vegetarian", "vegan": "Vegan",
    "gluten-free": "Gluten-free", "dairy-free": "Dairy-free",
  ]

  private var filterCount: Int {
    var n = diets == ["omnivore"] ? 0 : 1
    n += allergens.count + otherAllergens.count + avoids.count + otherAvoids.count
    n += who.count + cuisines.count + proteinMore.count + proteinLess.count
    if time != "any" { n += 1 }
    return n
  }

  /// Sections after Cook time fold to one line that says what's picked. Diet starts open.
  @State private var openSections: Set<String> = ["diet"]
  /// Long sections show their first few choices; "Show more" opens the rest.
  @State private var showAll: Set<String> = []

  var body: some View {
    VStack(spacing: 0) {
      ScrollView {
        VStack(alignment: .leading, spacing: 12) {
          if let error { ErrorBanner(message: error) }
          cookTimeCard
          tierCard("Hides meals", note: "Strict — never shown", strict: true) {
            foldSection("diet", "Diet", summary: dietSummary, isSet: diets != ["omnivore"]) { dietChips }
            foldSection("allergy", "Allergies", summary: Self.list(allergyLabels, empty: "None"), isSet: !allergyLabels.isEmpty) {
              allergyChips
            }
          }
          tierCard("Shows fewer", note: "Still allowed, just ranked lower") {
            foldSection("avoid", "Not a fan of", summary: Self.list(avoidLabels, empty: "Nothing yet"), isSet: !avoidLabels.isEmpty) {
              avoidChips
            }
          }
          tierCard("Preferences", note: "Tunes what we suggest") {
            foldSection("who", "Who it's for", summary: Self.list(whoLabels, empty: "Anyone"), isSet: !who.isEmpty) {
              KitchenFlow(spacing: 6) {
                ForEach(Self.who, id: \.0) { item in
                  choiceChip(item.1, on: who.contains(item.0)) { toggle(&who, item.0) }
                }
              }
            }
            foldSection("protein", "Proteins", summary: proteinSummary, isSet: !proteinMore.isEmpty || !proteinLess.isEmpty) {
              proteinRows
            }
            foldSection("cuisine", "Cuisines", summary: Self.list(cuisineLabels, empty: "Any"), isSet: !cuisines.isEmpty) {
              cuisineChips
            }
          }
          FilterSuggestionCard()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 16)
        .frame(maxWidth: .infinity, alignment: .leading)
      }
      footer
    }
    .background(Theme.bg)
    .navigationTitle("Filters")
    .navigationBarTitleDisplayMode(.inline)
    // Back waits for the last change to save, so it replaces the system back button.
    .navigationBarBackButtonHidden(onDone == nil)
    .toolbar {
      if onDone == nil {
        ToolbarItem(placement: .topBarLeading) {
          Button {
            Task { await close() }
          } label: {
            Image(systemName: "chevron.left").font(.system(size: 17, weight: .semibold))
          }
          .accessibilityLabel("Save and go back")
        }
        ToolbarItem(placement: .topBarTrailing) {
          Button("Reset") { resetFilters() }
            .font(Theme.action)
            .foregroundStyle(Theme.accent)
        }
      }
    }
    .task { await load() }
  }

  // MARK: Cook time

  /// Always open: it's the filter people change most.
  private var cookTimeCard: some View {
    VStack(alignment: .leading, spacing: 10) {
      HStack(alignment: .firstTextBaseline) {
        Text("Cook time").font(Self.sectionFont).foregroundStyle(Theme.ink)
          .accessibilityAddTraits(.isHeader)
        Spacer()
        Text("Prep to plate").font(Self.noteFont).foregroundStyle(Theme.muted)
      }
      HStack(spacing: 4) {
        ForEach(Self.times) { option in
          let on = time == option.id
          Button {
            time = option.id
            save()
          } label: {
            Text(option.id == "any" ? "Any" : "\(option.id) min")
              .font(Self.chipFont)
              .foregroundStyle(on ? Theme.ink : Theme.muted)
              .frame(maxWidth: .infinity, minHeight: 34)
              .background(on ? Theme.surface : Color.clear, in: RoundedRectangle(cornerRadius: 10))
              .shadow(color: on ? Theme.ink.opacity(0.15) : .clear, radius: 2, y: 1)
          }
          .buttonStyle(.plain)
          .accessibilityLabel(option.label)
          .accessibilityAddTraits(on ? .isSelected : [])
        }
      }
      .padding(3)
      .background(Theme.aubergineTint, in: RoundedRectangle(cornerRadius: 13))
    }
    .padding(.horizontal, 14)
    .padding(.top, 12)
    .padding(.bottom, 14)
    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 20))
    .overlay(RoundedRectangle(cornerRadius: 20).stroke(Theme.line))
  }

  // MARK: Sections

  private var dietChips: some View {
    KitchenFlow(spacing: 6) {
      ForEach(Self.diets, id: \.self) { item in
        choiceChip(Self.dietLabels[item] ?? item.capitalized, on: diets.contains(item)) { toggleDiet(item) }
      }
    }
  }

  private var allergyChips: some View {
    VStack(alignment: .leading, spacing: 10) {
      KitchenFlow(spacing: 6) {
        ForEach(Self.allergens, id: \.0) { item in
          choiceChip(item.1, on: allergens.contains(item.0)) { toggle(&allergens, item.0) }
        }
        ForEach(otherAllergens, id: \.self) { name in
          choiceChip("\(name) ✕", on: true) { otherAllergens.removeAll { $0 == name }; save() }
            .accessibilityLabel("Remove \(name)")
        }
        choiceChip("Other", on: otherAllergenOpen) { otherAllergenOpen.toggle() }
      }
      if otherAllergenOpen {
        ItemSearchField(label: "Other allergies", selected: $otherAllergens) {
          let known = Self.allergens.map(\.0)
          allergens.formUnion(otherAllergens.filter { known.contains($0) })
          otherAllergens.removeAll { known.contains($0) }
          save()
        }
      }
    }
  }

  private var avoidChips: some View {
    let shown = Self.firstOrPicked(Self.avoids, count: 6, open: showAll.contains("avoid")) { avoids.contains($0) }
    return VStack(alignment: .leading, spacing: 10) {
      KitchenFlow(spacing: 6) {
        ForEach(shown, id: \.self) { item in
          choiceChip(item.capitalized, on: avoids.contains(item)) { toggle(&avoids, item) }
        }
        ForEach(otherAvoids, id: \.self) { name in
          choiceChip("\(name) ✕", on: true) { otherAvoids.removeAll { $0 == name }; save() }
            .accessibilityLabel("Remove \(name)")
        }
      }
      showMoreButton("avoid", hidden: Self.avoids.count - shown.count, noun: "")
      ItemSearchField(label: "Foods to avoid", placeholder: "Add an ingredient…", dashed: true, presets: Self.avoids, taken: avoids, selected: $otherAvoids) {
        avoids.formUnion(otherAvoids.filter { Self.avoids.contains($0) })
        otherAvoids.removeAll { Self.avoids.contains($0) }
        save()
      }
    }
  }

  private var cuisineChips: some View {
    let shown = Self.firstOrPicked(Self.cuisines, count: 8, open: showAll.contains("cuisine")) { cuisines.contains($0.0) }
    return VStack(alignment: .leading, spacing: 8) {
      KitchenFlow(spacing: 6) {
        ForEach(shown, id: \.0) { item in
          choiceChip(item.1, on: cuisines.contains(item.0)) { toggle(&cuisines, item.0) }
        }
      }
      showMoreButton("cuisine", hidden: Self.cuisines.count - shown.count, noun: "cuisines")
    }
  }

  /// The proteins this kitchen's diet allows.
  private var proteinChoices: [(String, String)] {
    let diet = ["vegan", "vegetarian", "pescatarian"].first { diets.contains($0) }
    guard let diet, let allowed = Self.proteinDiets[diet] else { return Self.proteins }
    return Self.proteins.filter { allowed.contains($0.0) }
  }

  private var proteinRows: some View {
    let choices = proteinChoices
    let shown = Self.firstOrPicked(choices, count: 4, open: showAll.contains("protein")) {
      proteinMore.contains($0.0) || proteinLess.contains($0.0)
    }
    return VStack(alignment: .leading, spacing: 8) {
      VStack(spacing: 0) {
        HStack(spacing: 0) {
          Spacer()
          Text("LESS").frame(width: 50)
          Color.clear.frame(width: 36, height: 1)
          Text("MORE").frame(width: 50)
        }
        .font(.custom("DMSans-Bold", size: 11, relativeTo: .caption2))
        .tracking(0.5)
        .foregroundStyle(Theme.muted)
        .padding(.horizontal, 11)
        .padding(.top, 8)
        .padding(.bottom, 2)
        .accessibilityHidden(true)
        ForEach(Array(shown.enumerated()), id: \.element.0) { index, item in
          if index > 0 { Theme.line.frame(height: 1) }
          proteinRow(item.0, item.1)
        }
      }
      .background(Theme.bg, in: RoundedRectangle(cornerRadius: 16))
      .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.line))
      showMoreButton("protein", hidden: choices.count - shown.count, noun: "proteins")
    }
  }

  /// Less · no preference · more. Less ranks those meals lower; it doesn't cap them.
  private func proteinRow(_ id: String, _ name: String) -> some View {
    let value = proteinMore.contains(id) ? "more" : proteinLess.contains(id) ? "less" : ""
    return HStack(spacing: 12) {
      Text(name).font(Self.chipFont).foregroundStyle(Color(hex: 0x2E1A2C))
      Spacer(minLength: 0)
      HStack(spacing: 0) {
        proteinSegment(id, "less", on: value == "less", label: "Less \(name)") {
          Image(systemName: "minus").font(.system(size: 12, weight: .bold))
        }
        proteinSegment(id, "", on: value.isEmpty, label: "No preference for \(name)") {
          Circle().fill(value.isEmpty ? Theme.ink : Color(hex: 0xC9B9C4)).frame(width: 6, height: 6)
        }
        proteinSegment(id, "more", on: value == "more", label: "More \(name)") {
          Image(systemName: "plus").font(.system(size: 12, weight: .bold))
        }
      }
      .padding(3)
      .background(Theme.aubergineTint, in: RoundedRectangle(cornerRadius: 11))
    }
    .padding(.leading, 14)
    .padding(.trailing, 8)
    .padding(.vertical, 5)
    .frame(minHeight: 44)
  }

  private func proteinSegment<Label: View>(
    _ id: String, _ kind: String, on: Bool, label: String, @ViewBuilder content: () -> Label
  ) -> some View {
    let fill: Color = !on ? .clear : kind == "more" ? Theme.ink : kind == "less" ? Color(hex: 0xFDE6DD) : Theme.surface
    let ink: Color = !on ? Theme.muted : kind == "more" ? Theme.surface : kind == "less" ? Color(hex: 0x8A3A22) : Theme.ink
    return Button {
      proteinMore.remove(id)
      proteinLess.remove(id)
      if kind == "more" { proteinMore.insert(id) }
      if kind == "less" { proteinLess.insert(id) }
      save()
    } label: {
      content()
        .foregroundStyle(ink)
        .frame(width: kind.isEmpty ? 36 : 50, height: 30)
        .background(fill, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(on && kind == "less" ? Theme.accent : .clear, lineWidth: 1.5))
        .shadow(color: on && kind.isEmpty ? Theme.ink.opacity(0.15) : .clear, radius: 1.5, y: 1)
    }
    .buttonStyle(.plain)
    .accessibilityLabel(label)
    .accessibilityAddTraits(on ? .isSelected : [])
  }

  // MARK: Summaries

  private var dietSummary: String {
    diets == ["omnivore"] ? "Omnivore · no restriction" : Self.diets.filter { diets.contains($0) }.map { Self.dietLabels[$0] ?? $0 }.joined(separator: ", ")
  }
  private var allergyLabels: [String] { Self.allergens.filter { allergens.contains($0.0) }.map(\.1) + otherAllergens }
  private var avoidLabels: [String] { Self.avoids.filter { avoids.contains($0) }.map(\.capitalized) + otherAvoids }
  private var whoLabels: [String] { Self.who.filter { who.contains($0.0) }.map(\.1) }
  private var cuisineLabels: [String] { Self.cuisines.filter { cuisines.contains($0.0) }.map(\.1) }
  private var proteinSummary: String {
    let more = Self.proteins.filter { proteinMore.contains($0.0) }.map { $0.1.lowercased() }
    let less = Self.proteins.filter { proteinLess.contains($0.0) }.map { $0.1.lowercased() }
    var parts: [String] = []
    if !more.isEmpty { parts.append("More " + more.joined(separator: ", ")) }
    if !less.isEmpty { parts.append("less " + less.joined(separator: ", ")) }
    return parts.isEmpty ? "No preference" : parts.joined(separator: " · ")
  }

  /// "Peanut, Sesame, Soy +2"
  static func list(_ labels: [String], empty: String) -> String {
    guard !labels.isEmpty else { return empty }
    return labels.prefix(3).joined(separator: ", ") + (labels.count > 3 ? " +\(labels.count - 3)" : "")
  }

  /// The first `count` items, plus any picked one past them so a choice never hides.
  static func firstOrPicked<T>(_ items: [T], count: Int, open: Bool, picked: (T) -> Bool) -> [T] {
    open ? items : items.enumerated().filter { $0.offset < count || picked($0.element) }.map(\.element)
  }

  // MARK: Pieces

  private static let noteFont = Font.custom("DMSans-Regular", size: 13, relativeTo: .footnote)
  private static let chipFont = Font.custom("DMSans-SemiBold", size: 14, relativeTo: .subheadline)
  private static let sectionFont = Font.custom("DMSans-SemiBold", size: 15, relativeTo: .subheadline)

  /// A labeled group: how strongly its filters act, then its folding sections.
  private func tierCard<Content: View>(
    _ badge: String, note: String, strict: Bool = false, @ViewBuilder content: () -> Content
  ) -> some View {
    VStack(alignment: .leading, spacing: 0) {
      HStack(spacing: 10) {
        Text(badge)
          .font(.custom("DMSans-Bold", size: 12, relativeTo: .caption))
          .foregroundStyle(strict ? Color(hex: 0x8A3A22) : Theme.ink)
          .padding(.horizontal, 10)
          .frame(height: 24)
          .background(strict ? Color(hex: 0xFDE6DD) : Theme.aubergineTint, in: Capsule())
        Text(note).font(Self.noteFont).foregroundStyle(Theme.muted)
      }
      .padding(.bottom, 6)
      .accessibilityElement(children: .combine)
      content()
    }
    .padding(.horizontal, 14)
    .padding(.top, 14)
    .padding(.bottom, 4)
    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 20))
    .overlay(RoundedRectangle(cornerRadius: 20).stroke(Theme.line))
  }

  /// A section that folds to its title and a one-line summary of what's picked.
  private func foldSection<Content: View>(
    _ key: String, _ title: String, summary: String, isSet: Bool, @ViewBuilder content: () -> Content
  ) -> some View {
    let open = openSections.contains(key)
    return VStack(alignment: .leading, spacing: 0) {
      Theme.line.frame(height: 1)
      Button {
        withAnimation(.easeOut(duration: 0.2)) {
          if open { openSections.remove(key) } else { openSections.insert(key) }
        }
      } label: {
        HStack(spacing: 12) {
          VStack(alignment: .leading, spacing: 2) {
            Text(title).font(Self.sectionFont).foregroundStyle(Theme.ink)
            if !open {
              Text(summary)
                .font(Self.noteFont)
                .foregroundStyle(isSet ? Color(hex: 0x2E1A2C) : Theme.muted)
                .lineLimit(1)
            }
          }
          Spacer(minLength: 0)
          Image(systemName: "chevron.down")
            .font(.system(size: 12, weight: .bold))
            .foregroundStyle(Theme.muted)
            .rotationEffect(.degrees(open ? 180 : 0))
        }
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
        .contentShape(Rectangle())
      }
      .buttonStyle(.plain)
      .accessibilityAddTraits(.isHeader)
      .accessibilityValue(open ? "Expanded" : "Collapsed, \(summary)")
      if open {
        content().padding(.bottom, 12)
      }
    }
  }

  @ViewBuilder
  private func showMoreButton(_ key: String, hidden: Int, noun: String) -> some View {
    let open = showAll.contains(key)
    if open || hidden > 0 {
      Button {
        withAnimation(.easeOut(duration: 0.2)) {
          if open { showAll.remove(key) } else { showAll.insert(key) }
        }
      } label: {
        HStack(spacing: 6) {
          Text(open ? "Show less" : "Show \(hidden) more" + (noun.isEmpty ? "" : " \(noun)"))
          Image(systemName: "chevron.down")
            .font(.system(size: 12, weight: .bold))
            .rotationEffect(.degrees(open ? 180 : 0))
        }
        .font(.custom("DMSans-Bold", size: 14, relativeTo: .subheadline))
        .foregroundStyle(Theme.accent)
        .frame(minHeight: 36)
      }
      .buttonStyle(.plain)
    }
  }

  private func toggle(_ set: inout Set<String>, _ item: String) {
    if set.contains(item) { set.remove(item) } else { set.insert(item) }
    save()
  }

  private var footer: some View {
    HStack(spacing: 12) {
      Button {
        Task { await close() }
      } label: {
        Text(doneTitle ?? (filterCount == 0 ? "Save filters" : filterCount == 1 ? "Save 1 filter" : "Save \(filterCount) filters"))
        .font(.custom("DMSans-SemiBold", size: 16, relativeTo: .body))
        .foregroundStyle(Theme.surface)
        .frame(maxWidth: .infinity, minHeight: 46)
        .background(Theme.ink, in: Capsule())
      }
      .buttonStyle(.plain)
    }
    .padding(.horizontal, 20)
    .padding(.top, 10)
    .padding(.bottom, 8)
    .background(Theme.surface)
    .overlay(alignment: .top) { Theme.line.frame(height: 1) }
  }

  /// Each change saves as it's made; wait for the last one, then leave.
  private func close() async {
    await saveTask?.value
    guard !saveFailed else { return }  // a failed save stays here with its message
    if let onDone { await onDone() } else { dismiss() }
  }

  private func choiceChip(_ label: String, on: Bool, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      Text(label)
        .font(Self.chipFont)
        .foregroundStyle(on ? Theme.surface : Color(hex: 0x2E1A2C))
        .padding(.horizontal, 12)
        .frame(minHeight: 34)
        .background(on ? Theme.ink : Theme.surface, in: Capsule())
        .overlay(Capsule().stroke(on ? Theme.ink : Theme.line, lineWidth: 1))
    }
    .buttonStyle(.plain)
    .accessibilityAddTraits(on ? .isSelected : [])
  }

  private func resetFilters() {
    diets = ["omnivore"]
    allergens = []
    otherAllergens = []
    avoids = []
    otherAvoids = []
    who = []
    cuisines = []
    proteinMore = []
    proteinLess = []
    time = "any"
    otherAllergenOpen = false
    save()
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
        saveFailed = false
        // Recipes follow the filters. Refresh the list in the background: the server re-sorts
        // every recipe for new filters, and leaving this screen shouldn't wait for that.
        Task { await store.searchRecipes("") }
        Task {
          try? await Task.sleep(for: .seconds(2))
          if mine == saveCount, saveState == .saved { saveState = .idle }
        }
      } catch {
        if mine == saveCount { saveState = .idle }
        saveFailed = true
        self.error = KitchenAPI.message(error)
      }
    }
  }
}

/// "Missing a filter?" at the bottom of Filters. Sends a feature request (POST /feedback).
private struct FilterSuggestionCard: View {
  @State private var note = ""
  @State private var sending = false
  @State private var sent = false
  @State private var error: String?
  @FocusState private var focused: Bool

  private var trimmed: String { note.trimmingCharacters(in: .whitespacesAndNewlines) }

  var body: some View {
    VStack(alignment: .leading, spacing: 8) {
      Text("Missing a filter?")
        .font(.custom("DMSans-SemiBold", size: 15, relativeTo: .subheadline))
        .foregroundStyle(Theme.ink)
        .accessibilityAddTraits(.isHeader)
      Text("Tell us what you’d like to filter by, and we’ll look into adding it.")
        .font(.custom("DMSans-Regular", size: 13, relativeTo: .footnote))
        .foregroundStyle(Theme.muted)
        .fixedSize(horizontal: false, vertical: true)
      TextField("e.g. low sodium, no pork, more one-pan meals", text: $note, axis: .vertical)
        .lineLimit(2...5)
        .font(.custom("DMSans-Regular", size: 14, relativeTo: .subheadline))
        .focused($focused)
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(Theme.bg, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
        .onChange(of: note) { _, _ in if !note.isEmpty { sent = false } }
        .accessibilityLabel("Filter suggestion")
      if let error {
        Text(error).font(.custom("DMSans-Regular", size: 13, relativeTo: .footnote)).foregroundStyle(Theme.accent)
      }
      HStack {
        if sent {
          Label("Thanks! We got it.", systemImage: "checkmark.circle.fill")
            .font(.custom("DMSans-SemiBold", size: 13, relativeTo: .footnote))
            .foregroundStyle(Theme.ink)
        }
        Spacer()
        Button {
          Task { await send() }
        } label: {
          Text(sending ? "Sending…" : "Send suggestion")
            .font(.custom("DMSans-SemiBold", size: 14, relativeTo: .subheadline))
            .foregroundStyle(Theme.surface)
            .padding(.horizontal, 14)
            .frame(minHeight: 34)
            .background(Theme.ink.opacity(trimmed.isEmpty || sending ? 0.4 : 1), in: Capsule())
        }
        .buttonStyle(.plain)
        .disabled(trimmed.isEmpty || sending)
      }
    }
    .padding(14)
    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 20))
    .overlay(RoundedRectangle(cornerRadius: 20).stroke(Theme.line))
  }

  private func send() async {
    sending = true
    defer { sending = false }
    do {
      let _: Ok = try await API.send(
        "feedback", method: "POST", body: ["kind": "feature", "note": trimmed, "screen": "filters"])
      note = ""
      sent = true
      focused = false
      error = nil
      UIAccessibility.post(notification: .announcement, argument: "Suggestion sent")
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}

/// Shared preference chip: pale tint, filled coral when on. Tour and Filters both use this.
struct FilterChip: View {
  let label: String
  let on: Bool
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      Text(label).font(Theme.chipLabel)
        .foregroundStyle(on ? Color.white : Theme.ink)
        .multilineTextAlignment(.leading)
        .fixedSize(horizontal: false, vertical: true)
        .padding(.horizontal, 13)
        .padding(.vertical, 9)
        .frame(minHeight: 40)
        .background(on ? Theme.accent : Theme.aubergineTint, in: Capsule())
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
