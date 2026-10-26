import SwiftUI

/// What you already have. Optional: start every pantry item checked off on the grocery list.
struct PantryView: View {
  @EnvironmentObject private var store: Store
  @State private var items: [KitchenPantryItem] = []
  @State private var stores = KitchenDefaults.stores
  @State private var aisles = KitchenDefaults.aisles
  @State private var autoCheck = false
  @State private var adding = false
  @State private var error: String?

  var body: some View {
    List {
      if let error {
        ErrorBanner(message: error).themeBareRow()
      }
      ThemeAddRow(title: "Add item") { adding = true }.themeRows()
      
      Toggle(isOn: Binding(get: { autoCheck }, set: { on in Task { await setAutoCheck(on) } })) {
        Text("Always check off pantry items")
          .font(Theme.mealName)
          .foregroundStyle(Theme.ink)
      }
      .tint(Theme.accent)
      .padding(.vertical, 6)
      .themeRows()

      ThemeSection("In your pantry · \(items.count)") {
        if items.isEmpty {
          Text("Nothing here yet.").foregroundStyle(Theme.muted)
        }
        ForEach(items, id: \.name) { item in
          NavigationLink {
            PantryItemEditor(item: item, onChanged: { await load() })
          } label: {
            PantryRow(item: item, place: placeText(item), checksOff: autoCheck)
          }
        }
        .onDelete { offsets in
          let doomed = offsets.map { items[$0] }
          Task {
            for item in doomed { await remove(item) }
          }
        }

      }
      .themeRows()
    }
    .themeList()
    .navigationTitle("Pantry")
    .navigationBarTitleDisplayMode(.inline)
    .sheet(isPresented: $adding) {
      KitchenItemPicker(title: "Add to pantry") { names in
        await add(names)
      }
    }
    .task { await load() }
    .refreshable { await load() }
  }

  private func placeText(_ item: KitchenPantryItem) -> String? {
    guard item.store != nil || item.aisle != nil else { return nil }
    let store = stores.first { $0.id == item.store }?.name ?? "Any store"
    let aisle = aisles.first { $0.id == (item.aisle ?? "other") }?.name ?? "Other"
    return "\(store), \(aisle)"
  }

