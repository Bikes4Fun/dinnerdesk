import SwiftUI

/// Your stores, the aisle order, and which store/aisle each item belongs to.
struct GroceryStoreView: View {
  @EnvironmentObject private var store: Store

  enum Tab: String, CaseIterable, Identifiable {
    case unset = "Not set"
    case all = "All items"
    var id: String { rawValue }
  }

  @State private var stores = KitchenDefaults.stores
  @State private var aisles = KitchenDefaults.aisles
  @State private var items: [ItemPlacement] = []
  @State private var tab: Tab = .unset
  @State private var query = ""
  @State private var newStore = ""
  @State private var addingStore = false
  @State private var doomedStore: KitchenStore?
  @State private var error: String?

  private var unset: [ItemPlacement] { items.filter { $0.store.isEmpty } }

  private var shown: [ItemPlacement] {
    let base = tab == .unset ? unset : items
    let q = query.trimmingCharacters(in: .whitespaces).lowercased()
    return q.isEmpty ? base : base.filter { $0.name.lowercased().contains(q) }
  }

  private struct AisleGroup: Identifiable {
    let aisle: KitchenAisle
    let rows: [ItemPlacement]
    var id: String { aisle.id }
  }

  private var groups: [AisleGroup] {
    let known = Set(aisles.map(\.id))
    var out = aisles.map { aisle in
      AisleGroup(aisle: aisle, rows: shown.filter { $0.aisle == aisle.id })
    }
    let extra = shown.filter { !known.contains($0.aisle) }
    if !extra.isEmpty {
      out.append(
        AisleGroup(aisle: KitchenAisle(id: "_extra", name: "Other", number: ""), rows: extra))
    }
    return out.filter { !$0.rows.isEmpty }
  }

  private func count(_ store: KitchenStore) -> Int {
    items.filter { $0.store == store.id }.count
  }

  var body: some View {
    List {
      if let error {
        ErrorBanner(message: error).kitchenBareRow()
      }

      KitchenSection("Your stores") {
        KitchenFlow(spacing: 8) {
          ForEach(stores) { store in
            // A Menu per chip: a context menu inside a List row lifts the whole row and
            // only ever offered the first store.
            Menu {
              Button("Remove \(store.name)", role: .destructive) { doomedStore = store }
            } label: {
              KitchenChip(text: store.name, count: count(store), selected: false)
            }
            .buttonStyle(.borderless)
            .accessibilityHint("Opens an option to remove this store")
          }
          Button {
            addingStore = true
          } label: {
            KitchenChip(text: "+ Add store", count: nil, selected: false, dashed: true)
          }
          .buttonStyle(.plain)
        }
        .padding(.vertical, 8)
        .kitchenBareRow()

        Text(Copy.text("kitchen.store-chips"))
          .font(Theme.subtitle).foregroundStyle(Theme.muted)
          .accessibilityIdentifier("tip.kitchen.store-chips")
          .listRowBackground(Theme.bg)
          .listRowSeparator(.hidden)

        NavigationLink {
          AisleOrderView()
        } label: {
          KitchenIconRow(
            title: "Aisle order", systemImage: "list.number", value: "\(aisles.count) aisles")
        }
        .kitchenRows()
      }

      KitchenSection("Store & aisle for each item") {
        Picker("Which items", selection: $tab) {
          Text("Not set · \(unset.count)").tag(Tab.unset)
          Text("All items · \(items.count)").tag(Tab.all)
        }
        .pickerStyle(.segmented)
        .kitchenBareRow()
      } footer: {
        Text(Copy.text("kitchen.store-per-item"))
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .accessibilityIdentifier("tip.kitchen.store-per-item")
      }

      if groups.isEmpty {
        Section {
          Text(
            tab == .unset
              ? "Every item has a store."
              : "Items show up here once they're on a grocery list or in your pantry."
          )
          .foregroundStyle(Theme.muted)
          .kitchenBareRow()
        }
      }

      ForEach(groups) { group in
        KitchenSection(group.aisle.name) {
          ForEach(group.rows) { item in
            PlacementRow(item: item, stores: stores, aisles: aisles) { store, aisle in
              Task { await place(item, store: store, aisle: aisle) }
            }
          }
        }
        .kitchenRows()
      }
    }
    .kitchenList()
    .navigationTitle("Stores & aisles")
    .navigationBarTitleDisplayMode(.inline)
    .searchable(text: $query, prompt: "Search items")
    .task { await load() }
    .refreshable { await load() }
    .alert("Add a store", isPresented: $addingStore) {
      TextField("Store name", text: $newStore)
      Button("Add") { Task { await addStore() } }
      Button("Cancel", role: .cancel) { newStore = "" }
    }
    .alert(
      "Remove \(doomedStore?.name ?? "store")?",
      isPresented: Binding(get: { doomedStore != nil }, set: { if !$0 { doomedStore = nil } })
    ) {
      Button("Cancel", role: .cancel) { doomedStore = nil }
      Button("Remove", role: .destructive) {
        if let store = doomedStore {
          Task { await saveStores(stores.filter { $0.id != store.id }) }
        }
        doomedStore = nil
      }
    } message: {
      Text("You can add it back anytime.")
    }
  }

