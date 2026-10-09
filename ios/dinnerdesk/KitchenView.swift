import SwiftUI

/// My kitchen: portions, pantry, and the grocery settings. Push it from a NavigationStack (More tab).
struct KitchenView: View {
  @State private var portions = 4
  @State private var savedPortions: Int?
  @State private var error: String?

  var body: some View {
    List {
      if let error {
        ErrorBanner(message: error).kitchenBareRow()
      }

      KitchenSection("Cooking") {
        // The − / + drops below the label when "Family portions" can't stay on one line.
        ViewThatFits(in: .horizontal) {
          HStack(spacing: 14) {
            KitchenIconRow(title: "Family portions", systemImage: "person.2", value: "\(portions)")
            portionsStepper
          }
          VStack(alignment: .leading, spacing: 8) {
            KitchenIconRow(title: "Family portions", systemImage: "person.2", value: "\(portions)")
            portionsStepper.padding(.leading, 40)
          }
        }
        NavigationLink {
          PantryView()
        } label: {
          KitchenIconRow(title: "Pantry", systemImage: "shippingbox")
        }
      }
      .kitchenRows()

      KitchenSection("Grocery list") {
        NavigationLink {
          AlwaysCheckedView()
        } label: {
          KitchenIconRow(title: "Always checked off", systemImage: "checkmark.circle")
        }
        NavigationLink {
          SubstitutionsView()
        } label: {
          KitchenIconRow(title: "Substitutions", systemImage: "arrow.left.arrow.right")
        }
        NavigationLink {
          GroceryStoreView()
        } label: {
          KitchenIconRow(title: "Stores & aisles", systemImage: "storefront")
        }
      }
      .kitchenRows()
    }
    .kitchenList()
    .navigationTitle("My kitchen")
    .largeNavigationTitle()
    .task { await load() }
    .refreshable { await load() }
    .onChange(of: portions) { _, value in
      guard let saved = savedPortions, saved != value else { return }
      Task { await savePortions(value) }
    }
  }

  private var portionsStepper: some View {
    Stepper("Family portions", value: $portions, in: 1...50)
      .labelsHidden()
      .fixedSize()
      .accessibilityValue("\(portions)")
  }

  private func load() async {
    do {
      let prefs = try await KitchenAPI.prefs()
      let n = (prefs["family_portions"] as? Int).flatMap { $0 >= 1 ? $0 : nil } ?? portions
      savedPortions = n
      portions = n
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func savePortions(_ value: Int) async {
    do {
      try await KitchenAPI.savePrefs(["family_portions": value])
      savedPortions = value
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}

/// "Buy this instead of that": a recipe's item is swapped on the grocery list.
struct SubstitutionsView: View {
  @EnvironmentObject private var store: Store
  @State private var items: [KitchenOverride] = []
  @State private var from = ""
  @State private var to = ""
  @State private var error: String?

  private var canAdd: Bool {
    !from.trimmingCharacters(in: .whitespaces).isEmpty
      && !to.trimmingCharacters(in: .whitespaces).isEmpty
  }

  var body: some View {
    List {
      if let error {
        ErrorBanner(message: error).kitchenBareRow()
      }
      Text(Copy.text("kitchen.substitutions"))
        .font(Theme.subtitle)
        .foregroundStyle(Theme.muted)
        .accessibilityIdentifier("tip.kitchen.substitutions")
        .kitchenBareRow()

      KitchenSection("Your substitutions") {
        if items.isEmpty {
          Text("None yet").foregroundStyle(Theme.muted)
        }
        ForEach(items) { item in
          ViewThatFits(in: .horizontal) {
            HStack(spacing: 10) {
              Text(item.fromName).foregroundStyle(Theme.muted).fixedSize()
              Image(systemName: "arrow.right").foregroundStyle(Theme.muted)
              Text(item.toName).font(Theme.mealName).foregroundStyle(Theme.ink).fixedSize()
            }
            VStack(alignment: .leading, spacing: 8) {
              Text(item.fromName).foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
              Label(item.toName, systemImage: "arrow.right")
                .font(Theme.mealName).foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            }
          }
          .accessibilityElement(children: .combine)
          .accessibilityLabel("\(item.fromName) becomes \(item.toName)")
        }
        .onDelete { offsets in
          let doomed = offsets.map { items[$0] }
          Task {
            for item in doomed { await remove(item) }
          }
        }
      }
      .kitchenRows()

      KitchenSection("Add one") {
        TextField("Recipe says (e.g. vegetable oil)", text: $from)
          .textInputAutocapitalization(.never)
        TextField("Buy instead (e.g. olive oil)", text: $to)
          .textInputAutocapitalization(.never)
        KitchenAddRow(title: "Add substitution") { Task { await add() } }
          .disabled(!canAdd)
          .opacity(canAdd ? 1 : 0.45)
      }
      .kitchenRows()
    }
    .kitchenList()
    .navigationTitle("Substitutions")
    .navigationBarTitleDisplayMode(.inline)
    .toolbar { EditButton() }
    .task { await load() }
    .refreshable { await load() }
  }

  private func load() async {
    do {
      items = try await KitchenAPI.overrides()
      error = nil
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func add() async {
    do {
      items = try await KitchenAPI.addOverride(
        from: from.trimmingCharacters(in: .whitespaces),
        to: to.trimmingCharacters(in: .whitespaces)
      )
      from = ""
      to = ""
      error = nil
      await store.loadGrocery()
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func remove(_ item: KitchenOverride) async {
    items.removeAll { $0.id == item.id }
    do {
      items = try await KitchenAPI.deleteOverride(item.id)
      await store.loadGrocery()
    } catch {
      self.error = KitchenAPI.message(error)
      await load()
    }
  }
}
