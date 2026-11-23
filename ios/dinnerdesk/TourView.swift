import SwiftUI

extension Notification.Name {
  /// Quick start approved a plan or saved filters; the main app reloads its data.
  static let dinnerdeskTourFinished = Notification.Name("dinnerdeskTourFinished")
}

/// Quick start (mirrors web/src/Tour.jsx and TourView.kt): five full screens, one job each, each
/// fitting one phone screen without scrolling at default text size.
/// Welcome → Who's eating → Anything to avoid → Here's your week → Your week is ready.
/// Shown by AuthGate for new households or when replayed from Settings (replay skips Welcome).
struct TourView: View {
  enum Step: Int, CaseIterable { case welcome, household, avoid, week, ready }

  /// Keep writing the current tour version for clients that share the household preferences.
  static let version = 2

  /// The tour version this household last finished or skipped; 0 if never.
  static func seen(_ prefs: [String: Any]) -> Int {
    (prefs["tour_version"] as? Int) ?? (prefs["tour_done"] == nil ? 0 : 1)
  }

  /// Only households that have never completed or skipped the tour need onboarding.
  static func isDue(_ prefs: [String: Any]) -> Bool { seen(prefs) == 0 }

  /// Settings shows the first six Dislikes as chips; the tour shows the same six.
  private static let commonAvoids = Array(FilterOptions.avoids.prefix(6))
  private static let maxDinners = 7
  private static let small = Font.custom("DMSans-Regular", size: 15, relativeTo: .subheadline)
  /// Fills only, never text (DinnerDesk palette).
  private static let coral = Color(hex: 0xFA7E5A)

  @EnvironmentObject private var session: Session
  @State private var step: Step = .welcome
  @State private var busy = false
  @State private var error: String?
  @State private var showTasteLab = false
  /// The household's saved filters, so saving keeps the ones the tour doesn't show.
  @State private var savedFilters: [String: Any] = [:]
  @State private var people = 2
  @State private var time = "any"
  @State private var diets: Set<String> = ["omnivore"]
  @State private var allergens: Set<String> = []
  @State private var avoids: Set<String> = []
  @State private var dinners = 3
  @State private var proposal: Plan?
  @State private var plan: Plan?
  @State private var toBuy: Int?

