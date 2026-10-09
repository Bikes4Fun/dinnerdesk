import SwiftUI
import UIKit

struct PlanView: View {
  @EnvironmentObject private var store: Store
  @Environment(\.selectTab) private var selectTab
  @Environment(\.dynamicTypeSize) private var typeSize
  @State private var grid = false
  @State private var editing = false
  @State private var selected: Set<Int> = []
  @State private var menu = false
  @State private var picking: PlanSlot?
  @State private var drafts = false
  @State private var savingDraft = false
  @State private var draftTitle = ""
  @State private var removing = false
  /// Width of the plan list after its padding. One photo size is chosen from this.
  @State private var totalRowWidth: CGFloat = 350

  var body: some View {
    NavigationStack {
      ScrollView {
        VStack(alignment: .leading, spacing: 16) {

          // New inline custom header replacing the native toolbar
          HStack {
            Text(store.plan?.title ?? "This week")
              .font(Theme.bigTitle)

            Spacer()

            // While editing, a visible Done is the way out; the ⋯ menu alone was too hidden.
            if editing {
              Button("Done") { setEditing(false) }
                .font(Theme.action)
                .foregroundStyle(Theme.accent)
                .frame(minHeight: 44)
                .contentShape(Rectangle())
                .accessibilityLabel("Done editing plan")
            }

            Button {
              menu = true
            } label: {
              Image(systemName: "ellipsis")
                .font(.title3)
                .frame(minWidth: 44, minHeight: 44)
            }
            .accessibilityLabel("Plan menu")
          }
          .padding(.bottom, 4)

          if let error = store.error { ErrorBanner(message: error) }
          if let plan = store.plan {
            let photoWidth = calculateGlobalPhotoWidth(for: plan, availableWidth: totalRowWidth)
            if plan.status == "suggested", let note = plan.suggestionNote, !note.isEmpty {
              VStack(alignment: .leading, spacing: 8) {
                Text(note).font(Theme.subtitle).foregroundStyle(Theme.muted)
                NavigationLink {
                  TasteLabView(swipe: true)
                } label: {
                  Text("Improve your results")
                    .font(Theme.subtitle)
                    .foregroundStyle(Theme.accent)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
              }
            }
            if plan.slots.isEmpty {
              VStack {
                EmptyState(
                  title: "Nothing on this plan",
                  message: "Get suggestions for your next meals.",
                  systemImage: "calendar")
                Button {
                  Task { await store.newPlan(meals: 4) }
                } label: {
                  Label("New meal plan", systemImage: "sparkles")
                }
                .buttonStyle(.borderedProminent)
                .tint(Theme.accent)
              }
            }
            if editing && !plan.slots.isEmpty {
              // Side by side when it fits; stacked at large text so no word breaks mid-way.
              ViewThatFits(in: .horizontal) {
                HStack {
                  selectAllButton(plan)
                  Spacer()
                  selectedCount
                }
                VStack(alignment: .leading, spacing: 8) {
                  selectAllButton(plan)
                  selectedCount
                }
              }
              ViewThatFits(in: .horizontal) {
                HStack {
                  markCookedButton
                  Spacer()
                  removeButton
                }
                VStack(alignment: .leading, spacing: 8) {
                  markCookedButton
                  removeButton
                }
              }
              .disabled(selected.isEmpty)
            }
            ForEach(groups(plan), id: \.key) { group in
              if group.key >= 0 { KitchenHeader(dayTitle(plan.startDate, group.key)) }
              // At accessibility text sizes the grid shows as the list, so names don't break mid-word.
              if grid && !editing && !typeSize.isAccessibilitySize {
                LazyVGrid(
                  columns: [GridItem(.flexible(), alignment: .top), GridItem(.flexible(), alignment: .top)],
                  alignment: .leading, spacing: 16) {
                  ForEach(group.slots) { slot in
                    meal(slot, plan: plan, grid: true, photoWidth: photoWidth)
                  }
                }
              } else {
                ForEach(group.slots) { slot in
                  meal(slot, plan: plan, grid: false, photoWidth: photoWidth)
                  Divider()
                }
              }
            }
            Button {
              selectTab(.recipes)
            } label: {
              Label("Add meals", systemImage: "plus")
            }
            .font(Theme.mealName).padding(.vertical)
          } else {
            ProgressView()
          }
        }
        .background {
          GeometryReader { geo in
            Color.clear.preference(key: PlanRowWidthKey.self, value: geo.size.width)
          }
        }
        .padding()
      }
      .onPreferenceChange(PlanRowWidthKey.self) { totalRowWidth = $0 }
      .background(Theme.bg)
      .navigationBarTitleDisplayMode(.inline)
      .tint(Theme.accent)
      .menuSheet(isPresented: $menu) {
        [
          MenuSheetItem(title: editing ? "Finish editing" : "Edit plan", systemImage: editing ? "checkmark.circle" : "pencil") {
            setEditing(!editing)
          },
          MenuSheetItem(title: "Mark all cooked", systemImage: "checkmark.circle") {
            Task { await store.markAllCooked() }
          },
          MenuSheetItem(
            title: grid ? "List View" : "Grid View", systemImage: "square.grid.2x2"
          ) { grid.toggle() },
          MenuSheetItem(title: "Save as draft", systemImage: "square.and.arrow.down") {
            draftTitle = store.plan?.title ?? "Saved plan"
            savingDraft = true
          },
          MenuSheetItem(title: "Saved plans & history", systemImage: "tray") { drafts = true },
          MenuSheetItem(title: "New meal plan", systemImage: "sparkles") { Task { await store.newPlan(meals: 4) } }
        ]
      }
      .alert("Save as draft", isPresented: $savingDraft) {
        TextField("Plan name", text: $draftTitle)
        Button("Save") { Task { await store.saveDraft(title: draftTitle) } }
        Button("Cancel", role: .cancel) {}
      }
      .sheet(isPresented: $removing) {
        RemovalConfirmation(title: "Remove \(selected.count) \(selected.count == 1 ? "meal" : "meals")?", message: "Selected meals will be removed from your plan.", actionTitle: selected.count == 1 ? "Remove meal" : "Remove meals") {
          await store.removeSlots(ids: selected)
          selected = []
        }
      }
      .sheet(item: $picking) { slot in ScheduleMealSheet(slot: slot) }
      .sheet(isPresented: $drafts) { SavedPlansView() }
      .sheet(isPresented: Binding(get: { store.proposal != nil }, set: { if !$0 { store.proposal = nil } })) {
        SuggestedPlanReview()
      }
      .refreshable { await store.loadAll() }
    }
  }

  /// Turns Edit mode on or off. Leaving it clears any meal selection.
  private func setEditing(_ on: Bool) {
    editing = on
    if !on { selected = [] }
  }

  private func groups(_ plan: Plan) -> [(key: Int, slots: [PlanSlot])] {
    Set(plan.slots.map { $0.dayIndex ?? -1 }).sorted().map { day in
      (
        day,
        plan.slots.filter { ($0.dayIndex ?? -1) == day }.sorted {
          if $0.cooked != $1.cooked { return !$0.cooked }
          return $0.id < $1.id
        }
      )
    }
  }

  /// Keep meal photos at their intended size; names wrap instead of shrinking the photo.
  private func calculateGlobalPhotoWidth(for plan: Plan, availableWidth: CGFloat) -> CGFloat {
    160
  }

  private func meal(_ slot: PlanSlot, plan: Plan, grid: Bool, photoWidth: CGFloat) -> some View {
    return Group {
      if grid && !editing && !typeSize.isAccessibilitySize {
        VStack(alignment: .leading, spacing: 8) {
          photo(slot, side: nil)
          HStack(alignment: .top, spacing: 8) {
            if editing { selectionButton(slot) }
            title(slot, plan: plan)
          }
          if editing { editControls(slot, plan: plan) }
        }
      } else if typeSize.isAccessibilitySize {
        VStack(alignment: .leading, spacing: 12) {
          HStack(alignment: .top) {
            if editing { selectionButton(slot) }
            photo(slot, side: photoWidth)
          }
          title(slot, plan: plan)
          if editing { editControls(slot, plan: plan) }
          else { scheduleButton(slot, plan: plan) }
        }
      } else {
        HStack(alignment: .top, spacing: 8) {
          if editing { selectionButton(slot) }
          photo(slot, side: photoWidth)
          VStack(alignment: .leading, spacing: 8) {
            title(slot, plan: plan)
            if editing { editControls(slot, plan: plan) }
            else { scheduleButton(slot, plan: plan) }
          }
        }
      }
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .opacity(slot.cooked ? 0.45 : 1)
  }

  /// Under each meal: rate it so suggestions learn. 👎 = never suggest again.
  private func thumbs(_ slot: PlanSlot) -> some View {
    VStack(alignment: .leading, spacing: 4) {
      HStack(spacing: 4) {
        ThumbsControl(rating: slot.rating ?? 0, subject: slot.recipeName) { next in
          Task { await store.rateMeal(slot, next) }
        }
        .padding(.leading, -12)
        if (slot.rating ?? 0) > 0 {
          Text("We'll suggest more like this").font(Theme.subtitle).foregroundStyle(Theme.muted)
        }
      }
      if (slot.rating ?? 0) < 0 { StarTip(id: "plan.disliked") }
    }
  }

  private func selectAllButton(_ plan: Plan) -> some View {
    Button(selected.count == plan.slots.count ? "Deselect all" : "Select all") {
      selected = selected.count == plan.slots.count ? [] : Set(plan.slots.map(\.id))
    }
    .buttonStyle(.plain)
    .frame(minHeight: 44)
    .contentShape(Rectangle())
    .accessibilityLabel("Select all meals")
    .accessibilityValue(
      selected.count == plan.slots.count ? "All meals selected" : "Select all meals")
  }

  private var selectedCount: some View {
    Text("\(selected.count) selected").foregroundStyle(Theme.muted)
  }

  private var markCookedButton: some View {
    Button("Mark cooked") {
      Task {
        await store.markCooked(ids: selected)
        selected = []
      }
    }
    .frame(minHeight: 44)
  }

  private var removeButton: some View {
    Button("Remove", role: .destructive) { removing = true }
      .frame(minHeight: 44)
  }

  private func selectionButton(_ slot: PlanSlot) -> some View {
    Button {
      if !selected.insert(slot.id).inserted { selected.remove(slot.id) }
    } label: {
      Image(systemName: selected.contains(slot.id) ? "checkmark.square.fill" : "square")
        .font(.system(size: 22))
        .foregroundStyle(selected.contains(slot.id) ? Theme.accent : Theme.muted)
        .frame(width: 32, height: 44)
        .contentShape(Rectangle())
    }
    .buttonStyle(.plain)
    .accessibilityLabel("Select \(slot.recipeName)")
    .accessibilityValue(selected.contains(slot.id) ? "Selected" : "Not selected")
  }

  private func editControls(_ slot: PlanSlot, plan: Plan) -> some View {
    VStack(alignment: .leading, spacing: 6) {
      ViewThatFits(in: .horizontal) {
        HStack(spacing: 8) {
          scheduleButton(slot, plan: plan)
          servingsControl(slot)
        }
        VStack(alignment: .leading, spacing: 4) {
          scheduleButton(slot, plan: plan)
          servingsControl(slot)
        }
      }
      thumbs(slot)
    }
  }

  private func scheduleButton(_ slot: PlanSlot, plan: Plan) -> some View {
    Button {
      picking = slot
    } label: {
      Label(scheduleLabel(slot, plan: plan), systemImage: "calendar")
        .font(Theme.subtitle)
        .padding(.horizontal, 8)
        .frame(minHeight: 44)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))
    }
    .buttonStyle(.plain)
    .accessibilityLabel("Schedule \(slot.recipeName)")
  }

