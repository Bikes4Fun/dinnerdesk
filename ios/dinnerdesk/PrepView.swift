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
  @State private var missingOpen = false

  private static let sections: [(key: String, title: String, short: String)] = [
    ("veg", "Vegetables", "Veg"),
    ("herbs", "Aromatics, herbs & citrus", "Aromatics"),
    ("protein", "Protein", "Protein"),
    ("cheese", "Cheese & dairy", "Cheese"),
    ("sauce", "Sauces & dressings", "Sauce"),
    ("other", "More prep", "More"),
  ]
  private static let coral = Color(hex: 0xFA7E5A)
  private static let coralTint = Color(hex: 0xFDE6DD)
  private static let coralInk = Color(hex: 0x8A3A22)
  /// Recipe pills and the picked step in the missing-step sheet (#78).
  static let pill = Color(hex: 0xF6EEF5)
  static let dash = Color(hex: 0xDCCDD8)
  private static let bodyInk = Color(hex: 0x2E1A2C)
  static let stepFont = Font.custom("DMSans-Regular", size: 15, relativeTo: .subheadline)

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
            missingButton
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
    .sheet(isPresented: $missingOpen) { MissingPrepSheet() }
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

  /// "Missing a prep step?" (#78 E): opens the sheet that picks a meal, then a step.
  private var missingButton: some View {
    Button { missingOpen = true } label: {
      HStack(spacing: 12) {
        Image(systemName: "plus.circle").font(.system(size: 22)).accessibilityHidden(true)
        VStack(alignment: .leading, spacing: 2) {
          Text("Missing a prep step?").font(Theme.action)
          Text("Pick a step from this week’s recipes.").font(Theme.subtitle).foregroundStyle(Theme.muted)
        }
        Spacer(minLength: 0)
      }
      .foregroundStyle(Theme.accent)
      .padding(16)
      .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
      .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Self.dash, style: StrokeStyle(lineWidth: 1.5, dash: [5, 4])))
      .contentShape(Rectangle())
    }
    .buttonStyle(.plain)
    .padding(.top, 8)
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
    let open = detailsOpen.contains(task.id)
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

        Button { toggleDetails(task) } label: {
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
        .accessibilityHint(open ? "Hides the recipe steps" : "Shows the recipe steps")

        // 👍/👎 only on the open item (#78 D); closed rows stay quiet.
        if open {
          ThumbsControl(rating: task.rating ?? 0, subject: "prepping \(task.name) ahead") { next in
            whyOpen = next < 0 ? task.id : nil
            Task { await store.ratePrepTask(task.id, next, reason: next < 0 ? (task.reason ?? "") : "") }
          }
        }
        Button { toggleDetails(task) } label: {
          Image(systemName: "chevron.down")
            .font(.system(size: 15, weight: .bold))
            .foregroundStyle(open ? Theme.ink : Theme.muted)
            .rotationEffect(.degrees(open ? 180 : 0))
            .frame(width: 32, height: 32)
            .background(open ? Theme.aubergineTint : Color.clear, in: Circle())
            .frame(width: 44, height: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(open ? "Hide steps for \(task.name)" : "Show steps for \(task.name)")
      }
      .padding(.leading, 4)
      .padding(.trailing, 6)
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
          .padding(.leading, 54)
        } else if (task.rating ?? 0) < 0, let id = task.reason, let reason = PrepReason(rawValue: id) {
          Text(reason.label).font(Theme.count.weight(.semibold)).foregroundStyle(Self.coralInk)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Self.coralTint, in: RoundedRectangle(cornerRadius: 6))
            .padding(.leading, 54)
        }
        if open {
          // #78 D: the cook day on the left, the step, then each meal as a light pill link.
          VStack(alignment: .leading, spacing: 14) {
            ForEach(Array(Self.stepGroups(task).enumerated()), id: \.offset) { _, group in
              HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text((group.meals.first?.day ?? "").uppercased())
                  .font(Theme.count.weight(.bold)).tracking(0.5)
                  .foregroundStyle(Theme.ink)
                  .frame(width: 34, alignment: .center)
                  .accessibilityHidden(group.meals.first?.day == nil)
                VStack(alignment: .leading, spacing: 6) {
                  Text(group.text).font(Self.stepFont).foregroundStyle(Self.bodyInk)
                    .fixedSize(horizontal: false, vertical: true)
                  if Self.isAdded(task, group.text) {
                    Text("Added by you").font(Theme.count).foregroundStyle(Theme.muted)
                  }
                  ForEach(group.meals) { meal in
                    NavigationLink { RecipeDetailView(id: meal.id) } label: {
                      HStack(spacing: 4) {
                        Text(meal.name).lineLimit(1).truncationMode(.tail)
                        Image(systemName: "chevron.right").font(.system(size: 10, weight: .bold)).opacity(0.6)
                      }
                      .font(Theme.count.weight(.semibold))
                      .foregroundStyle(Theme.ink)
                      .padding(.leading, 10).padding(.trailing, 8).padding(.vertical, 5)
                      .background(Self.pill, in: Capsule())
                      .frame(minHeight: 32)
                      .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(meal.name)\(meal.day.map { ", \($0)" } ?? "")")
                    .accessibilityHint("Opens the recipe")
                  }
                }
              }
            }
          }
          .padding(.leading, 14)
        }
      }
      .padding(.trailing, 14)
      .padding(.bottom, whyOpen == task.id || open || (task.rating ?? 0) < 0 ? 14 : 0)
    }
    .background(task.done ? Theme.bg : Theme.surface)
  }

  private func toggleDetails(_ task: PrepTask) {
    if detailsOpen.contains(task.id) {
      detailsOpen.remove(task.id)
      if whyOpen == task.id { whyOpen = nil }
    } else {
      detailsOpen.insert(task.id)
    }
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

  private static func isAdded(_ task: PrepTask, _ text: String) -> Bool {
    task.meals.contains { meal in (meal.steps ?? []).contains { $0.added == true && $0.text == text } }
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

/// "Missing a prep step?" (#78 F): pick the meal, then the step that should have been prep,
/// optionally say why, and it joins prep (and is logged for review).
struct MissingPrepSheet: View {
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var meals: [MissingPrepMeal]?
  @State private var failed = false
  @State private var mealId: Int?
  @State private var stepKey: String?
  @State private var note = ""
  @State private var saving = false
  @State private var added: (meal: String, text: String)?

  private var meal: MissingPrepMeal? { meals?.first { $0.id == mealId } }
  private var step: MissingPrepStep? { meal?.steps.first { $0.key == stepKey } }

  var body: some View {
    NavigationStack {
      ScrollView {
        VStack(alignment: .leading, spacing: 18) {
          Text("Tell us a step that would have saved time if you did it ahead. We’ll add it to your prep and use it to make prep better.")
            .font(Theme.subtitle).foregroundStyle(Theme.muted)
            .fixedSize(horizontal: false, vertical: true)
          if let added {
            confirmation(added)
          } else if let meals {
            if meals.isEmpty {
              Text("Every step of this week’s recipes is already in prep.")
                .font(Theme.subtitle).foregroundStyle(Theme.muted)
            } else {
              mealPicker(meals)
              if let meal { stepPicker(meal) }
              if let meal, let step { noteAndAdd(meal, step) }
            }
          } else if failed {
            VStack(spacing: 12) {
              Text("Couldn’t load the recipes.").font(Theme.subtitle).foregroundStyle(Theme.muted)
              Button("Try again") { Task { await load() } }.font(Theme.action).frame(minHeight: 44)
            }
            .frame(maxWidth: .infinity)
          } else {
            ProgressView().frame(maxWidth: .infinity, minHeight: 120)
          }
        }
        .padding(.horizontal, 20)
        .padding(.bottom, 28)
      }
      .background(Theme.bg)
      .navigationTitle("Missing a prep step?")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button { dismiss() } label: { Image(systemName: "xmark") }
            .accessibilityLabel("Close")
        }
      }
    }
    .task { await load() }
  }

  private func load() async {
    failed = false
    meals = await store.loadMissingPrep()
    failed = meals == nil
  }

  private func label(_ text: String) -> some View {
    Text(text.uppercased()).font(Theme.count.weight(.bold)).tracking(0.8).foregroundStyle(Theme.muted)
      .accessibilityAddTraits(.isHeader)
  }

  private func dayText(_ day: String?) -> some View {
    Text((day ?? "").uppercased()).font(Theme.count.weight(.bold)).tracking(0.5)
      .foregroundStyle(Theme.ink).frame(width: 36, alignment: .leading)
      .accessibilityHidden(true)
  }

  // 1 · Meal: the full list until one is picked, then just that meal with Change.
  @ViewBuilder private func mealPicker(_ meals: [MissingPrepMeal]) -> some View {
    VStack(alignment: .leading, spacing: 8) {
      label("1 · Meal")
      if let meal {
        HStack(spacing: 10) {
          dayText(meal.day)
          Text(meal.name).font(Theme.mealName).foregroundStyle(Theme.ink)
            .frame(maxWidth: .infinity, alignment: .leading)
          Button("Change") {
            mealId = nil
            stepKey = nil
            note = ""
          }
          .font(Theme.action).foregroundStyle(Theme.accent).frame(minHeight: 44)
        }
        .padding(.leading, 14).padding(.trailing, 8).padding(.vertical, 6)
        .background(PrepView.pill, in: RoundedRectangle(cornerRadius: 16))
      } else {
        VStack(spacing: 0) {
          ForEach(Array(meals.enumerated()), id: \.element.id) { index, m in
            if index > 0 { Rectangle().fill(Theme.line).frame(height: 1) }
            Button {
              mealId = m.id
              stepKey = nil
              note = ""
            } label: {
              HStack(spacing: 10) {
                dayText(m.day)
                VStack(alignment: .leading, spacing: 2) {
                  Text(m.name).font(Theme.mealName).foregroundStyle(Theme.ink)
                  Text(m.steps.count == 1 ? "1 step not in prep" : "\(m.steps.count) steps not in prep")
                    .font(Theme.subtitle).foregroundStyle(Theme.muted)
                }
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: "chevron.right").foregroundStyle(Theme.muted).accessibilityHidden(true)
              }
              .padding(.horizontal, 14).padding(.vertical, 12)
              .frame(minHeight: 64)
              .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("\(m.name)\(m.day.map { ", \($0)" } ?? "")")
          }
        }
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.line))
      }
    }
  }

  // 2 · The step that should have been prep.
  private func stepPicker(_ meal: MissingPrepMeal) -> some View {
    VStack(alignment: .leading, spacing: 8) {
      label("2 · Step that should be prep")
      ForEach(meal.steps) { s in
        if s.added {
          // Already added: no radio, just a way to take it back.
          HStack(alignment: .top, spacing: 12) {
            Image(systemName: "checkmark.circle.fill").font(.system(size: 20)).foregroundStyle(Theme.ink)
              .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
              Text("Step \(s.step) · in your prep").font(Theme.subtitle).foregroundStyle(Theme.muted)
              Text(s.text).font(PrepView.stepFont).foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
              Button("Remove from prep") { Task { await save(meal, s, adding: false) } }
                .font(Theme.count.weight(.semibold)).foregroundStyle(Theme.accent)
                .frame(minHeight: 44)
                .disabled(saving)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
          }
          .padding(14)
          .background(Theme.surface, in: RoundedRectangle(cornerRadius: 14))
          .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        } else {
          let on = s.key == stepKey
          Button { stepKey = s.key } label: {
            HStack(alignment: .top, spacing: 12) {
              Image(systemName: on ? "largecircle.fill.circle" : "circle")
                .font(.system(size: 20))
                .foregroundStyle(on ? Theme.ink : Theme.muted)
                .accessibilityHidden(true)
              VStack(alignment: .leading, spacing: 3) {
                Text("Step \(s.step)").font(Theme.subtitle).foregroundStyle(Theme.muted)
                Text(s.text).font(PrepView.stepFont).foregroundStyle(Theme.ink)
                  .fixedSize(horizontal: false, vertical: true)
              }
              .multilineTextAlignment(.leading)
              .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(14)
            .background(on ? PrepView.pill : Theme.surface, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(on ? Theme.ink : Theme.line, lineWidth: on ? 1.5 : 1))
            .contentShape(Rectangle())
          }
          .buttonStyle(.plain)
          .accessibilityAddTraits(on ? .isSelected : [])
        }
      }
    }
  }

  // 3 · Why (optional), then Add to prep.
  private func noteAndAdd(_ meal: MissingPrepMeal, _ step: MissingPrepStep) -> some View {
    VStack(alignment: .leading, spacing: 12) {
      label("3 · Why do it ahead? (optional)")
      TextField("e.g. Tofu needs 15 min to press — no time on a weeknight", text: $note, axis: .vertical)
        .font(Theme.subtitle)
        .lineLimit(2...5)
        .padding(12)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
        .accessibilityLabel("Why do it ahead? Optional")
      Button { Task { await save(meal, step, adding: true) } } label: {
        Text(saving ? "Adding…" : "Add to prep").font(Theme.action).foregroundStyle(Theme.surface)
          .frame(maxWidth: .infinity, minHeight: 50)
          .background(Theme.ink, in: Capsule())
      }
      .buttonStyle(.plain)
      .disabled(saving)
    }
  }

  private func confirmation(_ done: (meal: String, text: String)) -> some View {
    VStack(spacing: 10) {
      Image(systemName: "checkmark")
        .font(.system(size: 22, weight: .bold)).foregroundStyle(Theme.ink)
        .frame(width: 48, height: 48)
        .background(Color(hex: 0xFA7E5A), in: Circle())
        .accessibilityHidden(true)
      Text("Added to your prep").font(Theme.tourTitle).foregroundStyle(Theme.ink)
      Text(done.text).font(Theme.subtitle).foregroundStyle(Theme.ink).multilineTextAlignment(.center)
      Text("\(done.meal) · marked “Added by you”").font(Theme.subtitle).foregroundStyle(Theme.muted)
        .multilineTextAlignment(.center)
      HStack(spacing: 10) {
        Button {
          added = nil
          mealId = nil
          stepKey = nil
          note = ""
        } label: {
          Text("Add another").font(Theme.action).foregroundStyle(Theme.ink)
            .frame(maxWidth: .infinity, minHeight: 44)
            .overlay(Capsule().stroke(Theme.line))
        }
        .buttonStyle(.plain)
        Button { dismiss() } label: {
          Text("Done").font(Theme.action).foregroundStyle(Theme.surface)
            .frame(maxWidth: .infinity, minHeight: 44)
            .background(Theme.ink, in: Capsule())
        }
        .buttonStyle(.plain)
      }
      .padding(.top, 6)
    }
    .padding(20)
    .frame(maxWidth: .infinity)
    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 16))
    .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.line))
    .accessibilityElement(children: .contain)
  }

  private func save(_ meal: MissingPrepMeal, _ step: MissingPrepStep, adding: Bool) async {
    saving = true
    let text = adding ? note.trimmingCharacters(in: .whitespacesAndNewlines) : ""
    if await store.setMissingPrep(recipeId: meal.id, key: step.key, note: text, added: adding),
      let m = meals?.firstIndex(where: { $0.id == meal.id }),
      let s = meals?[m].steps.firstIndex(where: { $0.key == step.key })
    {
      meals?[m].steps[s].added = adding
      meals?[m].steps[s].note = text
      if adding { added = (meal.name, step.text) }
      stepKey = nil
      note = ""
    }
    saving = false
  }
}

private extension Array {
  var nilIfEmpty: [Element]? { isEmpty ? nil : self }
}
