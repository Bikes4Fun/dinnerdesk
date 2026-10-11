import SwiftUI
import UIKit

struct GroceryView: View {
  @EnvironmentObject private var store: Store
  @Environment(\.selectTab) private var selectTab
  @State private var storeFilter = ""
  @State private var adding = false
  @State private var menu = false
  @State private var editingStores = false
  @State private var openItem: Int?
  @State private var menuStatus: String?
  @State private var sharing = false

  private var allGroceryComplete: Bool {
    !store.grocery.isEmpty && store.grocery.allSatisfy { $0.checked || $0.neverShop }
  }

  var body: some View {
    NavigationStack {
      VStack(spacing: 0) {
        HStack {
            Text("Grocery")
                .font(Theme.bigTitle)

            Spacer()

            Button {
                menu = true
            } label: {
                Image(systemName: "ellipsis")
                    .fontWeight(.semibold)
            }
            .tint(Theme.accent)
            .accessibilityLabel("Grocery List Settings")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Theme.bg)

        List {
          if let err = store.error {
            ErrorBanner(message: err).themeBareRow()
          }
          if !store.stores.isEmpty {
            Section {
              ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                  chip("All", on: storeFilter.isEmpty) { storeFilter = "" }
                  ForEach(store.stores) { shop in
                    chip(shop.name, on: storeFilter == shop.id) {
                      storeFilter = storeFilter == shop.id ? "" : shop.id
                    }
                  }
                }
                .padding(.vertical, 4)
              }
              .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
              .themeBareRow()
            }
          }
          if store.grocery.isEmpty {
            EmptyState(
              title: "List is empty",
              message: "Choose meals to build your grocery list.",
              systemImage: "cart"
            )
            .listRowInsets(EdgeInsets())
            .listRowSeparator(.hidden)
            .listRowBackground(Theme.bg)
            if store.plan?.slots.isEmpty != false {
              Button("Create meal plan") {
                selectTab(.plan)
                Task { await store.openSuggestions() }
              }.font(Theme.action).themeBareRow()
            }
          } else {
            if aisleBlocks.isEmpty {
              Text(allDoneMessage)
                .font(Theme.subtitle)
                .foregroundStyle(Theme.muted)
                .padding(.vertical, 24)
                .frame(maxWidth: .infinity)
                .multilineTextAlignment(.center)
                .themeBareRow()
            }
            ForEach(aisleBlocks, id: \.id) { block in
              ThemeSection(block.name) {
                ForEach(block.rows) { line in
                  GroceryRow(line: line) {
                    openItem = line.id
                  }
                }
              }
              .themeRows()
            }
            if completedCount > 0 {
              // Same switch as ⋯ → Show completed items, one tap from the list.
              Button {
                store.hideChecked.toggle()
                Task { await store.persistGroceryPrefs() }
              } label: {
                Label(
                  store.hideChecked ? "Show \(completedCount) completed" : "Hide completed",
                  systemImage: store.hideChecked ? "eye" : "eye.slash"
                )
                .font(Theme.action)
                .foregroundStyle(Theme.accent)
                .frame(maxWidth: .infinity, minHeight: 44)
              }
              .buttonStyle(.borderless)
              .themeBareRow()
            }
            // Room so the + button never covers the last row.
            Color.clear.frame(height: 72).themeBareRow()
          }
        }

        // .navigationTitle("Grocery")
        // .largeNavigationTitle()
        // .toolbar {
        //   ToolbarItem(placement: .topBarTrailing) {
        //     Button {
        //       menu = true
        //     } label: {
        //       Image(systemName: "ellipsis")
        //         .fontWeight(.semibold)
        //     }
        //     .tint(Theme.accent)
        //     .accessibilityLabel("Grocery menu")
        //   }
        // }

        .themeList()

        .overlay(alignment: .bottomTrailing) {
          Button {
            adding = true
          } label: {
            Image(systemName: "plus")
              .font(.system(size: 24, weight: .semibold))
              .foregroundStyle(.white)
              .frame(width: 60, height: 60)
              .background(Circle().fill(Theme.accent))
              .shadow(color: Theme.ink.opacity(0.2), radius: 10, y: 4)
          }
          .padding(.trailing, 20)
          .padding(.bottom, 16)
          .accessibilityLabel("Add item")
        }
        .menuSheet(isPresented: $menu) {
          [
            MenuSheetItem(
              title: "Show completed items",
              systemImage: "eye", dismissOnSelection: false, isOn: !store.hideChecked
            ) {
              store.hideChecked.toggle()
              Task { await store.persistGroceryPrefs() }
            },
            MenuSheetItem(
              title: allGroceryComplete ? "Uncheck all" : "Complete all",
              systemImage: allGroceryComplete ? "arrow.uturn.backward.circle" : "checkmark.circle",
              dismissOnSelection: false, status: menuStatus
            ) {
              let uncheck = allGroceryComplete
              Task {
                if uncheck { await store.uncheckAllGrocery() }
                else { await store.markAllGroceryComplete() }
                if store.error == nil { menuStatus = uncheck ? "Unchecked" : "Completed" }
              }
            },
            MenuSheetItem(
              title: "Show meals under each item",
              systemImage: "fork.knife", dismissOnSelection: false, isOn: store.showMeals
            ) {
              store.showMeals.toggle()
              Task { await store.persistGroceryPrefs() }
            },
            MenuSheetItem(
              title: "Show aisle numbers",
              systemImage: "number", dismissOnSelection: false, isOn: store.showAisleNums
            ) {
              store.showAisleNums.toggle()
              Task { await store.persistGroceryPrefs() }
            },
            MenuSheetItem(title: "Share list", systemImage: "square.and.arrow.up") {
              sharing = true
            },
            MenuSheetItem(title: "Edit stores & aisles", systemImage: "storefront") {
              editingStores = true
            },
          ]
        }
        // Messages, Mail, Notes…: the system share sheet covers sharing and email.
        .sheet(isPresented: $sharing) {
          ShareSheet(items: [shareText])
            .presentationDetents([.medium, .large])
        }
        .navigationDestination(isPresented: $editingStores) {
          GroceryStoreView()
        }
        .sheet(isPresented: $adding) {
          AddGrocerySheet(storeId: storeFilter.isEmpty ? nil : storeFilter)
        }
        .navigationDestination(item: $openItem) { id in
          GroceryItemView(lineId: id)
        }
        .refreshable { await store.loadGrocery() }
        .task { await store.loadGrocery() }
      }
    }
  }

  /// Lines for the selected store (or every store), before hiding completed ones.
  private var storeLines: [GroceryLine] {
    storeFilter.isEmpty ? store.grocery : store.grocery.filter { $0.store == storeFilter }
  }

  private var visible: [GroceryLine] {
    storeLines.filter { line in
      !(store.hideChecked && (line.checked || line.neverShop))
    }
  }

  /// What's left to buy, grouped by aisle in walk-the-store order, for the selected store.
  private var shareText: String {
    let left = storeLines.filter { !$0.checked && !$0.neverShop && !$0.fromPantry }
    let storeName = store.stores.first { $0.id == storeFilter }?.name
    let title = storeName.map { "Grocery list — \($0)" } ?? "Grocery list"
    guard !left.isEmpty else { return "\(title)\n\nNothing left to buy." }
    var blocks = store.aisles.map { aisle in (aisle.name, left.filter { $0.aisle == aisle.id }) }
    blocks.append(("Other", left.filter { line in !store.aisles.contains { $0.id == line.aisle } }))
    let body = blocks.filter { !$0.1.isEmpty }.map { name, rows in
      let items = rows.map { line in
        "• " + [line.quantity, line.name].filter { !$0.isEmpty }.joined(separator: " ")
      }
      return ([name.uppercased()] + items).joined(separator: "\n")
    }
    return "\(title)\n\n" + body.joined(separator: "\n\n")
  }

  private var completedCount: Int {
    storeLines.filter { $0.checked || $0.neverShop }.count
  }

  private var allDoneMessage: String {
    let name = store.stores.first { $0.id == storeFilter }?.name
    if storeLines.isEmpty {
      return name.map { "Nothing on the list for \($0)." } ?? "Nothing on the list."
    }
    return name.map { "Everything for \($0) is checked off." } ?? "Everything is checked off."
  }

  /// Sections follow the household's walk-the-store order (My kitchen › Aisle order).
  private var aisleBlocks: [(id: String, name: String, rows: [GroceryLine])] {
    let known = store.aisles
    var blocks = known.map { aisle in
      (
        id: aisle.id,
        name: store.showAisleNums ? store.aisleTitle(aisle.id) : aisle.name,
        rows: visible.filter { $0.aisle == aisle.id }
      )
    }
    let extra = visible.filter { line in !known.contains(where: { $0.id == line.aisle }) }
    if !extra.isEmpty {
      blocks.append((id: "extra", name: "Other", rows: extra))
    }
    return blocks.filter { !$0.rows.isEmpty }
  }

  private func chip(_ title: String, on: Bool, action: @escaping () -> Void) -> some View {
    Button(title, action: action)
      .font(Theme.chipLabel)
      .padding(.horizontal, 12)
      .padding(.vertical, 7)
      .background(on ? Theme.accent : Theme.chip)
      .foregroundStyle(on ? Color.white : Theme.ink)
      .clipShape(Capsule())
      .buttonStyle(.plain)
  }
}