  private func scheduleLabel(_ slot: PlanSlot, plan: Plan) -> String {
    guard let day = slot.dayIndex else { return "Schedule" }
    guard let start = planDate(plan.startDate),
      let date = Calendar.current.date(byAdding: .day, value: day, to: start)
    else {
      preconditionFailure("Invalid plan date")
    }
    return date.formatted(.dateTime.month(.abbreviated).day())
  }

  /// − count + in one box. The buttons grow with the text size so they never spill out of
  /// the box, and the count wraps instead of being cut off ("4 servin…").
  private func servingsControl(_ slot: PlanSlot) -> some View {
    HStack(spacing: 2) {
      Button {
        Task { await store.setServings(slot, slot.servings - 1) }
      } label: {
        Image(systemName: "minus").font(Theme.count)
          .frame(minWidth: 44, minHeight: 44).contentShape(Rectangle())
      }
      .disabled(slot.servings <= 1)
      .accessibilityLabel("Decrease servings for \(slot.recipeName)")
      Text("\(slot.servings) servings").font(Theme.count)
        .multilineTextAlignment(.center)
        .fixedSize(horizontal: false, vertical: true)
        .layoutPriority(1)
      Button {
        Task { await store.setServings(slot, slot.servings + 1) }
      } label: {
        Image(systemName: "plus").font(Theme.count)
          .frame(minWidth: 44, minHeight: 44).contentShape(Rectangle())
      }
      .disabled(slot.servings >= 50)
      .accessibilityLabel("Increase servings for \(slot.recipeName)")
    }
    .buttonStyle(.plain)
    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 10))
    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))
  }

  private func title(_ slot: PlanSlot, plan: Plan) -> some View {
    NavigationLink {
      RecipeDetailView(id: slot.recipeId)
    } label: {
      VStack(alignment: .leading, spacing: 4) {
        Text(slot.recipeName).font(Theme.mealName).foregroundStyle(Theme.ink)
          .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
        if !editing {
          Text("\(slot.servings) servings").font(Theme.subtitle).foregroundStyle(Theme.muted)
        }
      }
      .frame(maxWidth: .infinity, alignment: .leading)
    }.buttonStyle(.plain)
  }

  /// `side` locks a square of that size. Nil fills the column and stays square.
  private func photo(_ slot: PlanSlot, side: CGFloat?) -> some View {
    let square = Color.clear.aspectRatio(1, contentMode: .fit)
    return Group {
      if let side {
        square.frame(width: side, height: side)
      } else {
        square.frame(maxWidth: .infinity)
      }
    }
    .overlay {
        NavigationLink {
          RecipeDetailView(id: slot.recipeId)
        } label: {
          RecipePhoto(path: slot.photoPath, fill: true)
        }.buttonStyle(.plain)
      }
      .overlay(alignment: .topTrailing) {
        if !editing {
          Button {
            Task { await store.toggleCooked(slot) }
          } label: {
            Image(systemName: slot.cooked ? "checkmark.circle.fill" : "circle")
              .font(.title3).foregroundStyle(slot.cooked ? Theme.accent : .white)
              .shadow(color: .black.opacity(0.35), radius: 2).padding(8)
          }
          .buttonStyle(.plain)
          .accessibilityLabel(slot.cooked ? "Mark not cooked" : "Mark cooked")
        }
      }
      .clipShape(RoundedRectangle(cornerRadius: 12))
  }
}

