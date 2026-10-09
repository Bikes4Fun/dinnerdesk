import SwiftUI

/// First-run tour (mirrors web/src/Tour.jsx). Welcome → Quick start (filters, then how-to) or Taste Lab, or Skip.
/// Shown by AuthGate when prefs.tour_done is missing, or whenever `session.showTour` is set.
struct TourView: View {
  enum Step { case welcome, filters, how }

  private struct HowStep: Identifiable {
    let id: Int
    let title: String
    let systemImage: String
    let text: String
  }

  // Text lives in shared/copy.json (tour.how.N.title / tour.how.N), shared with the website tour.
  private static let how = ["book", "calendar", "cart", "list.bullet.clipboard"].enumerated().map {
    i, icon in
    HowStep(
      id: i, title: Copy.text("tour.how.\(i + 1).title"), systemImage: icon,
      text: Copy.text("tour.how.\(i + 1)"))
  }

  @EnvironmentObject private var session: Session
  @Environment(\.dynamicTypeSize) private var typeSize
  @State private var step: Step = .welcome
  @State private var diets: Set<String> = ["omnivore"]
  @State private var avoids: Set<String> = []
  @State private var time = "any"
  @State private var howIndex = 0
  @State private var showTasteLab = false
  @State private var saving = false
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
        case .filters: filters
        case .how: howTo
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
            Button("Skip") { Task { await finish(saveFilters: false) } }
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
          Text("Welcome to \(Copy.appName)")
            .font(KitchenStyle.bigTitle)
            .foregroundStyle(Theme.ink)
          Text(Copy.text("app.tagline"))
            .foregroundStyle(Theme.muted)
        }
        .padding(.bottom, 8)

        ChoiceCard(
          title: "Quick start",
          detail: "Tell us what you eat, then a 1-minute how-to.",
          systemImage: "bolt"
        ) { step = .filters }

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

        Button("Skip for now") { Task { await finish(saveFilters: false) } }
          .foregroundStyle(Theme.muted)
          .frame(maxWidth: .infinity)
          .padding(.top, 8)
      }
      .padding(20)
    }
  }

  // MARK: Filters

  private var filters: some View {
    VStack(spacing: 0) {
      ScrollView {
        VStack(alignment: .leading, spacing: 20) {
          VStack(alignment: .leading, spacing: 6) {
            Text("What do you eat?")
              .font(KitchenStyle.title)
              .foregroundStyle(Theme.ink)
            Text("You can change this later in Settings › Filters.")
              .font(Theme.subtitle)
              .foregroundStyle(Theme.muted)
          }

          chipGroup("Diet") {
            ForEach(FiltersView.diets, id: \.self) { item in
              chipButton(item.capitalized, on: diets.contains(item)) {
                diets = FiltersView.toggled(diets, item)
              }
            }
          }
          chipGroup("Avoid") {
            chipButton("None", on: avoids.isEmpty) { avoids = [] }
            ForEach(FiltersView.avoids, id: \.self) { item in
              chipButton(item.capitalized, on: avoids.contains(item)) {
                if avoids.contains(item) { avoids.remove(item) } else { avoids.insert(item) }
              }
            }
          }
          chipGroup("Cook time") {
            ForEach(FiltersView.times) { option in
              chipButton(option.label, on: time == option.id) { time = option.id }
            }
          }
        }
        .padding(20)
      }
      primaryButton("Next") { step = .how }
    }
  }

  private func chipGroup<C: View>(_ title: String, @ViewBuilder content: () -> C) -> some View {
    VStack(alignment: .leading, spacing: 8) {
      KitchenHeader(title)
      KitchenFlow(spacing: 8) { content() }
    }
  }

  private func chipButton(_ text: String, on: Bool, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      KitchenChip(text: text, count: nil, selected: on)
    }
    .buttonStyle(.plain)
    .accessibilityAddTraits(on ? .isSelected : [])
  }

  // MARK: How-to

  private var howTo: some View {
    VStack(spacing: 0) {
      TabView(selection: $howIndex) {
        ForEach(Self.how) { item in
          VStack(alignment: .leading, spacing: 14) {
            Image(systemName: item.systemImage)
              .font(.system(size: 34, weight: .semibold))
              .foregroundStyle(Theme.accent)
            Text(item.title)
              .font(KitchenStyle.title)
              .foregroundStyle(Theme.ink)
            Text(item.text)
              .font(Theme.body)
              .foregroundStyle(Theme.ink)
              .fixedSize(horizontal: false, vertical: true)
            // A drawn picture of the screen fills the space under the text. At large text
            // the words need the room, so it's left out.
            if !typeSize.isAccessibilitySize {
              TourScreenPicture(index: item.id)
                .frame(minHeight: 160, maxHeight: 280)
                .padding(.top, 4)
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
        primaryButton(saving ? "Saving…" : "Start planning") {
          Task { await finish(saveFilters: true) }
        }
        .disabled(saving)
      }
    }
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
    case .filters: step = .welcome
    case .how:
      if howIndex > 0 { withAnimation { howIndex -= 1 } } else { step = .filters }
    }
  }

  private var filterBody: [String: Any] {
    [
      "diets": FiltersView.diets.filter { diets.contains($0) },
      // Keep Other words saved in Settings or Taste Lab; allergies aren't sent, so the server keeps them.
      "avoids": FiltersView.avoids.filter { avoids.contains($0) } + avoids.filter { !FiltersView.avoids.contains($0) }.sorted(),
      "time": time,
    ]
  }

  private func loadFilters() async {
    do {
      let prefs = try await KitchenAPI.prefs()
      guard let saved = prefs["filters"] as? [String: Any] else { return }
      if let d = saved["diets"] as? [String], !d.isEmpty { diets = FiltersView.cleaned(d) }
      if let a = saved["avoids"] as? [String] { avoids = Set(a) }
      if let t = saved["time"] as? String { time = t }
    } catch { self.error = KitchenAPI.message(error) }
  }

  @discardableResult
  private func markDone(filters: [String: Any]?) async -> Bool {
    var patch: [String: Any] = ["tour_done": true]
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

  private func finish(saveFilters: Bool) async {
    saving = true
    defer { saving = false }
    let ok = await markDone(filters: saveFilters ? filterBody : nil)
    // Skip always closes; a failed save of chosen filters keeps the tour open so nothing is lost.
    if ok || !saveFilters { session.showTour = false }
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
