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
            ThemeIconRow(title: "Weekend prep", systemImage: "list.bullet.clipboard")
          }
          NavigationLink {
            KitchenView()
          } label: {
            ThemeIconRow(title: "My kitchen and Groceries", systemImage: "refrigerator")
          }
          NavigationLink {
            TasteLabView()
          } label: {
            ThemeIconRow(title: "Taste Lab", systemImage: "hand.draw")
          }
          NavigationLink {
            // Move to My kitchen and Groceries
            HiddenRecipesView() 
          } label: {
            ThemeIconRow(title: "Hidden recipes", systemImage: "eye.slash")
          }
          Button {
            session.showTour = true
          } label: {
            ThemeIconRow(title: "Quick start tour", systemImage: "arrow.counterclockwise")
          }
          .accessibilityHint("Replays the first-run tour")
        }
        .themeRows()
      }
      .themeList()
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
      .themeBareRow()
      if loaded && recipes.isEmpty {
        Text("Nothing hidden").foregroundStyle(Theme.muted).themeBareRow()
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
        .themeRows()
      }
    }
    .themeList()
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