private struct ScheduleMealSheet: View {
  let slot: PlanSlot
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var date = Date()
  @State private var saving = false
  var body: some View {
    NavigationStack {
      VStack(alignment: .leading, spacing: 16) {
        Text(slot.recipeName).font(Theme.mealName)
        DatePicker("Schedule meal", selection: $date, in: earliest..., displayedComponents: .date)
          .datePickerStyle(.graphical)
        if let error = store.error { ErrorBanner(message: error) }
        Button("Save date") {
          saving = true
          Task {
            if await store.schedule(slot, date: date) { dismiss() }
            saving = false
          }
        }.disabled(saving)
        Button("Unschedule") {
          Task {
            await store.unschedule(slot)
            dismiss()
          }
        }
      }.padding().background(Theme.bg)
        .navigationTitle("Schedule meal").navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        .onAppear {
          if let start = planDate(store.plan?.startDate ?? ""), let day = slot.dayIndex {
            date = max(
              earliest, Calendar.current.date(byAdding: .day, value: day, to: start) ?? earliest)
          } else {
            date = earliest
          }
        }
    }
  }
  private var earliest: Date {
    max(Calendar.current.startOfDay(for: Date()), planDate(store.plan?.startDate ?? "") ?? Date())
  }
}

struct SavedPlansView: View {
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var deleting: SavedPlan?
  @State private var plans: [SavedPlan] = []
  @State private var error: String?
  @State private var loading = true
  var body: some View {
    NavigationStack {
      List {
        if let error { ErrorBanner(message: error) }
        if loading { ProgressView() }
        Section("Drafts") {
          if !loading && drafts.isEmpty {
            Text("No drafts yet. Use ⋯ → Save as draft to keep a plan for later.")
              .foregroundStyle(Theme.muted)
          }
          ForEach(drafts, id: \.id) { plan in
            HStack(alignment: .top, spacing: 8) {
              Button {
                Task { if await store.newPlan(source: plan.id) { dismiss() } }
              } label: {
                row(plan)
              }
              .buttonStyle(.plain)
              deleteButton(plan)
            }
          }
        }
        Section("Plan history") {
          if !loading && history.isEmpty {
            Text("No past plans yet. Plans you approve or finish show up here.")
              .foregroundStyle(Theme.muted)
          }
          ForEach(history, id: \.id) { plan in
            HStack(alignment: .top, spacing: 8) {
              NavigationLink {
                List(plan.slots) { slot in
                  NavigationLink {
                    RecipeDetailView(id: slot.recipeId)
                  } label: {
                    VStack(alignment: .leading) {
                      Text(slot.recipeName)
                      Text("\(slot.servings) servings · \(slot.cooked ? "Cooked" : "Not cooked")")
                        .font(Theme.subtitle)
                    }
                  }
                }.navigationTitle(heading(plan))
              } label: {
                row(plan)
              }
              if plan.status != "active" { deleteButton(plan) }
            }
          }
        }
      }.kitchenList().navigationTitle("Saved plans")
        .sheet(item: $deleting) { plan in
          RemovalConfirmation(title: "Delete this plan?", message: heading(plan), actionTitle: "Delete plan") {
            do {
              let _: DeletePlanResult = try await API.send("plans/\(plan.id)", method: "DELETE")
              plans.removeAll { $0.id == plan.id }
            } catch { self.error = error.localizedDescription }
          }
        }
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        .task {
          do {
            let box: PlanList = try await API.get("plans")
            plans = box.plans
          } catch { self.error = KitchenAPI.message(error) }
          loading = false
        }
    }
  }