  private func load() async {
    do {
      async let pantryBox = KitchenAPI.pantry()
      let prefs = try await KitchenAPI.prefs()
      items = try await pantryBox.filter(\.have)
      stores = KitchenDefaults.stores(from: prefs)
      aisles = KitchenDefaults.aisles(from: prefs)
      autoCheck = prefs["pantry_auto_check"] as? Bool ?? false
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func setAutoCheck(_ on: Bool) async {
    autoCheck = on
    do {
      try await KitchenAPI.savePrefs(["pantry_auto_check": on])
      await store.loadGrocery()
    } catch {
      autoCheck = !on
      self.error = KitchenAPI.message(error)
    }
  }

  private func add(_ names: [String]) async {
    do {
      for name in names {
        try await KitchenAPI.upsertPantry(name: name, have: true, neverShop: false)
      }
      await load()
      await store.loadGrocery()
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func remove(_ item: KitchenPantryItem) async {
    items.removeAll { $0.name == item.name }
    guard let id = item.id else { return }
    do {
      try await KitchenAPI.patchPantry(id: id, have: false, neverShop: false)
      await store.loadGrocery()
    } catch {
      self.error = KitchenAPI.message(error)
      await load()
    }
  }
}

private struct PantryRow: View {
  let item: KitchenPantryItem
  let place: String?
  let checksOff: Bool

  var body: some View {
    HStack(spacing: 12) {
      VStack(alignment: .leading, spacing: 2) {
        Text(item.name)
          .font(Theme.mealName)
          .foregroundStyle(Theme.ink)
          .lineLimit(2)
        if !item.quantity.isEmpty {
          Text(item.quantity).font(Theme.subtitle).foregroundStyle(Theme.muted)
        }
        if let place {
          Text(place)
            .font(Theme.subtitle)
            .foregroundStyle(Theme.muted)
            .lineLimit(1)
        }
      }
      Spacer(minLength: 8)
      if item.neverShop || checksOff {
        Image(systemName: "checkmark.circle.fill")
          .foregroundStyle(Theme.muted.opacity(0.6))
          .accessibilityLabel("Checked off on the grocery list")
      }
    }
    .padding(.vertical, 4)
  }
}

/// Items you always have (salt, oil). They stay on the grocery list, already checked off.
struct AlwaysCheckedView: View {
  @EnvironmentObject private var store: Store
  @State private var items: [KitchenPantryItem] = []
  @State private var adding = false
  @State private var error: String?

  var body: some View {
    List {
      if let error {
        ErrorBanner(message: error).themeBareRow()
      }
      StarTip(id: "kitchen.always-checked")
        .themeBareRow()
      ThemeSection("Always checked off · \(items.count)") {
        if items.isEmpty {
          VStack(alignment: .leading, spacing: 10) {
            Text("Examples — add the items you always keep on hand")
            Text("Salt")
            Text("Olive oil")
            Text("Black pepper")
          }.foregroundStyle(Theme.muted).opacity(0.5)
        }
        ForEach(items, id: \.name) { item in
          Text(item.name)
            .font(Theme.mealName)
            .foregroundStyle(Theme.ink)
        }
        .onDelete { offsets in
          let doomed = offsets.map { items[$0] }
          Task {
            for item in doomed { await remove(item) }
          }
        }
        ThemeAddRow(title: "Add item") { adding = true }
      }
      .themeRows()
    }
    .themeList()
    .navigationTitle("Always checked off")
    .navigationBarTitleDisplayMode(.inline)
    .sheet(isPresented: $adding) {
      KitchenItemPicker(title: "Always check off") { names in
        await add(names)
      }
    }
    .task { await load() }
    .refreshable { await load() }
  }

  private func load() async {
    do {
      items = try await KitchenAPI.pantry().filter(\.neverShop)
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func add(_ names: [String]) async {
    do {
      for name in names {
        try await KitchenAPI.upsertPantry(name: name, have: true, neverShop: true)
      }
      await load()
      await store.loadGrocery()
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func remove(_ item: KitchenPantryItem) async {
    items.removeAll { $0.name == item.name }
    guard let id = item.id else { return }
    do {
      try await KitchenAPI.patchPantry(id: id, neverShop: false)
      await store.loadGrocery()
    } catch {
      self.error = KitchenAPI.message(error)
      await load()
    }
  }
}

/// Search the grocery catalog and pick several items (or keep what you typed), then Add saves
/// them all at once; Cancel drops the picks. Same search-and-chips field as Filters' allergies
/// and dislikes. The field is focused on open, Return adds the first match, Escape cancels.
struct KitchenItemPicker: View {
  let title: String
  let onPick: @MainActor ([String]) async -> Void

  @Environment(\.dismiss) private var dismiss
  @State private var picked: [String] = []
  @State private var saving = false

  init(title: String, onPick: @escaping @MainActor ([String]) async -> Void) {
    self.title = title
    self.onPick = onPick
  }

  var body: some View {
    NavigationStack {
      ScrollView {
        VStack(alignment: .leading, spacing: 16) {
          if !picked.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
              Text("Selected · \(picked.count)").font(Theme.subtitle).foregroundStyle(Theme.muted)
              KitchenFlow(spacing: 6) {
                ForEach(picked, id: \.self) { name in
                  FilterChip(label: "\(name) ✕", on: true) { picked.removeAll { $0 == name } }
                    .accessibilityLabel("Remove \(name)")
                }
              }
            }
          }
          ItemSearchField(
            label: "Items", placeholder: "Type an item, like garlic or rice", autofocus: true,
            selected: $picked, search: { try await KitchenAPI.searchItems($0) })
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
      }
      .background(Theme.bg)
      .navigationTitle(title)
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
        }
        ToolbarItem(placement: .confirmationAction) {
          Button(picked.isEmpty ? "Add" : "Add \(picked.count)") { save() }
            .disabled(picked.isEmpty || saving)
        }
      }
      .tint(Theme.accent)
      // A stray swipe shouldn't throw away the picks.
      .interactiveDismissDisabled(!picked.isEmpty)
    }
  }

  private func save() {
    guard !saving else { return }
    saving = true
    Task { @MainActor in
      await onPick(picked)
      dismiss()
    }
  }
}

private struct PantryItemEditor: View {
  let item: KitchenPantryItem
  let onChanged: () async -> Void
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var quantity = ""
  @State private var have = true
  @State private var neverShop = false
  @State private var placement: ItemPlacement?
  @FocusState private var amountFocused: Bool
  @State private var ready = false
  @State private var error: String?

  var body: some View {
    Form {
      Group {
        if let error { ErrorBanner(message: error) }
        Toggle("Have this item", isOn: $have)
          .onChange(of: have) { _, next in if ready { Task { await save(have: next) } } }
        Toggle("Always check off", isOn: $neverShop)
          .onChange(of: neverShop) { _, next in if ready { Task { await save(neverShop: next) } } }
        TextField("Amount (optional)", text: $quantity)
          .focused($amountFocused)
          .onChange(of: amountFocused) { _, focused in
            if ready && !focused { Task { await save(quantity: quantity) } }
          }
          .onSubmit { Task { await save(quantity: quantity) } }
        if let placement {
          Picker(
            "Store",
            selection: Binding(
              get: { placement.store }, set: { value in Task { await setPlace(storeId: value) } })
          ) {
            Text("Not set").tag("")
            ForEach(store.stores) { Text($0.name).tag($0.id) }
          }
          Picker(
            "Aisle",
            selection: Binding(
              get: { placement.aisle }, set: { value in Task { await setPlace(aisleId: value) } })
          ) {
            ForEach(store.aisles) { Text($0.name).tag($0.id) }
          }
        }
        Button("Delete item", role: .destructive) {
          Task {
            do {
              guard let id = item.id else { preconditionFailure("Pantry item has no id") }
              let _: Ok = try await API.send("pantry/items/\(id)", method: "DELETE")
              ready = false
              await onChanged()
              await store.loadGrocery()
              dismiss()
            } catch { self.error = KitchenAPI.message(error) }
          }
        }
      }
      .listRowBackground(Theme.surface)
    }
    .themeForm()
    .navigationTitle(item.name)
    .task {
      quantity = item.quantity
      have = item.have
      neverShop = item.neverShop
      do {
        let items = try await KitchenAPI.placements()
        placement = items.first { $0.name.lowercased() == item.name.lowercased() }
        ready = true
      } catch { self.error = KitchenAPI.message(error) }
    }
    .onDisappear {
      if ready {
        Task {
          if quantity != item.quantity { await save(quantity: quantity) }
          await onChanged()
        }
      }
    }
  }

  private func save(have: Bool? = nil, neverShop: Bool? = nil, quantity: String? = nil) async {
    guard let id = item.id else { preconditionFailure("Pantry item has no id") }
    do {
      try await KitchenAPI.patchPantry(id: id, have: have, neverShop: neverShop, quantity: quantity)
      await store.loadGrocery()
    } catch { self.error = KitchenAPI.message(error) }
  }

  private func setPlace(storeId: String? = nil, aisleId: String? = nil) async {
    guard let current = placement else { return }
    do {
      try await KitchenAPI.setPlacement(current, store: storeId, aisle: aisleId)
      if let storeId { placement?.store = storeId }
      if let aisleId { placement?.aisle = aisleId }
      await store.loadGrocery()
    } catch { self.error = KitchenAPI.message(error) }
  }
}