  var body: some View {
    NavigationStack {
      VStack(spacing: 0) {
        if step != .welcome { topBar }
        switch step {
        case .welcome: welcome
        case .household: household
        case .avoid: avoid
        case .week: week
        case .ready: ready
        }
      }
      .padding(.horizontal, 20)
      .padding(.bottom, 12)
      .frame(maxWidth: .infinity, maxHeight: .infinity)
      .background(Theme.bg)
      .toolbar(.hidden, for: .navigationBar)
      .navigationDestination(isPresented: $showTasteLab) {
        TasteLabView(swipe: true)
          .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
              Button("Done") { session.showTour = false }.font(Theme.action)
            }
          }
      }
    }
    .tint(Theme.accent)
    .interactiveDismissDisabled()
    .task { await load() }
  }

  // MARK: Shared pieces

  private var topBar: some View {
    HStack(spacing: 8) {
      if let back = backStep {
        Button { error = nil; step = back } label: {
          Image(systemName: "chevron.left").font(Theme.title).frame(width: 44, height: 44)
        }
        .accessibilityLabel("Back")
        .disabled(busy)
      } else {
        Color.clear.frame(width: 44, height: 44)
      }
      HStack(spacing: 4) {
        ForEach(Step.allCases, id: \.self) { s in
          Capsule().fill(s.rawValue <= step.rawValue ? Theme.ink : Theme.line).frame(height: 4)
        }
      }
      .accessibilityElement()
      .accessibilityLabel("Step \(step.rawValue + 1) of \(Step.allCases.count)")
      if step != .ready {
        Button("Skip") { Task { await finish() } }
          .font(Theme.chipLabel)
          .frame(minWidth: 44, minHeight: 44)
          .disabled(busy)
      } else {
        Color.clear.frame(width: 44, height: 44)
      }
    }
  }

  private var backStep: Step? {
    switch step {
    case .avoid: return .household
    case .week: return .avoid
    default: return nil
    }
  }

  /// Fits without scrolling when it can; scrolls only if large text needs the room.
  private func page<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
    let inner = VStack(alignment: .leading, spacing: 0) { content() }
      .frame(maxWidth: .infinity, alignment: .leading)
    return ViewThatFits(in: .vertical) {
      inner.frame(maxHeight: .infinity, alignment: .top)
      ScrollView { inner }
    }
  }

  private func heading(_ title: String, _ sub: String? = nil) -> some View {
    VStack(alignment: .leading, spacing: 6) {
      Text(title).font(Theme.tourTitle).foregroundStyle(Theme.ink)
      if let sub { Text(sub).font(Self.small).foregroundStyle(Theme.muted) }
    }
    .padding(.top, 8)
    .padding(.bottom, 16)
  }

  private func primary(_ title: String, disabled: Bool = false, action: @escaping () -> Void) -> some View {
    VStack(spacing: 8) {
      if let error { Text(error).font(Theme.subtitle).foregroundStyle(Theme.danger) }
      Button(action: action) {
        Text(title).font(Theme.action).frame(maxWidth: .infinity).frame(minHeight: 50)
      }
      .buttonStyle(.borderedProminent)
      .buttonBorderShape(.capsule)
      .tint(Theme.ink)
      .disabled(busy || disabled)
    }
    .padding(.top, 8)
  }

  private func stepper(_ value: Int, min: Int, max: Int, label: String, big: Bool, set: @escaping (Int) -> Void) -> some View {
    HStack(spacing: big ? 18 : 10) {
      roundButton("minus", label: "Fewer \(label)", size: big ? 48 : 44) { set(value - 1) }.disabled(busy || value <= min)
      Text("\(value)")
        .font(.custom("DMSans-Bold", size: big ? 40 : 22, relativeTo: big ? .largeTitle : .title3))
        .foregroundStyle(Theme.ink)
        .monospacedDigit()
        .frame(minWidth: big ? 36 : 26)
      roundButton("plus", label: "More \(label)", size: big ? 48 : 44) { set(value + 1) }.disabled(busy || value >= max)
    }
  }

  private func roundButton(_ icon: String, label: String, size: CGFloat, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      Image(systemName: icon).font(Theme.chipLabel).foregroundStyle(Theme.ink)
        .frame(width: size, height: size)
        .background(Circle().fill(Theme.bg))
        .overlay(Circle().stroke(Theme.line))
    }
    .accessibilityLabel(label)
  }

  private func chips(_ items: [(String, String)], selected: Set<String>, toggle: @escaping (String) -> Void) -> some View {
    KitchenFlow(spacing: 6) {
      ForEach(items, id: \.0) { id, text in
        Button { toggle(id) } label: { KitchenChip(text: text, count: nil, selected: selected.contains(id), compact: true) }
          .buttonStyle(.plain)
          .accessibilityAddTraits(selected.contains(id) ? .isSelected : [])
      }
    }
  }

  private func group(_ title: String, _ note: String) -> some View {
    VStack(alignment: .leading, spacing: 1) {
      Text(title).font(Theme.chipLabel).foregroundStyle(Theme.ink)
      Text(note).font(Theme.subtitle).foregroundStyle(Theme.muted)
    }
    .padding(.top, 12)
    .padding(.bottom, 8)
  }

  // MARK: 1 Welcome

  private var welcome: some View {
    VStack(spacing: 0) {
      Spacer(minLength: 0)
      Text("Free. No ads, ever.")
        .font(Theme.chipLabel).foregroundStyle(Theme.ink)
        .padding(.horizontal, 14).padding(.vertical, 6)
        .background(Capsule().fill(Theme.aubergineTint))
        .padding(.bottom, 16)
      Text("Custom meal plans in 5 minutes.")
        .font(Theme.bigTitle).foregroundStyle(Theme.ink)
        .multilineTextAlignment(.center)
        .padding(.bottom, 28)
      VStack(alignment: .leading, spacing: 16) {
        benefit("checklist", "Grocery list built for you")
        benefit("timer", "Prep-ahead steps for busy nights")
        benefit("leaf", "Less waste, using your pantry")
      }
      Spacer(minLength: 0)
      primary("Get started") { step = .household }
      Button("Skip, I’ll look around") { Task { await finish() } }
        .font(Theme.chipLabel).frame(minHeight: 44)
      if let more = URL(string: "support#ai", relativeTo: API.origin)?.absoluteURL {
        Link("How we use AI", destination: more).font(Theme.chipLabel).frame(minHeight: 40)
      }
    }
  }

  private func benefit(_ icon: String, _ text: String) -> some View {
    HStack(spacing: 14) {
      Image(systemName: icon).font(Theme.chipLabel).foregroundStyle(Theme.ink)
        .frame(width: 40, height: 40).background(Circle().fill(Theme.aubergineTint))
        .accessibilityHidden(true)
      Text(text).font(Theme.body).foregroundStyle(Theme.ink)
    }
  }

  // MARK: 2 Who's eating

  private var household: some View {
    VStack(spacing: 0) {
      page {
        heading("Who’s eating dinner?", "We’ll size recipes and the grocery list to match.")
        VStack(spacing: 10) {
          stepper(people, min: 1, max: 12, label: "people", big: true) { people = $0 }
          Text("people, most nights").font(Theme.body).foregroundStyle(Theme.ink)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 22)
        .background(RoundedRectangle(cornerRadius: 18).fill(Theme.surface))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.line))
        Text("Weeknight cook time").font(Theme.chipLabel).foregroundStyle(Theme.ink).padding(.top, 22).padding(.bottom, 8)
        Picker("Weeknight cook time", selection: $time) {
          ForEach(FilterOptions.times) { t in
            Text(t.label.replacingOccurrences(of: " or less", with: "").replacingOccurrences(of: "Any time", with: "Any")).tag(t.id)
          }
        }
        .pickerStyle(.segmented)
        Text("Feeding a crowd one night? Change servings on any single meal later.")
          .font(Self.small).foregroundStyle(Theme.ink)
          .padding(14).frame(maxWidth: .infinity, alignment: .leading)
          .background(RoundedRectangle(cornerRadius: 14).fill(Theme.aubergineTint))
          .padding(.top, 18)
      }
      primary(busy ? "Saving…" : "Next") { Task { await saveHousehold() } }
    }
  }

  // MARK: 3 Anything to avoid

  private var avoid: some View {
    VStack(spacing: 0) {
      page {
        heading("Anything to avoid?")
        group("Diet", "Only show recipes that fit.")
        chips(FilterOptions.diets.map { ($0, FilterOptions.dietLabels[$0] ?? $0) }, selected: diets) { toggleDiet($0) }
        group("Allergies", "Never shown. We check every ingredient.")
        chips(FilterOptions.allergens, selected: allergens) { allergens.formSymmetricDifference([$0]) }
        group("Dislikes", "Suggested less often. You can still add them yourself.")
        chips(Self.commonAvoids.map { ($0, $0.capitalized) }, selected: avoids) { avoids.formSymmetricDifference([$0]) }
      }
      primary(busy ? "Planning your week…" : "Next") { Task { await saveFilters() } }
    }
  }

  private func toggleDiet(_ d: String) {
    if FilterOptions.exclusiveDiets.contains(d) {
      diets = diets.subtracting(FilterOptions.exclusiveDiets).union([d])
    } else {
      diets.formSymmetricDifference([d])
    }
  }

  // MARK: 4 Here's your week

  private var week: some View {
    VStack(spacing: 0) {
      page {
        heading("Here’s your week", "Picked for you. Swap anything that doesn’t sound good.")
        HStack {
          Text("Dinners this week").font(Theme.action).foregroundStyle(Theme.ink)
          Spacer()
          stepper(dinners, min: 1, max: Self.maxDinners, label: "dinners", big: false) { n in Task { await resize(n) } }
        }
        .padding(.leading, 16).padding(6)
        .background(RoundedRectangle(cornerRadius: 18).fill(Theme.surface))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.line))
        .padding(.bottom, 12)
        VStack(spacing: 8) {
          ForEach(proposal?.slots ?? []) { slot in mealRow(slot) }
        }
      }
      primary("Looks good", disabled: (proposal?.slots ?? []).isEmpty) { Task { await approve() } }
    }
  }

  private func mealRow(_ slot: PlanSlot) -> some View {
    HStack(spacing: 12) {
      RecipePhoto(path: slot.photoPath).frame(width: 56, height: 56).clipShape(RoundedRectangle(cornerRadius: 10))
      VStack(alignment: .leading, spacing: 2) {
        Text(slot.recipeName).font(Theme.recipeCardName).foregroundStyle(Theme.ink).lineLimit(3)
        if let m = slot.cookingMinutes { Text("\(m) min").font(Theme.subtitle).foregroundStyle(Theme.muted) }
      }
      Spacer(minLength: 0)
      if proposal?.suggestedRecipeIds?.contains(slot.recipeId) == true {
        Button { Task { await swap(slot) } } label: {
          Label("Swap", systemImage: "arrow.left.arrow.right").font(Theme.chipLabel)
            .padding(.horizontal, 12).frame(minHeight: 44)
            .background(Capsule().fill(Theme.bg)).overlay(Capsule().stroke(Theme.line))
        }
        .accessibilityLabel("Swap \(slot.recipeName)")
        .disabled(busy)
      }
    }
    .padding(8)
    .background(RoundedRectangle(cornerRadius: 16).fill(Theme.surface))
    .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.line))
  }

  // MARK: 5 Your week is ready

  private var ready: some View {
    let count = (plan ?? proposal)?.slots.count ?? 0
    var sub = "\(count) dinner\(count == 1 ? "" : "s") for \(people)"
    if let toBuy { sub += " · \(toBuy) thing\(toBuy == 1 ? "" : "s") to buy" }
    return VStack(spacing: 0) {
      page {
        heading("Your week is ready", sub)
        VStack(alignment: .leading, spacing: 16) {
          tip(1, "Plan", "Give meals a day when you know it. No rush, they stay on your list.")
          tip(2, "Grocery", "Your list builds itself. Check things off in the store.")
          tip(3, "Prep ahead", "Got time on the weekend? See what you can chop and cook early.")
        }
        VStack(alignment: .leading, spacing: 2) {
          Text("Want better picks next week?").foregroundStyle(Theme.ink)
          Button("Try Taste Lab (about 2 min)") { Task { await markDone(); showTasteLab = true } }
            .frame(minHeight: 44)
        }
        .font(Self.small)
        .padding(14).frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.aubergineTint))
        .padding(.top, 24)
      }
      primary("Done") { Task { await finish() } }
    }
  }

  private func tip(_ n: Int, _ title: String, _ text: String) -> some View {
    HStack(alignment: .top, spacing: 12) {
      Text("\(n)").font(Theme.count).foregroundStyle(Theme.ink)
        .frame(width: 26, height: 26).background(Circle().fill(Self.coral))
        .accessibilityHidden(true)
      VStack(alignment: .leading, spacing: 2) {
        Text(title).font(Theme.chipLabel).foregroundStyle(Theme.ink)
        Text(text).font(Self.small).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
      }
    }
    .accessibilityElement(children: .combine)
  }

  // MARK: Actions

  private func load() async {
    guard let prefs = try? await KitchenAPI.prefs() else { return }
    // Replayed from Settings: skip Welcome.
    if Self.seen(prefs) > 0 && step == .welcome { step = .household }
    let f = prefs["filters"] as? [String: Any] ?? [:]
    savedFilters = f
    if let d = f["diets"] as? [String], !d.isEmpty {
      let picked = FilterOptions.strictest.first { d.contains($0) }
      diets = Set(d.filter { !FilterOptions.exclusiveDiets.contains($0) } + (picked.map { [$0] } ?? []))
    }
    if let a = f["allergens"] as? [String] { allergens = Set(a) }
    if let a = f["avoids"] as? [String] { avoids = Set(a) }
    if let t = f["time"] as? String { time = t }
    if let n = prefs["family_portions"] as? Int, n >= 1 { people = min(12, n) }
  }

  private func run(_ work: () async throws -> Void) async {
    busy = true
    error = nil
    defer { busy = false }
    do { try await work() } catch { self.error = KitchenAPI.message(error) }
  }

  private func saveHousehold() async {
    await run {
      var filters = savedFilters
      filters["time"] = time
      try await KitchenAPI.savePrefs(["family_portions": people, "filters": filters])
      savedFilters = filters
      step = .avoid
    }
  }

  /// Saves the filters, then asks for a suggested plan that respects them.
  private func saveFilters() async {
    await run {
      var filters = savedFilters
      filters["diets"] = Array(diets)
      filters["allergens"] = Array(allergens)
      filters["avoids"] = Array(avoids)
      filters["time"] = time
      try await KitchenAPI.savePrefs(["filters": filters])
      savedFilters = filters
      let caps: SuggestionCapabilities = try await API.get("suggestions/capabilities", reportErrors: false)
      guard caps.version >= 2 && caps.review && caps.resize && caps.swap else {
        throw APIError.http(409, "Meal planning needs the updated server. Please try again after the server update.")
      }
      let created: Plan = try await API.send("plans", method: "POST", body: ["title": "This week", "meal_count": dinners, "keep_current": false])
      proposal = created
      dinners = created.slots.count
      step = .week
    }
  }

  private func resize(_ n: Int) async {
    guard let proposal else { return }
    await run {
      dinners = n
      self.proposal = try await API.send("plans/\(proposal.id)/resize", method: "POST", body: ["meal_count": n])
    }
  }

  /// Swap brings in the next-best match; the server records it as a pass for Taste Lab.
  private func swap(_ slot: PlanSlot) async {
    guard let proposal else { return }
    await run { self.proposal = try await API.send("plans/\(proposal.id)/swap/\(slot.id)", method: "POST", body: [:]) }
  }

  private func approve() async {
    guard let proposal else { return }
    await run {
      let approved: Plan = proposal.status == "suggested"
        ? try await API.send("plans/\(proposal.id)/decision/approve", method: "POST", body: [:])
        : proposal
      plan = approved
      step = .ready
      if let g = try? await KitchenAPI.json("plans/\(approved.id)/grocery"), let lines = g["lines"] as? [[String: Any]] {
        toBuy = lines.filter { ($0["checked"] as? Bool) != true && ($0["never_shop"] as? Bool) != true }.count
      }
    }
  }

  private func markDone() async {
    try? await KitchenAPI.savePrefs(["tour_done": true, "tour_version": Self.version])
    NotificationCenter.default.post(name: .dinnerdeskTourFinished, object: nil)
  }

  /// Ends the tour. A suggested plan that wasn't approved stays on Plan for review.
  private func finish() async {
    busy = true
    defer { busy = false }
    do {
      try await KitchenAPI.savePrefs(["tour_done": true, "tour_version": Self.version])
    } catch {
      self.error = KitchenAPI.message(error)
      return
    }
    NotificationCenter.default.post(name: .dinnerdeskTourFinished, object: nil)
    session.showTour = false
  }
}