  private var drafts: [SavedPlan] { plans.filter { $0.status == "draft" } }
  private var history: [SavedPlan] {
    plans.filter { $0.status != "draft" && $0.status != "active" || $0.decision != nil }
  }

  /// One plan: its name (or the week it starts), dates, meal count and status, the first
  /// few meals, and when it was saved, so rows that share a week can be told apart.
  private func row(_ plan: SavedPlan) -> some View {
    VStack(alignment: .leading, spacing: 4) {
      Text(heading(plan)).font(Theme.mealName).foregroundStyle(Theme.ink)
      Text(([dateRange(plan), "\(plan.slots.count) \(plan.slots.count == 1 ? "meal" : "meals")"]
        + [statusWord(plan)].compactMap { $0 }).joined(separator: " · "))
        .font(Theme.subtitle)
      if !plan.slots.isEmpty {
        Text(mealsLine(plan)).font(Theme.subtitle).foregroundStyle(Theme.muted).lineLimit(2)
      }
      if let saved = savedLine(plan) {
        Text(saved).font(Theme.subtitle).foregroundStyle(Theme.muted)
      }
    }
    .fixedSize(horizontal: false, vertical: true)
    .frame(maxWidth: .infinity, alignment: .leading)
    .padding(.vertical, 4)
    .contentShape(Rectangle())
  }