struct GroceryRow: View {
  @EnvironmentObject private var store: Store
  @Environment(\.dynamicTypeSize) private var typeSize
  let line: GroceryLine
  let onOpen: () -> Void

  var body: some View {
    HStack(spacing: 0) {
      Button {
        Task { await store.toggleGrocery(line) }
      } label: {
        Image(systemName: line.checked ? "checkmark.circle.fill" : "circle")
          .font(.system(size: 24))
          .foregroundStyle(line.checked ? Theme.accent : Theme.muted)
          .frame(width: 60)
          .frame(minHeight: 56, maxHeight: .infinity)
          .contentShape(Rectangle())
      }
      .buttonStyle(.plain)
      .accessibilityLabel(line.checked ? "Uncheck \(line.name)" : "Check off \(line.name)")

      Button(action: onOpen) {
        HStack(spacing: 10) {
          if line.ingredientPhotoPath != nil {
            RecipePhoto(path: line.ingredientPhotoPath)
          }
          VStack(alignment: .leading, spacing: 2) {
            Text(line.name)
              .font(Theme.body)
              .strikethrough(line.checked)
              .foregroundStyle(line.checked ? Theme.muted : Theme.ink)
            // Large text: the amount goes under the name so the name keeps the width.
            if typeSize.isAccessibilitySize, !line.quantity.isEmpty {
              Text(line.quantity).font(Theme.count).foregroundStyle(Theme.muted)
            }
            if !note.isEmpty {
              Text(note).font(Theme.subtitle).foregroundStyle(Theme.muted)
            }
            if line.fromPantry && !line.neverShop {
              pantryTip
            }
          }
          .frame(maxWidth: .infinity, alignment: .leading)
          if !typeSize.isAccessibilitySize, !line.quantity.isEmpty {
            Text(line.quantity)
              .font(Theme.count)
              .foregroundStyle(Theme.muted)
          }
        }
        .padding(.trailing, 16)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, minHeight: 56, alignment: .leading)
        .contentShape(Rectangle())
      }
      .buttonStyle(.plain)
    }
    .listRowInsets(EdgeInsets())
    .listRowBackground(Theme.bg)
  }

  private var note: String {
    var parts: [String] = []
    if store.showMeals && !line.usedBy.isEmpty {
      parts.append(line.usedBy.map(shortMealName).filter { !$0.isEmpty }.joined(separator: " · "))
    }
    return parts.joined(separator: " · ")
  }

  /// The pantry note is a tip (purple ★ on the aubergine tint), not plain grey text.
  private var pantryTip: some View {
    HStack(alignment: .firstTextBaseline, spacing: 4) {
      Image(systemName: "star.fill").font(Theme.subtitle)
        .foregroundStyle(Color(hex: 0x7A3B73))
        .accessibilityHidden(true)
      Text(Copy.text("grocery.pantry")).font(Theme.subtitle).foregroundStyle(Theme.ink)
    }
    .padding(.horizontal, 8)
    .padding(.vertical, 3)
    .background(Theme.aubergineTint, in: Capsule())
    .accessibilityElement(children: .combine)
    .accessibilityIdentifier("tip.grocery.pantry")
  }
}

