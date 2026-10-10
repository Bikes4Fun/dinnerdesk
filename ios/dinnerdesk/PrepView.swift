import SwiftUI

/// Weekend prep, grouped by what the food is (#21; mirrors web/src/pages/Prep.jsx).
/// One row per item however many meals use it. A progress ring and one bar per section up
/// top; collapsible sections; 👍/👎 on every item (a 👎 asks why); and check-off that works like
/// the grocery list: a done item leaves its section unless "Show completed" is on, and a bar at
/// the bottom offers Undo and asks whether it was worth doing ahead.
struct PrepView: View {
  @EnvironmentObject private var store: Store
  @Environment(\.selectTab) private var selectTab
  @Environment(\.dismiss) private var dismiss
  @Environment(\.dynamicTypeSize) private var typeSize

  @AppStorage("prep.showDone") private var showDone = false
  @AppStorage("prep.closed") private var closedRaw = ""
  @State private var whyOpen: Int?
  @State private var detailsOpen: Set<Int> = []
  @State private var toast: Int?
  @State private var toastWhy = false

  private static let sections: [(key: String, title: String, short: String)] = [
    ("veg", "Vegetables", "Veg"),
    ("herbs", "Aromatics, herbs & citrus", "Herbs"),
    ("protein", "Protein", "Protein"),
    ("cheese", "Cheese & dairy", "Cheese"),
    ("sauce", "Sauces & dressings", "Sauce"),
    ("other", "More prep", "More"),
  ]
  private static let coral = Color(hex: 0xFA7E5A)
  private static let coralTint = Color(hex: 0xFDE6DD)
  private static let coralInk = Color(hex: 0x8A3A22)

  private var closed: Set<String> { Set(closedRaw.split(separator: ",").map(String.init)) }
  private var tasks: [PrepTask] { store.prepTasks }
  private var doneCount: Int { tasks.filter(\.done).count }

  private struct PrepGroup: Identifiable {
    let key: String, title: String, short: String
    let all: [PrepTask]
    let shown: [PrepTask]
    var id: String { key }
    var done: Int { all.filter(\.done).count }
  }

  private var groups: [PrepGroup] {
    Self.sections.compactMap { s in
      let all = tasks.filter { ($0.section ?? "other") == s.key }
      guard !all.isEmpty else { return nil }
      let left = all.filter { !$0.done }
      return PrepGroup(
        key: s.key, title: s.title, short: s.short, all: all,
        shown: showDone ? left + all.filter(\.done) : left)
    }
  }

  var body: some View {
    ScrollViewReader { proxy in
      ScrollView {
        LazyVStack(alignment: .leading, spacing: 16) {
          if let err = store.error { ErrorBanner(message: err) }
          if tasks.isEmpty {
            EmptyState(
              title: "No prep yet",
              message: "Add meals on Plan. Make-ahead steps like chopping, grating and sauces show up here.",
              systemImage: "list.clipboard")
            Button("Back to plan") {
              selectTab(.plan)
              dismiss()
            }
            .font(Theme.action)
            .frame(maxWidth: .infinity, minHeight: 44)
          } else {
            header { key in withAnimation { proxy.scrollTo(key, anchor: .top) } }
            ForEach(groups) { group in section(group).id(group.key) }
          }
          // Room so the check-off bar never covers the last row.
          Color.clear.frame(height: toast == nil ? 8 : 180)
        }
        .padding(.horizontal, 16)
        .padding(.top, 4)
      }
    }
    .background(Theme.bg)
    .overlay(alignment: .bottom) { toastBar }
    .navigationTitle("Weekend prep")
    .largeNavigationTitle()
    .refreshable { await store.loadPrep() }
    .task { await store.loadPrep() }
  }

  // MARK: Header