  /// A visible delete, so it doesn't depend on discovering swipe.
  private func deleteButton(_ plan: SavedPlan) -> some View {
    Button {
      deleting = plan
    } label: {
      Image(systemName: "trash")
        .foregroundStyle(Theme.accent)
        .frame(minWidth: 44, minHeight: 44)
        .contentShape(Rectangle())
    }
    .buttonStyle(.borderless)
    .accessibilityLabel("Delete \(heading(plan))")
  }

  private func heading(_ plan: SavedPlan) -> String {
    let title = plan.title.trimmingCharacters(in: .whitespaces)
    if !title.isEmpty && title != "This week" { return title }
    guard let start = planDate(plan.startDate) else { return "Plan" }
    return "Week of \(start.formatted(.dateTime.month(.abbreviated).day()))"
  }

  private func dateRange(_ plan: SavedPlan) -> String {
    guard let start = planDate(plan.startDate) else { return plan.startDate }
    let end = Calendar.current.date(byAdding: .day, value: max(plan.days, 1) - 1, to: start) ?? start
    let day = Date.FormatStyle.dateTime.month(.abbreviated).day()
    return "\(start.formatted(day)) – \(end.formatted(day))"
  }

  private func statusWord(_ plan: SavedPlan) -> String? {
    switch plan.decision {
    case "approve": return "Approved"
    case "decline": return "Declined"
    default: break
    }
    switch plan.status {
    case "draft": return nil
    case "active": return "Current plan"
    case "suggested": return "Waiting for review"
    default: return plan.status.capitalized
    }
  }