struct GroceryItemView: View {
  let lineId: Int
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var editing = false
  @State private var subName = ""
  @State private var suggestions: [String] = []
  @State private var suggestTask: Task<Void, Never>?
  /// After a substitution the list is rebuilt and the item comes back as a new line.
  /// This follows it so the screen stays open for more changes.
  @State private var followId: Int?

  private var line: GroceryLine? {
    let id = followId ?? lineId
    return store.grocery.first(where: { $0.id == id })
  }

  private var substituteLabel: some View {
    Text("Substitute")
      .font(Theme.mealName)
      .foregroundStyle(Theme.ink)
      .lineLimit(1)
      .fixedSize(horizontal: true, vertical: false)
  }

  private var substituteField: some View {
    TextField("Try another item", text: $subName)
      .textFieldStyle(.roundedBorder)
      .frame(minWidth: 140)
      .onChange(of: subName) { _, q in
        suggestTask?.cancel()
        suggestTask = Task {
          try? await Task.sleep(for: .milliseconds(220))
          guard !Task.isCancelled else { return }
          suggestions = await store.suggestGroceryItems(q)
        }
      }
  }

  var body: some View {
    Group {
      if let line {
        GeometryReader { geometry in
          ScrollView {
            VStack(alignment: .leading, spacing: 12) {
              VStack(alignment: .leading, spacing: 6) {
                Text(itemTitle(line))
                  .font(Theme.title)
                  .foregroundStyle(Theme.ink)
                  .lineLimit(2)
                Text(store.aisleName(line.aisle).uppercased())
                  .font(Theme.subtitle)
                  .foregroundStyle(Theme.muted)
              }

              RecipePhoto(path: line.ingredientPhotoPath, large: true, hideUnavailable: true)
                .accessibilityLabel("Photo of \(line.name)")
              ViewThatFits(in: .horizontal) {
                HStack(spacing: 12) {
                  substituteLabel
                  substituteField
                }
                VStack(alignment: .leading, spacing: 8) {
                  substituteLabel
                  substituteField
                }
              }
              .frame(width: geometry.size.width - 32, alignment: .leading)
              if !suggestions.isEmpty {
                ForEach(suggestions, id: \.self) { name in
                  Button(name) {
                    subName = name
                    suggestions = []
                  }
                  .foregroundStyle(Theme.ink)
                }
              }
              if !subName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                Button("Use this instead") {
                  let target = subName.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
                  let current = line.id
                  Task {
                    await store.addSubstitute(from: line.name, to: subName)
                    if store.grocery.contains(where: { $0.id == current }) { return }
                    if let next = store.grocery.first(where: { $0.name.lowercased() == target }) {
                      followId = next.id
                      subName = ""
                      suggestions = []
                    } else {
                      dismiss()
                    }
                  }
                }
                .foregroundStyle(Theme.accent)
              }

              Text("You'll use this in…")
                .font(Theme.subtitle)
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
              if !line.usedIn.isEmpty {
                ForEach(line.usedIn) { meal in
                  if let rid = meal.recipeId {
                    NavigationLink {
                      RecipeDetailView(id: rid)
                    } label: {
                      mealLabel(meal)
                    }
                  } else {
                    mealLabel(meal)
                  }
                }
              } else if !line.usedBy.isEmpty {
                ForEach(line.usedBy, id: \.self) { name in
                  Text(name).foregroundStyle(Theme.ink)
                }
              } else {
                Text("Added by you").foregroundStyle(Theme.muted)
              }

              VStack(spacing: 0) {
                pickerRow("Store", value: store.storeName(line)) {
                  ForEach(store.stores) { shop in
                    Button(shop.name) {
                      Task { await store.setGroceryStore(line, shop.id) }
                    }
                  }
                }
                hairline
                pickerRow("Aisle", value: store.aisleName(line.aisle)) {
                  ForEach(store.aisles) { aisle in
                    Button(aisle.name) {
                      Task { await store.setGroceryAisle(line, aisle.id) }
                    }
                  }
                }

                hairline
                Toggle(isOn: pantryBinding(line)) {
                  Text("In my pantry").font(Theme.rowTitle).foregroundStyle(Theme.ink)
                }
                .tint(Theme.accent)
                .frame(minHeight: 44)
                hairline
                Toggle(isOn: neverBinding(line)) {
                  Text("Always check off").font(Theme.rowTitle).foregroundStyle(Theme.ink)
                }
                .tint(Theme.accent)
                .frame(minHeight: 44)
              }
            }
            .padding(16)
            .frame(width: geometry.size.width, alignment: .leading)
          }
        }
        .background(Theme.bg)
        .toolbar {
          ToolbarItem(placement: .topBarTrailing) {
            Button("Edit") { editing = true }
          }
        }
        .sheet(isPresented: $editing) {
          EditGrocerySheet(line: line)
        }
      } else {
        ContentUnavailableView("Item gone", systemImage: "cart")
      }
    }
  }

  private var hairline: some View {
    Rectangle().fill(Theme.line).frame(height: 1)
  }

  private func mealLabel(_ meal: UsedMeal) -> some View {
    HStack(spacing: 12) {
      RecipePhoto(path: meal.photoPath)
      VStack(alignment: .leading, spacing: 4) {
        Text(meal.name)
          .font(Theme.mealName)
          .foregroundStyle(Theme.ink)
          .multilineTextAlignment(.leading)
          .lineLimit(2)
          .truncationMode(.tail)
        if !meal.quantity.isEmpty {
          Text(meal.quantity).font(Theme.count).foregroundStyle(Theme.muted)
        }
      }
      .frame(maxWidth: .infinity, alignment: .leading)
    }
  }

  private func pickerRow<Content: View>(
    _ label: String, value: String, @ViewBuilder content: () -> Content
  ) -> some View {
    HStack {
      Text(label).font(Theme.rowTitle).foregroundStyle(Theme.ink)
      Spacer()
      Menu {
        content()
      } label: {
        HStack(spacing: 4) {
          Text(value)
          Image(systemName: "chevron.up.chevron.down")
            .font(Theme.subtitle)
        }
        .foregroundStyle(Theme.muted)
      }
    }
    .frame(minHeight: 44)
  }

  private func pantryBinding(_ line: GroceryLine) -> Binding<Bool> {
    Binding(
      get: { line.fromPantry },
      set: { next in
        Task { await store.setPantryFlags(name: line.name, have: next, neverShop: line.neverShop) }
      }
    )
  }

  private func neverBinding(_ line: GroceryLine) -> Binding<Bool> {
    Binding(
      get: { line.neverShop },
      set: { next in
        Task { await store.setPantryFlags(name: line.name, have: line.fromPantry, neverShop: next) }
      }
    )
  }

  private func itemTitle(_ line: GroceryLine) -> String {
    [line.quantity, line.name]
      .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
      .filter { !$0.isEmpty }
      .joined(separator: " ")
  }
}

