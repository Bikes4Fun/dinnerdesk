import SwiftUI

/// First-run tour (mirrors web/src/Tour.jsx). Welcome → Quick start (how we use AI, how-to, then Filters)
/// or Taste Lab, or Skip.
/// Shown by AuthGate for new households and after a major update (`version`), or whenever
/// `session.showTour` is set.
struct TourView: View {
  enum Step { case welcome, ai, how, prefs, filters }

  /// Raise this (and TOUR_VERSION in web/src/Tour.jsx) with a major update: everyone who saw an
  /// older tour gets it once more. Households that finished the tour before versions existed
  /// count as version 1.
  static let version = 2

  /// The tour version this household last finished or skipped; 0 if never.
  static func seen(_ prefs: [String: Any]) -> Int {
    (prefs["tour_version"] as? Int) ?? (prefs["tour_done"] == nil ? 0 : 1)
  }

  /// Does this household still need to see the current tour?
  static func isDue(_ prefs: [String: Any]) -> Bool { seen(prefs) < version }

  // Every new build (each TestFlight upload) opens the tour once on this device, as What's new.
  private static let buildKey = "dinnerdesk.tourBuild"
  private static var build: String { Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "" }

  /// This device saw the tour (or was checked) on an earlier build.
  static var isNewBuild: Bool {
    guard let last = UserDefaults.standard.string(forKey: buildKey) else { return false }
    return last != build
  }

  /// Remember this build, so the tour waits for the next one.
  static func noteBuild() { UserDefaults.standard.set(build, forKey: buildKey) }

  private struct HowStep: Identifiable {
    let id: Int
    let title: String
    let systemImage: String
    let text: String
  }

  // Text lives in shared/copy.json (tour.how.N.title / tour.how.N), shared with the website tour.
  private static let how = ["book", "calendar", "tray.and.arrow.down", "cart", "shippingbox", "list.bullet.clipboard", "sparkles", "hand.draw"].enumerated().map {
    i, icon in
    HowStep(
      id: i, title: Copy.text("tour.how.\(i + 1).title"), systemImage: icon,
      text: Copy.text("tour.how.\(i + 1)"))
  }

  // tour.ai.N in shared/copy.json, the same points the website tour shows.
  private static let ai = ["photo", "c.circle", "desktopcomputer", "camera"].enumerated().map {
    i, icon in
    HowStep(
      id: i, title: Copy.text("tour.ai.\(i + 1).title"), systemImage: icon,
      text: Copy.text("tour.ai.\(i + 1)"))
  }

  @EnvironmentObject private var session: Session
  @Environment(\.dynamicTypeSize) private var typeSize
  @State private var step: Step = .welcome
  @State private var howIndex = 0
  @State private var showTasteLab = false
  @State private var saving = false
  /// They saw an older tour, so this is the one after a major update: welcome says What's new.
  @State private var isUpdate = false
  @State private var error: String?

  init() {}

