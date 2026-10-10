import SwiftUI

/// Everything that isn't Plan, Recipes or Grocery: one list of grey-icon rows in a shared settings layout.
struct MoreView: View {
  @EnvironmentObject private var session: Session

  var body: some View {
    NavigationStack {
      List {
        Section {
          NavigationLink {
            PrepView()
          } label: {
            KitchenIconRow(title: "Weekend prep", systemImage: "list.bullet.clipboard")
          }
          NavigationLink {
            KitchenView()
          } label: {
            KitchenIconRow(title: "My kitchen and Groceries", systemImage: "refrigerator")
          }
          NavigationLink {
            TasteLabView()
          } label: {
            KitchenIconRow(title: "Taste Lab", systemImage: "hand.draw")
          }
          NavigationLink {
            // Move to My kitchen and Groceries
            HiddenRecipesView() 
          } label: {
            KitchenIconRow(title: "Hidden recipes", systemImage: "eye.slash")
          }
        }
        .kitchenRows()

        Section {
          Button {
            session.showTour = true
          } label: {
            KitchenIconRow(title: "Quick start tour", systemImage: "arrow.counterclockwise")
          }
          .accessibilityHint("Replays the first-run tour")
          NavigationLink {
            SettingsView()
          } label: {
            KitchenIconRow(title: "Settings", systemImage: "gearshape")
          }
          if let url = URL(string: "https://dinnerdesk.computerscience.build") {
            Link(destination: url) {
              KitchenIconRow(title: "\(Copy.appName) on the web", systemImage: "safari")
            }
          }
          Link(destination: URL(string: "https://x.com/DinnerDesk")!) {
            KitchenIconRow(
              title: "Twitter", systemImage: "bubble.left.and.bubble.right", value: "@DinnerDesk")
          }
        }
        .kitchenRows()
      }
      .kitchenList()
      .tint(Theme.accent)
      .navigationTitle("More")
      .largeNavigationTitle()
    }
  }
}

/// Recipes hidden from browse. Tap Unhide to bring one back.
struct HiddenRecipesView: View {
  @EnvironmentObject private var store: Store
  @State private var recipes: [RecipeSummary] = []
  @State private var loaded = false

  var body: some View {
    List {
      Text(
        "Recipes you hid from Recipes. They stay out of browse and search until you unhide them."
      )
      .font(Theme.subtitle)
      .foregroundStyle(Theme.muted)
      .kitchenBareRow()
      if loaded && recipes.isEmpty {
        Text("Nothing hidden").foregroundStyle(Theme.muted).kitchenBareRow()
      }
      ForEach(recipes) { recipe in
        HStack(spacing: 12) {
          NavigationLink {
            RecipeDetailView(id: recipe.id)
          } label: {
            HStack(spacing: 12) {
              RecipePhoto(path: recipe.photoPath)
                .frame(width: 56, height: 56)
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
              Text(recipe.name)
                .font(Theme.rowTitle)
                .foregroundStyle(Theme.ink)
                .lineLimit(2)
            }
          }
          Button("Unhide") {
            Task { await unhide(recipe) }
          }
          .font(Theme.action)
          .foregroundStyle(Theme.ink)
          .padding(.horizontal, 12)
          .padding(.vertical, 6)
          .background(Capsule().fill(Theme.chip))
          .buttonStyle(.borderless)
        }
        .kitchenRows()
      }
    }
    .kitchenList()
    .navigationTitle("Hidden recipes")
    .navigationBarTitleDisplayMode(.inline)
    .task { await load() }
    .refreshable { await load() }
  }

  private func load() async {
    recipes = await store.loadHiddenRecipes()
    loaded = true
  }

  private func unhide(_ recipe: RecipeSummary) async {
    recipes.removeAll { $0.id == recipe.id }
    _ = await store.setHidden(id: recipe.id, on: false)
  }
}