/// Rounded chip used by the tour filters and the grocery-store page. `count` shows a grey number after the text.
struct KitchenChip: View {
  let text: String
  let count: Int?
  let selected: Bool
  var dashed = false
  /// Shorter chips, so the Quick start filters fit one screen.
  var compact = false

  var body: some View {
    HStack(spacing: 6) {
      Text(text).lineLimit(1)
      if let count {
        Text("\(count)")
          .font(Theme.count)
          .foregroundStyle(selected ? Color.white.opacity(0.8) : Theme.muted)
          .monospacedDigit()
      }
    }
    .font(Theme.chipLabel)
    .foregroundStyle(selected ? Color.white : (dashed ? Theme.accent : Theme.ink))
    .padding(.horizontal, compact ? 12 : 14)
    .frame(minHeight: compact ? 34 : 36)
    .background(Capsule().fill(selected ? Theme.accent : (dashed ? Color.clear : Theme.chip)))
    .overlay(
      Capsule().strokeBorder(
        dashed ? Theme.accent.opacity(0.6) : Color.clear,
        style: StrokeStyle(lineWidth: 1, dash: [4, 3])
      )
    )
    .contentShape(Capsule())
  }
}

/// Lays children left to right and wraps to new rows (chip clouds).
struct KitchenFlow: Layout {
  var spacing: CGFloat = 8

  func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
    let maxWidth = proposal.width ?? .infinity
    var x: CGFloat = 0
    var y: CGFloat = 0
    var rowHeight: CGFloat = 0
    var widest: CGFloat = 0
    for view in subviews {
      let size = view.sizeThatFits(.unspecified)
      if x > 0, x + size.width > maxWidth {
        y += rowHeight + spacing
        x = 0
        rowHeight = 0
      }
      x += size.width + spacing
      rowHeight = max(rowHeight, size.height)
      widest = max(widest, x - spacing)
    }
    return CGSize(width: proposal.width ?? widest, height: y + rowHeight)
  }

  func placeSubviews(
    in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()
  ) {
    var x: CGFloat = 0
    var y: CGFloat = 0
    var rowHeight: CGFloat = 0
    for view in subviews {
      let size = view.sizeThatFits(.unspecified)
      if x > 0, x + size.width > bounds.width {
        y += rowHeight + spacing
        x = 0
        rowHeight = 0
      }
      view.place(
        at: CGPoint(x: bounds.minX + x, y: bounds.minY + y), proposal: ProposedViewSize(size))
      x += size.width + spacing
      rowHeight = max(rowHeight, size.height)
    }
  }
}