private struct EditGrocerySheet: View {
  let line: GroceryLine
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var qty: String
  @State private var itemName: String

  init(line: GroceryLine) {
    self.line = line
    _qty = State(initialValue: line.quantity)
    _itemName = State(initialValue: line.name)
  }

  var body: some View {
    NavigationStack {
      Form {
        Group {
          TextField("Amount", text: $qty)
          TextField("Item name", text: $itemName)
        }
        .listRowBackground(Theme.surface)
      }
      .themeForm()
      .navigationTitle("Edit item")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button("Cancel") { dismiss() }
        }
        ToolbarItem(placement: .confirmationAction) {
          Button("Save") {
            Task {
              let name = itemName.trimmingCharacters(in: .whitespacesAndNewlines)
              if !name.isEmpty && name != line.name {
                await store.patchGrocery(line, ["custom_text": name])
              }
              let trimmed = qty.trimmingCharacters(in: .whitespacesAndNewlines)
              if trimmed != line.quantity {
                await store.setGroceryQuantity(line, trimmed)
              }
              if store.error == nil { dismiss() }
            }
          }
          .disabled(itemName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
      }
    }
    .presentationDetents([.medium])
  }
}

private struct AddGrocerySheet: View {
  var storeId: String?
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @Environment(\.dynamicTypeSize) private var typeSize
  @State private var newName = ""
  @State private var newQty = ""
  /// The single best match for what's typed. One line keeps Quantity and Add on screen.
  @State private var suggestion: String?
  @State private var suggestTask: Task<Void, Never>?
  @State private var saving = false