  private func mealsLine(_ plan: SavedPlan) -> String {
    let names = plan.slots.map(\.recipeName)
    let shown = names.prefix(3).joined(separator: ", ")
    return names.count > 3 ? "\(shown) +\(names.count - 3) more" : shown
  }

  private func savedLine(_ plan: SavedPlan) -> String? {
    guard let raw = plan.createdAt, let date = ISO8601DateFormatter().date(from: raw) else { return nil }
    return "Saved \(date.formatted(.dateTime.month(.abbreviated).day().hour().minute()))"
  }
}

private struct PlanRowWidthKey: PreferenceKey {
  static var defaultValue: CGFloat = 350
  static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
    value = nextValue()
  }
}

func planDate(_ value: String) -> Date? {
  let f = DateFormatter()
  f.locale = Locale(identifier: "en_US_POSIX")
  f.dateFormat = "yyyy-MM-dd"
  return f.date(from: value)
}

func dayTitle(_ start: String, _ index: Int) -> String {
  guard let date = planDate(start),
    let day = Calendar.current.date(byAdding: .day, value: index, to: date)
  else { return "Day \(index + 1)" }
  return day.formatted(.dateTime.weekday(.wide).month(.abbreviated).day())
}

private struct SuggestedPlanReview: View {
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @Environment(\.dynamicTypeSize) private var textSize
  @State private var swapping: PlanSlot?
  @State private var busy = false
  @State private var captionHeights: [Int: CGFloat] = [:]
  @State private var headerHeight: CGFloat = 40
  @State private var actionsHeight: CGFloat = 44
  @State private var improveHeight: CGFloat = 20
  var body: some View {
    NavigationStack {
      GeometryReader { geometry in
        ScrollView {
          VStack(alignment: .leading, spacing: 12) {
            Stepper(value: Binding(get: { store.proposal?.slots.count ?? 4 }, set: { count in run { await store.resizeProposal(count) } }), in: max(1, (store.proposal?.slots.count ?? 0) - (store.proposal?.suggestedRecipeIds?.count ?? 0))...14) {
              Text("\(store.proposal?.slots.count ?? 4) meals").font(Theme.mealName)
            }
            .disabled(store.proposal?.status != "suggested")
            .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { headerHeight = $0 }
            if let error = store.proposalError {
              ErrorBanner(message: error)
              Button("Dismiss error") { store.proposalError = nil }
            }
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), alignment: .top), count: textSize.isAccessibilitySize ? 1 : 2), alignment: .leading, spacing: 12) {
              ForEach(store.proposal?.slots ?? []) { slot in
                VStack(alignment: .leading, spacing: 6) {
                  Color.clear.frame(height: photoHeight(in: geometry.size))
                    .overlay {
                      NavigationLink { RecipeDetailView(id: slot.recipeId) } label: { RecipePhoto(path: slot.photoPath, fill: true) }
                    }.clipShape(RoundedRectangle(cornerRadius: 14))
                    .overlay(alignment: .topTrailing) {
                      if store.proposal?.suggestedRecipeIds?.contains(slot.recipeId) == true {
                        Button { swapping = slot } label: {
                          Image(systemName: "arrow.triangle.2.circlepath")
                            .font(Theme.action).frame(width: 44, height: 44)
                            .background(Theme.surface, in: Circle())
                        }.buttonStyle(.plain).foregroundStyle(Theme.accent)
                          .disabled(store.proposal?.status != "suggested")
                          .accessibilityLabel("Swap meal: \(slot.recipeName)").padding(6)
                      }
                    }
                  VStack(alignment: .leading, spacing: 6) {
                    Text(slot.recipeName).font(Theme.mealName)
                      .fixedSize(horizontal: false, vertical: true)
                      .frame(maxWidth: .infinity, alignment: .leading)
                    if let minutes = slot.cookingMinutes { Text("\(minutes) min").font(Theme.subtitle).foregroundStyle(Theme.muted) }
                    if store.proposal?.suggestedRecipeIds?.contains(slot.recipeId) != true {
                      Text("Your selection").font(Theme.subtitle)
                    }
                  }
                  .onGeometryChange(for: CGFloat.self) { $0.size.height } action: {
                    captionHeights[slot.id] = $0
                  }
                }
              }
            }
            ViewThatFits(in: .horizontal) {
              HStack(spacing: 12) { reviewActions }
              VStack(alignment: .leading, spacing: 12) { reviewActions }
            }
            .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { actionsHeight = $0 }
            NavigationLink { TasteLabView(swipe: true) } label: { Text("Improve suggestions").font(Theme.subtitle) }
              .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { improveHeight = $0 }
          }.padding().disabled(busy)
        }
      }.background(Theme.bg).navigationTitle("Review your suggestions").navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { store.proposalError = nil; dismiss() } } }
        .sheet(item: $swapping) { slot in ProposalSwapPicker(slot: slot) }
        .onDisappear { store.proposalError = nil }
    }.tint(Theme.accent)
  }
  @ViewBuilder private var reviewActions: some View {
    if store.proposal?.status == "suggested" {
      Button("Approve plan") { run { await store.reviewProposal("approve") } }
        .buttonStyle(.borderedProminent).fixedSize(horizontal: true, vertical: false)
      Button("Suggest another") { run { await store.reviewProposal("decline") } }
        .fixedSize(horizontal: true, vertical: false)
        .accessibilityLabel("Decline and suggest another plan")
    } else {
      Button("Try another suggestion") { run { await store.replaceDeclinedProposal() } }
        .fixedSize(horizontal: true, vertical: false)
    }
  }
  private func photoHeight(in size: CGSize) -> CGFloat {
    let width = textSize.isAccessibilitySize ? size.width - 32 : (size.width - 44) / 2
    if let slots = store.proposal?.slots, slots.count == 4, !textSize.isAccessibilitySize {
      let firstRow = max(captionHeights[slots[0].id] ?? 110, captionHeights[slots[1].id] ?? 110)
      let secondRow = max(captionHeights[slots[2].id] ?? 110, captionHeights[slots[3].id] ?? 110)
      // Padding, stack/grid gaps, and the gap between each photo and caption.
      let reserved = headerHeight + actionsHeight + improveHeight + firstRow + secondRow + 92
      return min(width, max(96, (size.height - reserved) / 2))
    }
    return width
  }
  private func run(_ work: @escaping () async -> Void) {
    busy = true
    Task { await work(); busy = false }
  }
}