  private func load() async {
    do {
      async let itemsBox = KitchenAPI.placements()
      let prefs = try await KitchenAPI.prefs()
      stores = KitchenDefaults.stores(from: prefs)
      aisles = KitchenDefaults.aisles(from: prefs)
      items = try await itemsBox
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func addStore() async {
    let name = newStore.trimmingCharacters(in: .whitespaces)
    newStore = ""
    guard !name.isEmpty else { return }
    let id: String
    do { id = try KitchenDefaults.slug(name) } catch {
      self.error = KitchenAPI.message(error)
      return
    }
    guard !stores.contains(where: { $0.id == id }) else { return }
    await saveStores(stores + [KitchenStore(id: id, name: name)])
  }

  private func saveStores(_ next: [KitchenStore]) async {
    let before = stores
    stores = next
    do {
      try await KitchenAPI.saveGroceryPrefs(["stores": KitchenDefaults.json(next)])
      let valid = Set(next.map(\.id))
      for i in items.indices where !valid.contains(items[i].store) { items[i].store = "" }
      await store.loadGrocery()
    } catch {
      stores = before
      self.error = KitchenAPI.message(error)
    }
  }

  private func place(_ item: ItemPlacement, store: String?, aisle: String?) async {
    guard let index = items.firstIndex(where: { $0.id == item.id }) else { return }
    let before = items[index]
    if let store { items[index].store = store }
    if let aisle { items[index].aisle = aisle }
    do {
      try await KitchenAPI.setPlacement(before, store: store, aisle: aisle)
      await self.store.loadGrocery()
    } catch {
      if let i = items.firstIndex(where: { $0.id == item.id }) { items[i] = before }
      self.error = KitchenAPI.message(error)
    }
  }
}

/// One item on one line: name, then a store menu and an aisle menu.
private struct PlacementRow: View {
  let item: ItemPlacement
  let stores: [KitchenStore]
  let aisles: [KitchenAisle]
  let onChange: (_ store: String?, _ aisle: String?) -> Void

  private var storeName: String {
    stores.first { $0.id == item.store }?.name ?? "Not set"
  }

  private var aisleName: String {
    aisles.first { $0.id == item.aisle }?.name ?? "Other"
  }

  var body: some View {
    ViewThatFits(in: .horizontal) {
      HStack(spacing: 8) {
        name
        Spacer(minLength: 4)
        pickers
      }
      VStack(alignment: .leading, spacing: 6) {
        name
        pickers
      }
    }
  }

  private var name: some View {
    Text(item.name).font(Theme.mealName).foregroundStyle(Theme.ink).lineLimit(2)
  }

  private var pickers: some View {
    HStack(spacing: 6) {
      Menu {
        Button("Not set") { onChange("", nil) }
        ForEach(stores) { store in
          Button(store.name) { onChange(store.id, nil) }
        }
      } label: {
        PickerChip(text: storeName, unset: item.store.isEmpty)
      }
      .accessibilityLabel("Store for \(item.name): \(storeName)")
      Menu {
        ForEach(aisles) { aisle in
          Button(aisle.name) { onChange(nil, aisle.id) }
        }
      } label: {
        PickerChip(text: aisleName, unset: false)
      }
      .accessibilityLabel("Aisle for \(item.name): \(aisleName)")
    }
  }
}

private struct PickerChip: View {
  let text: String
  let unset: Bool

  var body: some View {
    HStack(spacing: 4) {
      Text(text).lineLimit(1)
      Image(systemName: "chevron.down").font(Theme.subtitle)
    }
    .font(Theme.chipLabel)
    .foregroundStyle(unset ? Theme.muted : Theme.ink)
    .padding(.horizontal, 12)
    .frame(minHeight: 34)
    .background(Capsule().fill(unset ? Color.clear : Theme.chip))
    .overlay(
      Capsule().strokeBorder(
        unset ? Theme.line : Color.clear, style: StrokeStyle(lineWidth: 1, dash: [4, 3]))
    )
  }
}

/// Put aisles in the order you walk the store; give them numbers.
struct AisleOrderView: View {
  @EnvironmentObject private var store: Store
  @State private var aisles = KitchenDefaults.aisles
  @State private var counts: [String: Int] = [:]
  @State private var newAisle = ""
  @State private var addingAisle = false
  @State private var error: String?

  var body: some View {
    List {
      if let error {
        ErrorBanner(message: error).kitchenBareRow()
      }
      KitchenSection("Walk-the-store order") {
        ForEach($aisles) { $aisle in
          HStack(spacing: 12) {
            TextField("#", text: $aisle.number)
              .keyboardType(.numberPad)
              .multilineTextAlignment(.center)
              .font(Theme.count.monospacedDigit())
              .frame(width: 44, height: 32)
              .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(Theme.chip))
              .accessibilityLabel("Aisle number for \(aisle.name)")
              .onSubmit { Task { await save(aisles) } }
            Text(aisle.name)
              .font(Theme.mealName)
              .foregroundStyle(Theme.ink)
              .lineLimit(2)
            Spacer(minLength: 4)
            Text(countText(aisle.id))
              .font(Theme.subtitle)
              .foregroundStyle(Theme.muted)
              .monospacedDigit()
          }
        }
        .onMove { from, to in
          var next = aisles
          next.move(fromOffsets: from, toOffset: to)
          Task { await save(next) }
        }
        KitchenAddRow(title: "Add aisle") { addingAisle = true }
      } footer: {
        Text(Copy.text("kitchen.aisle-order"))
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .accessibilityIdentifier("tip.kitchen.aisle-order")
      }
      .kitchenRows()
    }
    .kitchenList()
    .environment(\.editMode, .constant(.active))
    .navigationTitle("Aisle order")
    .navigationBarTitleDisplayMode(.inline)
    .task { await load() }
    .onDisappear { Task { await save(aisles) } }
    .alert("Add an aisle", isPresented: $addingAisle) {
      TextField("Aisle name", text: $newAisle)
      Button("Add") { Task { await addAisle() } }
      Button("Cancel", role: .cancel) { newAisle = "" }
    }
  }

  private func countText(_ id: String) -> String {
    let n = counts[id] ?? 0
    return n == 1 ? "1 item" : "\(n) items"
  }

  private func load() async {
    do {
      aisles = KitchenDefaults.aisles(from: try await KitchenAPI.prefs())
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
    do {
      let items = try await KitchenAPI.placements()
      counts = Dictionary(grouping: items, by: \.aisle).mapValues(\.count)
    } catch { self.error = KitchenAPI.message(error) }
  }

  private func addAisle() async {
    let name = newAisle.trimmingCharacters(in: .whitespaces)
    newAisle = ""
    guard !name.isEmpty else { return }
    let id: String
    do { id = try KitchenDefaults.slug(name) } catch {
      self.error = KitchenAPI.message(error)
      return
    }
    guard !aisles.contains(where: { $0.id == id }) else { return }
    var next = aisles.filter { $0.id != "other" }
    next.append(KitchenAisle(id: id, name: name, number: ""))
    next += aisles.filter { $0.id == "other" }
    await save(next)
  }

  private func save(_ next: [KitchenAisle]) async {
    aisles = next
    do {
      try await KitchenAPI.saveGroceryPrefs(["aisles": KitchenDefaults.json(next)])
      await store.loadGrocery()
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}