  private func header(jump: @escaping (String) -> Void) -> some View {
    VStack(alignment: .leading, spacing: 14) {
      HStack(alignment: .center, spacing: 14) {
        ZStack {
          Circle().stroke(Theme.aubergineTint, lineWidth: 7)
          Circle()
            .trim(from: 0, to: tasks.isEmpty ? 0 : CGFloat(doneCount) / CGFloat(tasks.count))
            .stroke(Self.coral, style: StrokeStyle(lineWidth: 7, lineCap: .butt))
            .rotationEffect(.degrees(-90))
          Text("\(doneCount)/\(tasks.count)").font(Theme.count.weight(.bold)).foregroundStyle(Theme.ink)
            .minimumScaleFactor(0.6)
        }
        .frame(width: 56, height: 56)
        .accessibilityElement()
        .accessibilityLabel("\(doneCount) of \(tasks.count) prep items done")
        Text(Copy.text("prep.about")).font(Theme.subtitle).foregroundStyle(Theme.muted)
          .fixedSize(horizontal: false, vertical: true)
      }
      // One bar per section. Tap to jump there.
      // At large text the bars stack so their labels stay readable.
      let bars = ForEach(groups) { g in
        Button { jump(g.key) } label: {
          VStack(alignment: .leading, spacing: 6) {
            GeometryReader { geo in
              ZStack(alignment: .leading) {
                Capsule().fill(Theme.aubergineTint)
                Capsule().fill(Self.coral).frame(width: geo.size.width * CGFloat(g.done) / CGFloat(g.all.count))
              }
            }
            .frame(height: 8)
            Text("\(g.short) ").font(Theme.count.weight(.bold)).foregroundStyle(Theme.ink)
              + Text("\(g.done)/\(g.all.count)").font(Theme.count).foregroundStyle(Theme.muted)
          }
          .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
          .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(g.title), \(g.done) of \(g.all.count) done")
      }
      if typeSize.isAccessibilitySize {
        VStack(alignment: .leading, spacing: 8) { bars }
      } else {
        HStack(alignment: .top, spacing: 6) { bars }
      }
      HStack {
        Text("\(doneCount) completed").font(Theme.subtitle).foregroundStyle(Theme.muted)
        Spacer()
        if doneCount > 0 {
          Button(showDone ? "Hide completed" : "Show completed") { showDone.toggle() }
            .font(Theme.action).foregroundStyle(Theme.accent)
            .frame(minHeight: 44)
        }
      }
    }
  }

  // MARK: Sections

  private func section(_ g: PrepGroup) -> some View {
    let open = !closed.contains(g.key)
    return VStack(alignment: .leading, spacing: 8) {
      Button {
        var next = closed
        if open { next.insert(g.key) } else { next.remove(g.key) }
        closedRaw = next.sorted().joined(separator: ",")
      } label: {
        HStack(spacing: 10) {
          Text(g.title).font(Theme.recipeTitle.weight(.semibold)).foregroundStyle(Theme.ink)
            .multilineTextAlignment(.leading)
            .frame(maxWidth: .infinity, alignment: .leading)
          Text("\(g.done) of \(g.all.count)").font(Theme.count).foregroundStyle(Theme.muted)
          Image(systemName: "chevron.up")
            .font(.system(size: 15, weight: .bold))
            .foregroundStyle(Theme.ink)
            .rotationEffect(.degrees(open ? 0 : 180))
            .frame(width: 32, height: 32)
            .background(Theme.aubergineTint, in: Circle())
        }
        .frame(minHeight: 44)
        .contentShape(Rectangle())
      }
      .buttonStyle(.plain)
      .accessibilityAddTraits(.isHeader)
      .accessibilityValue(open ? "Expanded" : "Collapsed")

      if open {
        if g.shown.isEmpty {
          Text("All prepped here.").font(Theme.subtitle).foregroundStyle(Theme.muted)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Theme.line, style: StrokeStyle(lineWidth: 1, dash: [4])))
        } else {
          VStack(spacing: 0) {
            ForEach(Array(g.shown.enumerated()), id: \.element.id) { index, task in
              if index > 0 { Rectangle().fill(Theme.line).frame(height: 1) }
              row(task)
            }
          }
          .background(Theme.surface, in: RoundedRectangle(cornerRadius: 16))
          .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.line))
          .clipShape(RoundedRectangle(cornerRadius: 16))
        }
      }
    }
  }

  // MARK: Rows

  private func row(_ task: PrepTask) -> some View {
    let sub = task.quantities.filter { !$0.isEmpty }.joined(separator: " · ")
    return VStack(alignment: .leading, spacing: 8) {
      HStack(alignment: .center, spacing: 10) {
        Button {
          let next = !task.done
          Task { await store.togglePrep(task) }
          toast = next ? task.id : nil
          toastWhy = false
        } label: {
          Image(systemName: task.done ? "checkmark.circle.fill" : "circle")
            .font(.system(size: 26))
            .foregroundStyle(task.done ? Self.coral : Theme.muted)
            .frame(width: 44, height: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(task.done ? "Uncheck \(task.name)" : "Check off \(task.name)")

        Button {
          if detailsOpen.contains(task.id) { detailsOpen.remove(task.id) } else { detailsOpen.insert(task.id) }
        } label: {
          VStack(alignment: .leading, spacing: 2) {
            Text(task.name).font(Theme.mealName).foregroundStyle(Theme.ink)
              .strikethrough(task.done)
            if !sub.isEmpty { Text(sub).font(Theme.subtitle).foregroundStyle(Theme.muted) }
          }
          .multilineTextAlignment(.leading)
          .frame(maxWidth: .infinity, alignment: .leading)
          .opacity(task.done ? 0.6 : 1)
          .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityHint(detailsOpen.contains(task.id) ? "Hides the recipe steps" : "Shows the recipe steps")

        ThumbsControl(rating: task.rating ?? 0, subject: "prepping \(task.name) ahead") { next in
          whyOpen = next < 0 ? task.id : nil
          Task { await store.ratePrepTask(task.id, next, reason: next < 0 ? (task.reason ?? "") : "") }
        }
      }
      .padding(.leading, 4)
      .padding(.vertical, 6)

      Group {
        if whyOpen == task.id {
          VStack(alignment: .leading, spacing: 8) {
            Text("Why not?").font(Theme.action).foregroundStyle(Theme.ink)
            KitchenFlow(spacing: 6) {
              ForEach(PrepReason.allCases) { reason in
                chip(reason.label, on: task.reason == reason.rawValue) {
                  whyOpen = nil
                  Task { await store.ratePrepTask(task.id, -1, reason: reason.rawValue) }
                }
              }
            }
          }
        } else if (task.rating ?? 0) < 0, let id = task.reason, let reason = PrepReason(rawValue: id) {
          Text(reason.label).font(Theme.count.weight(.semibold)).foregroundStyle(Self.coralInk)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Self.coralTint, in: RoundedRectangle(cornerRadius: 6))
        }
        if detailsOpen.contains(task.id) {
          // One line per distinct step; the meals that use it are small links underneath.
          VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(Self.stepGroups(task).enumerated()), id: \.offset) { _, group in
              VStack(alignment: .leading, spacing: 3) {
                Text(group.text).font(Theme.subtitle).foregroundStyle(Theme.ink)
                  .fixedSize(horizontal: false, vertical: true)
                ForEach(group.meals) { meal in
                  NavigationLink { RecipeDetailView(id: meal.id) } label: {
                    Text(meal.name).font(Theme.count.weight(.semibold)).foregroundStyle(Theme.accent)
                      .multilineTextAlignment(.leading)
                      .frame(maxWidth: .infinity, minHeight: 28, alignment: .leading)
                  }
                  .buttonStyle(.plain)
                  .accessibilityHint("Opens the recipe")
                }
              }
              .padding(.leading, 10)
              .overlay(alignment: .leading) { Rectangle().fill(Theme.line).frame(width: 2) }
            }
          }
        }
      }
      .padding(.leading, 58)
      .padding(.trailing, 14)
      .padding(.bottom, whyOpen == task.id || detailsOpen.contains(task.id) || (task.rating ?? 0) < 0 ? 12 : 0)
    }
    .background(task.done ? Theme.bg : Theme.surface)
  }

  private func chip(_ text: String, on: Bool, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      Text(text).font(Theme.chipLabel)
        .padding(.horizontal, 14)
        .frame(minHeight: 44)
        .foregroundStyle(on ? Theme.surface : Theme.ink)
        .background(on ? Theme.ink : Theme.surface, in: Capsule())
        .overlay(Capsule().stroke(on ? Theme.ink : Theme.line))
    }
    .buttonStyle(.plain)
    .accessibilityAddTraits(on ? .isSelected : [])
  }

  /// The open row's steps, each distinct text once with the meals that use it, in meal order.
  private static func stepGroups(_ task: PrepTask) -> [(text: String, meals: [PrepMeal])] {
    var out: [(text: String, meals: [PrepMeal])] = []
    for meal in task.meals {
      let texts = (meal.steps ?? []).map(\.text).nilIfEmpty ?? meal.instructions
      for text in texts {
        let key = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if let i = out.firstIndex(where: { $0.text.caseInsensitiveCompare(key) == .orderedSame }) {
          if !out[i].meals.contains(where: { $0.id == meal.id }) { out[i].meals.append(meal) }
        } else {
          out.append((key, [meal]))
        }
      }
    }
    return out
  }

  // MARK: Check-off bar

  @ViewBuilder private var toastBar: some View {
    if let id = toast, let task = tasks.first(where: { $0.id == id }) {
      VStack(alignment: .leading, spacing: 6) {
        HStack(spacing: 10) {
          Image(systemName: "checkmark.circle.fill").foregroundStyle(Self.coral)
            .accessibilityHidden(true)
          Text("\(task.name) checked off").font(Theme.action).foregroundStyle(Theme.surface)
            .frame(maxWidth: .infinity, alignment: .leading)
          Button("Undo") {
            Task { await store.togglePrep(task) }
            toast = nil
          }
          .font(Theme.action).foregroundStyle(Self.coralTint).underline()
          .frame(minHeight: 44)
          Button { toast = nil } label: {
            Image(systemName: "xmark").foregroundStyle(Theme.aubergineTint).frame(width: 44, height: 44)
          }
          .accessibilityLabel("Dismiss")
        }
        HStack(spacing: 8) {
          Text("Worth prepping ahead next time?").font(Theme.subtitle).foregroundStyle(Theme.aubergineTint)
            .frame(maxWidth: .infinity, alignment: .leading)
          toastThumb(up: true, on: (task.rating ?? 0) > 0) {
            toast = nil
            Task { await store.ratePrepTask(task.id, 1) }
          }
          toastThumb(up: false, on: (task.rating ?? 0) < 0) {
            toastWhy = true
            Task { await store.ratePrepTask(task.id, -1, reason: task.reason ?? "") }
          }
        }
        if toastWhy {
          KitchenFlow(spacing: 6) {
            ForEach(PrepReason.allCases) { reason in
              Button {
                toast = nil
                Task { await store.ratePrepTask(task.id, -1, reason: reason.rawValue) }
              } label: {
                Text(reason.label).font(Theme.chipLabel).foregroundStyle(Theme.ink)
                  .padding(.horizontal, 14).frame(minHeight: 44)
                  .background(task.reason == reason.rawValue ? Self.coral : Theme.surface, in: Capsule())
              }
              .buttonStyle(.plain)
            }
          }
        }
      }
      .padding(.leading, 16).padding(.trailing, 6).padding(.vertical, 8)
      .background(Theme.ink, in: RoundedRectangle(cornerRadius: 20))
      .shadow(color: Theme.ink.opacity(0.25), radius: 14, y: 6)
      .padding(.horizontal, 12)
      .padding(.bottom, 12)
      .transition(.move(edge: .bottom).combined(with: .opacity))
    }
  }

  private func toastThumb(up: Bool, on: Bool, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      Image(systemName: up ? (on ? "hand.thumbsup.fill" : "hand.thumbsup") : (on ? "hand.thumbsdown.fill" : "hand.thumbsdown"))
        .foregroundStyle(on ? Theme.ink : Theme.surface)
        .frame(width: 44, height: 44)
        .background(on ? Self.coral : Color.clear, in: Circle())
        .overlay(Circle().stroke(on ? Self.coral : Theme.surface.opacity(0.4)))
    }
    .buttonStyle(.plain)
    .accessibilityLabel(up ? "Yes, worth it" : "No, not worth it")
    .accessibilityAddTraits(on ? .isSelected : [])
  }
}

private extension Array {
  var nilIfEmpty: [Element]? { isEmpty ? nil : self }
}
