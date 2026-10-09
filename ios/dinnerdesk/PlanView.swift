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
  @State private var makingPlan = false
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
              HStack {
                Button(selected.count == plan.slots.count ? "Deselect all" : "Select all") {
                  selected = selected.count == plan.slots.count ? [] : Set(plan.slots.map(\.id))
                }
                .buttonStyle(.plain)
                .contentShape(Rectangle())
                .accessibilityLabel("Select all meals")
                .accessibilityValue(
                  selected.count == plan.slots.count ? "All meals selected" : "Select all meals")
                Spacer()
                Text("\(selected.count) selected").foregroundStyle(Theme.muted)
              }
              HStack {
                Button("Mark cooked") {
                  Task {
                    await store.markCooked(ids: selected)
                    selected = []
                  }
                }
                Spacer()
                Button("Remove", role: .destructive) { removing = true }
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
      .sheet(isPresented: $makingPlan) { NewPlanSheet() }
      .sheet(isPresented: Binding(get: { store.proposal != nil && !makingPlan }, set: { if !$0 { store.proposal = nil } })) {
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

  /// One photo size for every list row. Grows to 200 only when every title fits on two
  /// lines beside that photo. Otherwise the widest 16-character opening in the plan
  /// pulls every photo down together, never above the 160 ideal. At 70 the photo
  /// stops shrinking and the title may show fewer than 16 characters.
  private func calculateGlobalPhotoWidth(for plan: Plan, availableWidth: CGFloat) -> CGFloat {
    let minPhoto: CGFloat = 70
    let ideal: CGFloat = 160
    let maxPhoto: CGFloat = 200
    let gap: CGFloat = 8 + (editing ? 40 : 0)
    let font = mealTitleFont()
    let names = plan.slots.map(\.recipeName)
    guard !names.isEmpty else { return ideal }

    func textTrack(photo: CGFloat) -> CGFloat { availableWidth - gap - photo }

    let roomAtMax = textTrack(photo: maxPhoto)
    if roomAtMax > 0, names.allSatisfy({ fits($0, width: roomAtMax, lines: 2, font: font) }) {
      return maxPhoto
    }

    let floor = names.map { widthForTwoLines(String($0.prefix(16)), font: font) }.max() ?? 0
    return min(ideal, max(minPhoto, availableWidth - gap - floor))
  }

  /// DM Sans Semibold 17, the same face as Theme.mealName, scaled for the current text size.
  private func mealTitleFont() -> UIFont {
    let base = UIFont(name: "DMSans-SemiBold", size: 17) ?? .systemFont(ofSize: 17, weight: .semibold)
    return UIFontMetrics(forTextStyle: .body).scaledFont(for: base)
  }

  private func fits(_ text: String, width: CGFloat, lines: Int, font: UIFont) -> Bool {
    guard width > 1, !text.isEmpty else { return text.isEmpty }
    let rect = (text as NSString).boundingRect(
      with: CGSize(width: width, height: .greatestFiniteMagnitude),
      options: [.usesLineFragmentOrigin, .usesFontLeading],
      attributes: [.font: font],
      context: nil
    )
    return ceil(rect.height) <= font.lineHeight * CGFloat(lines) + 1
  }

  private func widthForTwoLines(_ text: String, font: UIFont) -> CGFloat {
    if text.isEmpty { return 0 }
    let single = ceil((text as NSString).size(withAttributes: [.font: font]).width)
    var low: CGFloat = 0
    var high = max(single, 1)
    for _ in 0..<18 {
      let mid = (low + high) / 2
      if fits(text, width: mid, lines: 2, font: font) { high = mid } else { low = mid }
    }
    return ceil(high)
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
      } else {
        HStack(alignment: .top, spacing: 8) {
          if editing { selectionButton(slot) }
          photo(slot, side: photoWidth)
          VStack(alignment: .leading, spacing: 8) {
            title(slot, plan: plan)
            if editing { editControls(slot, plan: plan) }
          }
        }
      }
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .opacity(slot.cooked ? 0.45 : 1)
  }

  /// Under each meal: rate it so suggestions learn. 👎 = never suggest again.
  private func thumbs(_ slot: PlanSlot) -> some View {
    HStack(spacing: 4) {
      ThumbsControl(rating: slot.rating ?? 0, subject: slot.recipeName) { next in
        Task { await store.rateMeal(slot, next) }
      }
      .padding(.leading, -12)
      if (slot.rating ?? 0) < 0 {
        Text("Won't be suggested again").font(Theme.subtitle).foregroundStyle(Theme.muted)
      } else if (slot.rating ?? 0) > 0 {
        Text("We'll suggest more like this").font(Theme.subtitle).foregroundStyle(Theme.muted)
      }
    }
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

  private func servingsControl(_ slot: PlanSlot) -> some View {
    HStack(spacing: 2) {
      Button {
        Task { await store.setServings(slot, slot.servings - 1) }
      } label: {
        Image(systemName: "minus").frame(width: 28, height: 44).contentShape(Rectangle())
      }
      .disabled(slot.servings <= 1)
      .accessibilityLabel("Decrease servings for \(slot.recipeName)")
      Text("\(slot.servings) servings").font(Theme.count).lineLimit(1)
      Button {
        Task { await store.setServings(slot, slot.servings + 1) }
      } label: {
        Image(systemName: "plus").frame(width: 28, height: 44).contentShape(Rectangle())
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
          .multilineTextAlignment(.leading).lineLimit(2).truncationMode(.tail)
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

private struct NewPlanSheet: View {
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var keepCurrent = false
  @State private var saving = false

  var body: some View {
    NavigationStack {
      VStack(alignment: .leading, spacing: 16) {
        Text("Choose your own meals or start with four suggestions.")
        if !(store.plan?.slots.isEmpty ?? true) { Toggle("Keep my selected meals", isOn: $keepCurrent) }
        Button("Suggest 4 meals") { go(meals: 4) }.buttonStyle(.borderedProminent).disabled(saving)
        Button("I'll choose the meals") { go(meals: nil) }.disabled(saving)
        if let error = store.error { ErrorBanner(message: error) }
      }
      .padding()
      .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
      .background(Theme.bg)
      .navigationTitle("New meal plan")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
    }
    .tint(Theme.accent)
  }

  private func go(meals: Int?) {
    saving = true
    Task {
      if await store.newPlan(meals: meals, keepCurrent: keepCurrent) { dismiss() }
      saving = false
    }
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
          if !loading && plans.filter({ $0.status == "draft" }).isEmpty {
            Text("No saved drafts yet").foregroundStyle(Theme.muted)
          }
          ForEach(plans.filter { $0.status == "draft" }, id: \.id) { plan in
            Button("\(plan.title) · \(plan.slots.count) meals") {
              Task { if await store.newPlan(source: plan.id) { dismiss() } }
            }
            .swipeActions { Button("Delete", role: .destructive) { deleting = plan } }
          }
        }
        Section("Plan history") {
          ForEach(plans.filter { $0.status != "draft" && $0.status != "active" || $0.decision != nil }, id: \.id) { plan in
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
              }.navigationTitle(plan.title)
            } label: {
              VStack(alignment: .leading, spacing: 5) {
                Text(plan.title).font(Theme.mealName)
                Text("\(planDate(plan.startDate)?.formatted(date: .abbreviated, time: .omitted) ?? plan.startDate) · \(plan.slots.count) meals").font(Theme.subtitle)
                Text("\(plan.decision == "approve" ? "Approved" : plan.decision == "decline" ? "Declined" : plan.status.capitalized) · \(plan.changes?.count ?? 0) swaps").font(Theme.subtitle).foregroundStyle(Theme.muted)
              }.fixedSize(horizontal: false, vertical: true).padding(.vertical, 4)
            }
            .swipeActions { if plan.status != "active" { Button("Delete", role: .destructive) { deleting = plan } } }
          }
        }
      }.kitchenList().navigationTitle("Saved plans")
        .sheet(item: $deleting) { plan in
          RemovalConfirmation(title: "Delete this plan?", message: plan.title, actionTitle: "Delete plan") {
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
  var body: some View {
    NavigationStack {
      GeometryReader { geometry in
        ScrollView {
          VStack(alignment: .leading, spacing: 12) {
            Stepper(value: Binding(get: { store.proposal?.slots.count ?? 4 }, set: { count in run { await store.resizeProposal(count) } }), in: max(1, (store.proposal?.slots.count ?? 0) - (store.proposal?.suggestedRecipeIds?.count ?? 0))...14) {
              Text("\(store.proposal?.slots.count ?? 4) meals").font(Theme.mealName)
            }
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
                          .accessibilityLabel("Swap meal: \(slot.recipeName)").padding(6)
                      }
                    }
                  Text(slot.recipeName).font(Theme.mealName)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                  if let minutes = slot.cookingMinutes { Text("\(minutes) min").font(Theme.subtitle).foregroundStyle(Theme.muted) }
                  if store.proposal?.suggestedRecipeIds?.contains(slot.recipeId) != true {
                    Text("Your selection").font(Theme.subtitle)
                  }
                }
              }
            }
            ViewThatFits(in: .horizontal) {
              HStack(spacing: 12) { reviewActions }
              VStack(alignment: .leading, spacing: 12) { reviewActions }
            }
            NavigationLink { TasteLabView(swipe: true) } label: { Text("Improve suggestions").font(Theme.subtitle) }
          }.padding().disabled(busy)
        }
      }.background(Theme.bg).navigationTitle("Review your suggestions").navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { store.proposalError = nil; dismiss() } } }
        .sheet(item: $swapping) { slot in ProposalSwapPicker(slot: slot) }
        .onDisappear { store.proposalError = nil }
    }.tint(Theme.accent)
  }
  @ViewBuilder private var reviewActions: some View {
    Button("Approve plan") { run { await store.reviewProposal("approve") } }
      .buttonStyle(.borderedProminent).fixedSize(horizontal: true, vertical: false)
    Button("Suggest another") { run { await store.reviewProposal("decline") } }
      .fixedSize(horizontal: true, vertical: false)
      .accessibilityLabel("Decline and suggest another plan")
  }
  private func photoHeight(in size: CGSize) -> CGFloat {
    let width = textSize.isAccessibilitySize ? size.width - 32 : (size.width - 44) / 2
    if store.proposal?.slots.count == 4 && textSize <= .large && size.height >= 650 {
      return min(width, max(100, (size.height - 420) / 2))
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