  var body: some View {
    NavigationStack {
      VStack(spacing: 0) {
        if let error {
          ErrorBanner(message: error).padding(.horizontal, 16)
        }
        switch step {
        case .welcome: welcome
        case .ai: aiUse
        case .how: howTo
        case .prefs: prefsIntro
        case .filters: filters
        }
      }
      .frame(maxWidth: .infinity, maxHeight: .infinity)
      .background(Theme.bg)
      .toolbar {
        if step != .welcome {
          ToolbarItem(placement: .topBarLeading) {
            Button("Back") { goBack() }
          }
          ToolbarItem(placement: .topBarTrailing) {
            Button("Skip") { Task { await finish() } }
              .foregroundStyle(Theme.muted)
          }
        }
      }
      .navigationBarTitleDisplayMode(.inline)
      .navigationDestination(isPresented: $showTasteLab) {
        TasteLabView()
          .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
              Button("Done") { session.showTour = false }
                .font(Theme.action)
            }
          }
      }
    }
    .tint(Theme.accent)
    .interactiveDismissDisabled()
    .task { await loadFilters() }
  }

  // MARK: Welcome

  private var welcome: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 16) {
        VStack(alignment: .leading, spacing: 6) {
          Text(isUpdate ? Copy.text("tour.update.title") : "Welcome to \(Copy.appName)")
            .font(Theme.bigTitle)
            .foregroundStyle(Theme.ink)
          Text(isUpdate ? Copy.text("tour.update") : Copy.text("app.tagline"))
            .foregroundStyle(Theme.muted)
        }
        .padding(.bottom, 8)

        ChoiceCard(
          title: "Quick start",
          detail: "A 1-minute how-to, then tell us what you eat.",
          systemImage: "bolt"
        ) { step = .ai }

        ChoiceCard(
          title: "Taste Lab",
          detail: "Swipe through dishes so \(Copy.appName) learns what you like.",
          systemImage: "hand.draw"
        ) {
          Task {
            await markDone(filters: nil)
            showTasteLab = true
          }
        }

        Button("Skip for now") { Task { await finish() } }
          .foregroundStyle(Theme.muted)
          .frame(maxWidth: .infinity)
          .padding(.top, 8)
      }
      .padding(20)
    }
  }

  // MARK: Filters

  /// The same Filters screen as Settings; it saves each change itself.
  private var filters: some View {
    FiltersView(doneTitle: "Start planning") {
      await finish()
    }
  }

  // MARK: Before filters

  private var prefsIntro: some View {
    VStack(spacing: 0) {
      ScrollView {
        VStack(alignment: .leading, spacing: 6) {
          Text(Copy.text("tour.prefs.title"))
            .font(Theme.tourTitle)
            .foregroundStyle(Theme.ink)
          Text(Copy.text("tour.prefs"))
            .font(Theme.body)
            .foregroundStyle(Theme.ink)
            .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(20)
      }
      primaryButton("Next") { step = .filters }
    }
  }

  // MARK: How we use AI

  private var aiUse: some View {
    VStack(spacing: 0) {
      ScrollView {
        VStack(alignment: .leading, spacing: 18) {
          Text(Copy.text("tour.ai.title"))
            .font(Theme.tourTitle)
            .foregroundStyle(Theme.ink)
          ForEach(Self.ai) { item in
            HStack(alignment: .top, spacing: 14) {
              Image(systemName: item.systemImage)
                .font(Theme.title)
                .foregroundStyle(Theme.accent)
                .frame(width: 28)
                .accessibilityHidden(true)
              VStack(alignment: .leading, spacing: 4) {
                Text(item.title)
                  .font(Theme.mealName)
                  .foregroundStyle(Theme.ink)
                Text(item.text)
                  .font(Theme.body)
                  .foregroundStyle(Theme.ink)
                  .fixedSize(horizontal: false, vertical: true)
              }
            }
            .accessibilityElement(children: .combine)
          }
          // The full explanation lives on the website's Help & support page.
          if let more = URL(string: "support#ai", relativeTo: API.origin)?.absoluteURL {
            Link(destination: more) {
              Label(Copy.text("tour.ai.more"), systemImage: "arrow.up.right.square")
                .font(Theme.action)
            }
            .accessibilityHint("Opens the support page in Safari")
          }
        }
        .padding(20)
      }
      primaryButton("Next") { step = .how }
    }
  }

  // MARK: How-to

  private var howTo: some View {
    VStack(spacing: 0) {
      TabView(selection: $howIndex) {
        ForEach(Self.how) { item in
          VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
              Image(systemName: item.systemImage)
                .scaledIcon(size: 24, weight: .semibold)
                .foregroundStyle(Theme.accent)
                .accessibilityHidden(true)
              Text(item.title)
                .font(Theme.tourTitle)
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            }
            // Smaller than body text so the picture of the screen gets the room.
            Text(item.text)
              .font(Self.howText)
              .foregroundStyle(Theme.ink)
              .fixedSize(horizontal: false, vertical: true)
            // A picture of the screen fills the space under the text: real screenshots where we
            // have them (Self.shots), drawn pictures for the rest. At large text the words need the room,
            // so it's left out.
            if !typeSize.isAccessibilitySize {
              if let shot = Self.shots[item.id] {
                if item.id == 0 { newPlanHint }
                Image(shot)
                  .resizable()
                  .scaledToFit()
                  .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                  .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Theme.line))
                  .frame(maxWidth: .infinity, minHeight: 200, maxHeight: .infinity)
                  .layoutPriority(1)
                  .accessibilityHidden(true)
              } else if let drawing = Self.drawings[item.id] {
                TourScreenPicture(index: drawing)
                  .frame(minHeight: 160, maxHeight: 280)
                  .accessibilityHidden(true)
                  .padding(.top, 4)
              } else if item.id == Self.tipsCard {
                // A real tip, so the card shows exactly what one looks like.
                StarTip(id: "recipes.ai-photo").padding(.top, 4)
              }
            }
            Spacer(minLength: 0)
          }
          .padding(24)
          .frame(maxWidth: .infinity, alignment: .leading)
          .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous).fill(Theme.surface)
          )
          .shadow(color: Theme.ink.opacity(0.06), radius: 10, y: 3)
          .padding(.horizontal, 20)
          .padding(.vertical, 12)
          .tag(item.id)
        }
      }
      .tabViewStyle(.page(indexDisplayMode: .never))

      HStack(spacing: 6) {
        ForEach(Self.how) { item in
          Capsule()
            .fill(item.id == howIndex ? Theme.accent : Theme.line)
            .frame(width: item.id == howIndex ? 18 : 6, height: 6)
        }
      }
      .animation(.easeOut(duration: 0.2), value: howIndex)
      .padding(.bottom, 4)

      if howIndex < Self.how.count - 1 {
        primaryButton("Next") { withAnimation { howIndex += 1 } }
      } else {
        primaryButton("Next") { step = .prefs }
      }
    }
  }

  /// Real screenshots for how-to cards, by card index; the others use TourScreenPicture.
  private static let shots = [0: "TourSuggestions", 1: "TourSchedule", 2: "TourDraft", 3: "TourStores"]
  /// The drawn picture for each remaining card (TourScreenPicture: 2 checked-off list, 3 prep).
  private static let drawings = [4: 2, 5: 3]
  /// The tips & Apple Watch card shows a real tip instead of a picture.
  private static let tipsCard = 6

  private static let howText = Font.custom("DMSans-Regular", size: 14, relativeTo: .subheadline)

  /// Where suggestions come from: Plan's New meal plan button, drawn like the real one and ringed.
  private var newPlanHint: some View {
    HStack(spacing: 8) {
      Text("On Plan, tap")
        .font(Self.howText)
        .foregroundStyle(Theme.ink)
      Label("New meal plan", systemImage: "sparkles")
        .font(Theme.chipLabel)
        .foregroundStyle(.white)
        .padding(.horizontal, 14)
        .frame(minHeight: 34)
        .background(Capsule().fill(Theme.accent))
        .padding(4)
        .overlay(Capsule().stroke(Theme.accent.opacity(0.45), lineWidth: 3))
    }
    .accessibilityElement(children: .combine)
  }

  private func primaryButton(_ title: String, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      Text(title)
        .font(Theme.action)
        .frame(maxWidth: .infinity)
        .frame(minHeight: 50)
    }
    .buttonStyle(.borderedProminent)
    .buttonBorderShape(.capsule)
    .tint(Theme.accent)
    .padding(.horizontal, 20)
    .padding(.vertical, 12)
  }

  // MARK: Actions

  private func goBack() {
    switch step {
    case .welcome: break
    case .ai: step = .welcome
    case .how:
      if howIndex > 0 { withAnimation { howIndex -= 1 } } else { step = .ai }
    case .prefs: step = .how
    case .filters: step = .prefs
    }
  }

  private func loadFilters() async {
    do {
      let prefs = try await KitchenAPI.prefs()
      let seen = Self.seen(prefs)
      isUpdate = (seen > 0 && seen < Self.version) || Self.isNewBuild
    } catch { self.error = KitchenAPI.message(error) }
  }

  @discardableResult
  private func markDone(filters: [String: Any]?) async -> Bool {
    Self.noteBuild()
    var patch: [String: Any] = ["tour_done": true, "tour_version": Self.version]
    if let filters { patch["filters"] = filters }
    do {
      try await KitchenAPI.savePrefs(patch)
      error = nil
      return true
    } catch {
      self.error = KitchenAPI.message(error)
      return false
    }
  }

  private func finish() async {
    saving = true
    defer { saving = false }
    await markDone(filters: nil)
    session.showTour = false
  }
}

private struct ChoiceCard: View {
  let title: String
  let detail: String
  let systemImage: String
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      HStack(alignment: .top, spacing: 14) {
        Image(systemName: systemImage)
          .font(Theme.title)
          .foregroundStyle(Theme.accent)
          .frame(width: 28)
        VStack(alignment: .leading, spacing: 4) {
          Text(title)
            .font(Theme.mealName)
            .foregroundStyle(Theme.ink)
          Text(detail)
            .font(Theme.subtitle)
            .foregroundStyle(Theme.muted)
            .multilineTextAlignment(.leading)
            .fixedSize(horizontal: false, vertical: true)
        }
        Spacer(minLength: 0)
        Image(systemName: "chevron.right")
          .font(Theme.chipLabel)
          .foregroundStyle(Theme.muted)
      }
      .padding(18)
      .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.surface))
      .shadow(color: Theme.ink.opacity(0.06), radius: 10, y: 3)
    }
    .buttonStyle(.plain)
  }
}

/// Rounded chip used by the tour filters and the grocery-store page. `count` shows a grey number after the text.
struct KitchenChip: View {
  let text: String
  let count: Int?
  let selected: Bool
  var dashed = false

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
    .padding(.horizontal, 14)
    .frame(minHeight: 36)
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