private struct RemovalConfirmation: View {
  let title: String
  let message: String
  let actionTitle: String
  let action: () async -> Void
  @Environment(\.dismiss) private var dismiss
  @State private var busy = false
  @State private var contentHeight: CGFloat = 280
  @Environment(\.dynamicTypeSize) private var textSize
  var body: some View {
    ScrollView {
      VStack(spacing: 16) {
        Text(title).font(Theme.title).multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
        Text(message).font(Theme.body).foregroundStyle(Theme.muted).multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
        Button(role: .destructive) {
          busy = true
          Task { await action(); dismiss() }
        } label: {
          Text(actionTitle).font(Theme.action).frame(maxWidth: .infinity, minHeight: 44)
        }.buttonStyle(.borderedProminent).tint(.red)
        Button("Cancel") { dismiss() }.font(Theme.action).frame(maxWidth: .infinity, minHeight: 44)
      }.padding(.horizontal, 20).padding(.vertical, 20).frame(maxWidth: .infinity).disabled(busy)
        .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { contentHeight = $0 + 20 }
    }.presentationDetents(textSize.isAccessibilitySize ? [.large] : [.height(contentHeight), .large]).presentationDragIndicator(.visible).presentationBackground(Theme.bg)
  }
}

private struct DeletePlanResult: Decodable { let ok: Bool }