  private var canAdd: Bool {
    !saving && !newName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
  }

  var body: some View {
    NavigationStack {
      Form {
        Group {
          TextField("Item", text: $newName)
            .onChange(of: newName) { _, q in
              suggestTask?.cancel()
              suggestTask = Task {
                try? await Task.sleep(for: .milliseconds(220))
                guard !Task.isCancelled else { return }
                let best = await store.suggestGroceryItems(q).first
                let typed = q.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
                suggestion = best?.lowercased() == typed ? nil : best
              }
            }
          if let suggestion {
            Button {
              newName = suggestion
              self.suggestion = nil
            } label: {
              HStack(alignment: .firstTextBaseline, spacing: 8) {
                Image(systemName: "sparkle.magnifyingglass").foregroundStyle(Theme.muted)
                Text(suggestion).foregroundStyle(Theme.accent).multilineTextAlignment(.leading)
              }
            }
            .accessibilityLabel("Use suggestion: \(suggestion)")
          }
          TextField("Quantity (optional)", text: $newQty)
          Button("Add to list") { add() }
            .disabled(!canAdd)
        }
        .listRowBackground(Theme.surface)
      }
      .themeForm()
      .navigationTitle("Add item")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button("Cancel") { dismiss() }
        }
        // Always reachable, however large the text gets.
        ToolbarItem(placement: .confirmationAction) {
          Button("Add") { add() }.disabled(!canAdd)
        }
      }
    }
    .presentationDetents(typeSize.isAccessibilitySize ? [.large] : [.medium, .large])
  }

  private func add() {
    saving = true
    Task {
      await store.addGroceryLine(name: newName, quantity: newQty, store: storeId)
      saving = false
      if store.error == nil { dismiss() }
    }
  }
}

private func shortMealName(_ name: String) -> String {
  let raw = name.trimmingCharacters(in: .whitespacesAndNewlines)
  guard !raw.isEmpty else { return "" }
  let head = raw.split(separator: ",", maxSplits: 1)[0]
    .trimmingCharacters(in: .whitespacesAndNewlines)
  if let range = head.range(of: " with ", options: .caseInsensitive) {
    return String(head[..<range.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
  }
  return head
}


/// The system share sheet, for plain text.
private struct ShareSheet: UIViewControllerRepresentable {
  let items: [Any]

  func makeUIViewController(context: Context) -> UIActivityViewController {
    UIActivityViewController(activityItems: items, applicationActivities: nil)
  }

  func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