private struct ProposalSwapPicker: View {
  let slot: PlanSlot
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var query = ""
  @State private var options: [SwapOption] = []
  @State private var loading = false
  @State private var saving = false
  @State private var error: String?
  var body: some View {
    NavigationStack {
      List {
        Text("Replace \(slot.recipeName)").font(Theme.subtitle)
        if let error { ErrorBanner(message: error) }
        if loading { ProgressView() }
        if !loading && options.isEmpty { Text("No matching meals. Try another search or loosen Settings → Filters.").font(Theme.body) }
        ForEach(options) { option in
          Button {
            saving = true
            Task {
              await store.swapProposal(slot, recipeId: option.id)
              saving = false
              if store.proposalError == nil { dismiss() }
              else { error = store.proposalError; store.proposalError = nil }
            }
          } label: {
            HStack(alignment: .top, spacing: 12) {
              RecipePhoto(path: option.photoPath, fill: true).frame(width: 70, height: 70).clipped()
              VStack(alignment: .leading, spacing: 6) {
                Text(option.name).font(Theme.mealName).fixedSize(horizontal: false, vertical: true)
                if let minutes = option.cookingMinutes { Text("\(minutes) min").font(Theme.subtitle) }
              }
            }
          }.disabled(saving || loading)
        }
      }.navigationTitle("Choose a replacement").navigationBarTitleDisplayMode(.inline)
        .searchable(text: $query, prompt: "Search meals or ingredients")
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        .task(id: query) {
          loading = true
          defer { loading = false }
          do {
            try await Task.sleep(for: .milliseconds(250))
            guard let plan = store.proposal else { return }
            let result: SwapOptions = try await API.get("plans/\(plan.id)/swap-options/\(slot.id)", query: ["q": query], reportErrors: false)
            try Task.checkCancellation()
            options = result.recipes
            error = nil
          } catch { if !API.isCancellation(error) { self.error = error.localizedDescription } }
        }
    }
  }
}
