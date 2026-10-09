import SwiftUI

private enum RecipeListKind: String, CaseIterable, Identifiable {
  case suggestions, fav, tryLater, popular, mine, simple, sauces, hidden, all
  var id: String { rawValue }

  var title: String {
    switch self {
    case .suggestions: "Suggestions"
    case .fav: "Your Favorites"
    case .tryLater: "To try"
    case .popular: "Most Popular"
    case .mine: "Your Recipes"
    case .simple: "Super simple"
    case .sauces: "Sauces & dressings"
    case .hidden: "Hidden"
    case .all: "All recipes"
    }
  }
}

private enum RecipeSearchFilter: String, CaseIterable, Identifiable {
  case fav, tryLater, popular, quick, pantry, hidden
  var id: String { rawValue }

  var label: String {
    switch self {
    case .fav: "Your favorites"
    case .tryLater: "To try"
    case .popular: "Popular"
    case .quick: "Quick"
    case .pantry: "Uses pantry"
    case .hidden: "Hidden"
    }
  }
}

/// Two columns of recipe cards; one at accessibility text sizes so names don't break mid-word.
private func recipeColumns(_ typeSize: DynamicTypeSize) -> [GridItem] {
  let column = GridItem(.flexible(), spacing: 12, alignment: .top)
  return typeSize.isAccessibilitySize ? [column] : [column, column]
}

struct RecipesView: View {
  @EnvironmentObject private var store: Store
  @Environment(\.dynamicTypeSize) private var typeSize
  @State private var suggestedIds: [Int] = []
  @State private var query = ""
  @State private var searchOpen = false
  @State private var searchTask: Task<Void, Never>?
  @State private var list: RecipeListKind?
  @State private var filters: Set<RecipeSearchFilter> = []
  /// Pantry items you have, for the "Uses pantry" filter. Loaded when that chip is tapped.
  @State private var pantryHave: Set<String> = []
  @State private var hiddenRecipes: [RecipeSummary] = []

  private var searching: Bool {
    !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !filters.isEmpty
  }

  var body: some View {
    NavigationStack {
      VStack(spacing: 0) {
        HStack {
          Text("Recipes").font(Theme.bigTitle)
          Spacer()
          Button {
            searchOpen.toggle()
            if !searchOpen {
              query = ""
              searchTask?.cancel()
              Task { await store.searchRecipes("") }
            }
          } label: {
            Image(systemName: "magnifyingglass")
              .font(.title3)
          }
          .accessibilityLabel("Search Recipes")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Theme.bg)
        if searchOpen {
          TextField("Search recipes or ingredients", text: $query)
            .textFieldStyle(.plain)
            .font(Theme.body)
            .padding(12)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))
            .padding(.horizontal, 16)
            .padding(.bottom, 12)
            .onChange(of: query) { _, q in
              searchTask?.cancel()
              searchTask = Task {
                try? await Task.sleep(for: .milliseconds(280))
                guard !Task.isCancelled else { return }
                if filters.contains(.hidden) {
                  hiddenRecipes = await store.loadHiddenRecipes()
                } else {
                  await store.searchRecipes(q)
                }
              }
            }
        }

      ScrollView {
        LazyVStack(alignment: .leading, spacing: 24) {
          if let err = store.error {
            ErrorBanner(message: err)
              .padding(.horizontal, 16)
          }
          filterChips
          if searching {
            recipeGrid(searchRows, empty: query.isEmpty ? "No recipes" : "No matches")
              .padding(.horizontal, 16)
          } else {
            browseHome
          }
        }
        .padding(.vertical)
      }
      .background(Theme.bg)
      // .navigationTitle("Recipes")
      // .largeNavigationTitle()
      // .searchable(
      //   text: $query,
      //   placement: .toolbar,
      //   prompt: "Search recipes or ingredients"
      //   )
      // .onChange(of: query) { _, q in
      //   searchTask?.cancel()
      //   searchTask = Task {
      //     try? await Task.sleep(for: .milliseconds(280))
      //     guard !Task.isCancelled else { return }
      //     if filters.contains(.hidden) {
      //       hiddenRecipes = await store.loadHiddenRecipes()
      //     } else {
      //       await store.searchRecipes(q)
      //     }
      //   }
      // }
      .navigationDestination(item: $list) { kind in
        RecipeGridPage(title: kind.title, recipes: rows(for: kind))
      }
      .refreshable {
        await store.searchRecipes(query)
        hiddenRecipes = await store.loadHiddenRecipes()
        if let suggestions: RecipeSuggestions = try? await API.get("suggestions/recipes", reportErrors: false) { suggestedIds = suggestions.recipeIds }
      }
      .task {
        hiddenRecipes = await store.loadHiddenRecipes()
      }
      }
    }
  }

  @ViewBuilder
  private var browseHome: some View {
    if !suggestedIds.isEmpty { browseSection("Suggestions", rows: rows(for: .suggestions), seeAll: .suggestions) }
    browseSection(
      "Your favorites", rows: favorites, seeAll: .fav, empty: "Heart a recipe to keep it here.")
    if !toTry.isEmpty {
      browseSection("To try", rows: toTry, seeAll: .tryLater)
    }
    if !popular.isEmpty {
      browseSection("Most popular", rows: popular, seeAll: .popular)
    }
    if !mine.isEmpty {
      browseSection("Your recipes", rows: mine, seeAll: .mine)
    }
    if !simple.isEmpty {
      browseSection("Super simple", rows: simple, seeAll: .simple)
    }
    if !sauces.isEmpty {
      browseSection("Sauces & dressings", rows: sauces, seeAll: .sauces)
    }
    browseSection("All recipes", rows: rows(for: .all), seeAll: .all, empty: "No recipes")
  }

  private func browseSection(
    _ title: String, rows: [RecipeSummary], seeAll: RecipeListKind, empty: String? = nil
  ) -> some View {
    VStack(alignment: .leading, spacing: 12) {
      Group {
        if rows.isEmpty {
          Text(title)
            .font(Theme.title)
            .foregroundStyle(Theme.ink)
        } else {
          // "See all" sits beside the title when both fit on one line. At large text the
          // title itself becomes the link, with a chevron, so the title never gets cut off.
          ViewThatFits(in: .horizontal) {
            HStack {
              Text(title)
                .font(Theme.title)
                .foregroundStyle(Theme.ink)
                .lineLimit(1)
              Spacer()
              Button("See all") { list = seeAll }
                .font(Theme.action)
                .foregroundStyle(Theme.accent)
            }
            Button { list = seeAll } label: {
              HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(title)
                  .font(Theme.title)
                  .foregroundStyle(Theme.ink)
                  .multilineTextAlignment(.leading)
                Image(systemName: "chevron.right")
                  .font(Theme.action)
                  .foregroundStyle(Theme.accent)
              }
              .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("\(title), see all")
          }
        }
      }
      .padding(.horizontal, 16)
      if rows.isEmpty, let empty {
        Text(empty)
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .padding(.horizontal, 16)
      } else if !rows.isEmpty {
        ScrollView(.horizontal, showsIndicators: false) {
          LazyHStack(spacing: 12) {
            ForEach(browseOrder(rows)) { recipe in
              RecipeTile(recipe: recipe)
                .frame(width: typeSize.isAccessibilitySize ? 280 : 160)
            }
          }
          .padding(.horizontal, 16)
        }
      }
    }
  }

  private var filterChips: some View {
    ScrollView(.horizontal, showsIndicators: false) {
      HStack(spacing: 8) {
        chip("All", on: filters.isEmpty) { filters = [] }
        ForEach(RecipeSearchFilter.allCases) { filter in
          chip(filter.label, on: filters.contains(filter)) {
            if filters.contains(filter) {
              filters.remove(filter)
            } else {
              filters.insert(filter)
            }
            if filter == .hidden {
              Task { hiddenRecipes = await store.loadHiddenRecipes() }
            }
            if filter == .pantry {
              Task {
                if let items = try? await KitchenAPI.pantry() { pantryHave = PantryMatch.have(items) }
              }
            }
          }
        }
      }
      .padding(.horizontal, 16)
    }
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

  @ViewBuilder
  private func recipeGrid(_ rows: [RecipeSummary], empty: String?) -> some View {
    if rows.isEmpty {
      if let empty {
        Text(empty)
          .foregroundStyle(Theme.muted)
          .frame(maxWidth: .infinity, alignment: .leading)
      }
    } else {
      LazyVGrid(columns: recipeColumns(typeSize), spacing: 16) {
        ForEach(rows) { recipe in
          RecipeTile(recipe: recipe)
        }
      }
    }
  }

  private func browseOrder(_ rows: [RecipeSummary]) -> [RecipeSummary] {
    let seed = UInt64(Calendar.current.ordinality(of: .day, in: .era, for: Date())!)
    func score(_ recipe: RecipeSummary) -> UInt64 {
      var value = UInt64(recipe.id) ^ seed
      value = (value ^ (value >> 16)) &* 0x45d9f3b
      return value ^ (value >> 16)
    }
    return rows.sorted { score($0) < score($1) }
  }

  private var favorites: [RecipeSummary] { store.recipes.filter(\.favorited) }
  private var toTry: [RecipeSummary] { store.recipes.filter(\.toTry) }
  private var meals: [RecipeSummary] { store.recipes.filter(\.isMeal) }
  private var popular: [RecipeSummary] { meals.filter { $0.tags.contains("popular") } }
  private var mine: [RecipeSummary] { store.recipes.filter { !$0.catalog } }
  private var simple: [RecipeSummary] { meals.filter { ($0.cookingMinutes ?? 99) <= 20 } }
  private var sauces: [RecipeSummary] { store.recipes.filter(\.isExtra) }

  private func rows(for list: RecipeListKind) -> [RecipeSummary] {
    switch list {
    case .suggestions: suggestedIds.compactMap { id in store.recipes.first { $0.id == id } }
    case .fav: favorites
    case .tryLater: toTry
    case .popular: popular
    case .mine: mine
    case .simple: simple
    case .sauces: sauces
    case .hidden: hiddenRecipes
    case .all:
      meals.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }
  }

  private var searchRows: [RecipeSummary] {
    var rows = filters.contains(.hidden) ? hiddenRecipes : store.recipes
    let q = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    if filters.contains(.hidden), !q.isEmpty {
      rows = rows.filter { recipe in
        recipe.name.lowercased().contains(q)
          || recipe.ingredients.contains { $0.lowercased().contains(q) }
      }
    }
    if filters.contains(.fav) { rows = rows.filter(\.favorited) }
    if filters.contains(.tryLater) { rows = rows.filter(\.toTry) }
    if filters.contains(.popular) { rows = rows.filter { $0.tags.contains("popular") } }
    if filters.contains(.quick) { rows = rows.filter { ($0.cookingMinutes ?? 99) <= 30 } }
    if filters.contains(.pantry) {
      rows = rows.filter { PantryMatch.uses($0.ingredients, have: pantryHave) }
    }
    return rows
  }
}

private struct RecipeGridPage: View {
  let title: String
  let recipes: [RecipeSummary]
  @Environment(\.dynamicTypeSize) private var typeSize

  var body: some View {
    ScrollView {
      if recipes.isEmpty {
        Text("No recipes")
          .foregroundStyle(Theme.muted)
          .frame(maxWidth: .infinity, alignment: .leading)
          .padding()
      } else {
        LazyVGrid(columns: recipeColumns(typeSize), spacing: 16) {
          ForEach(recipes) { recipe in
            RecipeTile(recipe: recipe)
          }
        }
        .padding()
      }
    }
    .background(Theme.bg)
    .navigationTitle(title)
    .largeNavigationTitle()
  }
}

/// Square photo with a this-week check, bold name underneath. Long-press for favorite / to try / hide.
struct RecipeTile: View {
  @EnvironmentObject private var store: Store
  let recipe: RecipeSummary

  var body: some View {
    NavigationLink {
      RecipeDetailView(id: recipe.id)
    } label: {
      VStack(alignment: .leading, spacing: 8) {
        Color.clear
          .aspectRatio(1, contentMode: .fit)
          .overlay {
            // fill: size to this square. The old fixed 220pt banner overflowed it,
            // which zoomed the photo in and let the hidden overflow steal taps.
            RecipePhoto(path: recipe.photoPath, fill: true)
              .allowsHitTesting(false)
          }
          .clipped()
          .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
          .overlay(alignment: .topTrailing) {
            Button {
              Task { await store.toggleWeek(recipe) }
            } label: {
              Image(
                systemName: store.onWeek(recipe.id) ? "checkmark.circle.fill" : "plus.circle.fill"
              )
              .font(.system(size: 32))
              .symbolRenderingMode(.palette)
              .foregroundStyle(
                Color.white, store.onWeek(recipe.id) ? Theme.accent : Color.black.opacity(0.35)
              )
              .frame(width: 44, height: 44)
              .contentShape(Rectangle())
            }
            .buttonStyle(.borderless)
            .padding(4)
            .accessibilityLabel(
              store.onWeek(recipe.id) ? "Remove from this plan" : "Add to this plan")
          }
          .contentShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        Text(recipe.name)
          .font(Theme.recipeCardName)
          .foregroundStyle(Theme.ink)
          .lineLimit(3, reservesSpace: true)
          .truncationMode(.tail)
          .multilineTextAlignment(.leading)
          .fixedSize(horizontal: false, vertical: true)
          .frame(maxWidth: .infinity, alignment: .leading)
      }
    }
    .buttonStyle(.plain)
    .contextMenu {
      Button(recipe.favorited ? "Unfavorite" : "Favorite") {
        Task { await store.toggleFavorite(recipe) }
      }
      Button(store.onWeek(recipe.id) ? "Remove from plan" : "Add to plan") {
        Task { await store.toggleWeek(recipe) }
      }
      Button(recipe.toTry ? "Remove from To try" : "To try") {
        Task { await store.toggleTryLater(recipe) }
      }
      Button(
        recipe.hidden ? "Unhide recipe" : "Hide recipe",
        role: recipe.hidden ? .none : .destructive
      ) {
        Task { _ = await store.setHidden(id: recipe.id, on: !recipe.hidden) }
      }
    }
  }
}

private enum RecipePageTab: String {
  case overview, cook
}

struct RecipeDetailView: View {
  let id: Int
  @EnvironmentObject private var store: Store
  @Environment(\.dismiss) private var dismiss
  @State private var recipe: RecipeDetail?
  @State private var error: String?
  private var added: Bool { store.onWeek(id) }
  @State private var adding = false
  @State private var planNotice: String?
  @State private var showingMenu = false
  @State private var tab: RecipePageTab = .overview
  @State private var nameExpanded = false
  @State private var draftServings: Int?

  private var mealServings: Int {
    if let slot = store.plan?.slots.first(where: { $0.recipeId == id }) {
      return slot.servings
    }
    return draftServings ?? recipe?.servings ?? 4
  }

  var body: some View {
    Group {
      if let recipe {
        ScrollView {
          VStack(alignment: .leading, spacing: 16) {
            Picker("Page", selection: $tab) {
              Text("Overview").tag(RecipePageTab.overview)
              Text("Cook").tag(RecipePageTab.cook)
            }
            .pickerStyle(.segmented)

            if tab == .overview {
              RecipePhoto(path: recipe.photoPath, large: true)
            }

            // Long names at large text sizes pushed everything else off screen.
            // Cap at 3 lines with "…"; tap to see the whole name. VoiceOver always reads it all.
            Button {
              nameExpanded.toggle()
            } label: {
              Text(recipe.name)
                .font(Theme.recipeTitle)
                .foregroundStyle(Theme.ink)
                .multilineTextAlignment(.leading)
                .lineLimit(nameExpanded ? nil : 3)
                .truncationMode(.tail)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(recipe.name)
            .accessibilityAddTraits(.isHeader)
            .accessibilityRemoveTraits(.isButton)
            servingsRow(recipe)
            if tab == .overview, !recipe.prettyTags.isEmpty {
              Text(recipe.prettyTags).font(Theme.subtitle).foregroundStyle(Theme.muted)
            }

            if tab == .overview {
              Text("Ingredients").font(Theme.title)
              // Hairlines between rows, so at large text an amount stacked above its name
              // clearly belongs to that name and not the one before it.
              VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(recipe.ingredients.enumerated()), id: \.element.id) { i, ing in
                  if i > 0 { Rectangle().fill(Theme.line).frame(height: 1) }
                  ingredientLine(ing, recipe: recipe).padding(.vertical, 8)
                }
              }
            } else {
              Text("Steps").font(Theme.title)
              if recipe.instructionsCustomized {
                Text("Instructions customized by Dinnerdesk")
                  .font(Theme.subtitle).foregroundStyle(Theme.muted)
              }
              ForEach(Array(recipe.instructions.enumerated()), id: \.offset) { i, step in
                CookStepRow(index: i, step: step) {
                  Task { await togglePrep(at: i) }
                }
              }
            }

            Button {
              Task { await addToWeek() }
            } label: {
              Text(added ? "Remove from this plan" : "Add to this plan")
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(Theme.accent)
            .disabled(adding)
          }
          .padding()
        }
        .background(Theme.bg)
      } else if let error {
        ErrorBanner(message: error).padding()
      } else {
        ProgressView()
      }
    }
    .overlay(alignment: .bottom) {
      if let planNotice {
        Text(planNotice)
          .font(Theme.body)
          .padding()
          .background(Theme.bg, in: Capsule())
          .shadow(radius: 4)
          .padding(.bottom, 16)
          .allowsHitTesting(false)
      }
    }
    .task(id: planNotice) {
      guard planNotice != nil else { return }
      do { try await Task.sleep(for: .seconds(2)) } catch { return }
      planNotice = nil
    }
    .navigationBarTitleDisplayMode(.inline)
    .toolbar {
      if let recipe {
        ToolbarItem(placement: .topBarTrailing) {
          HStack {
            Button {
              Task { await addToWeek() }
            } label: {
              Image(systemName: added ? "minus.circle.fill" : "plus.circle.fill")
            }
            .disabled(adding)
            .accessibilityLabel(added ? "Remove from this plan" : "Add to this plan")
            .accessibilityValue(adding ? "Adding" : added ? "Added" : "Not added")
            Button {
              Task { await favorite(recipe) }
            } label: {
              Image(systemName: recipe.favorited ? "heart.fill" : "heart")
                .foregroundStyle(recipe.favorited ? Theme.accent : Theme.muted)
            }
            Button { showingMenu = true } label: {
              Image(systemName: "ellipsis.circle")
                .frame(minWidth: 44, minHeight: 44)
                .contentShape(Rectangle())
            }
            .accessibilityLabel("Recipe options")
          }
        }
      }
    }
    .menuSheet(isPresented: $showingMenu) {
      if let recipe {
        [
          MenuSheetItem(title: recipe.toTry ? "Remove from To try" : "To try", systemImage: "bookmark") {
            Task { await tryLater(recipe) }
          },
          MenuSheetItem(title: recipe.hidden ? "Unhide recipe" : "Hide recipe", systemImage: recipe.hidden ? "eye" : "eye.slash", destructive: !recipe.hidden) {
            Task { await hide(on: !recipe.hidden) }
          }
        ]
      } else { [] }
    }
    .task {
      do {
        recipe = try await API.get("recipes/\(id)")
      } catch {
        self.error = error.localizedDescription
      }
    }
  }

  private func ingredientLine(_ ing: IngredientLine, recipe: RecipeDetail) -> some View {
    let qty = scaleAmount(ing.quantity ?? "", from: recipe.servings, to: mealServings)
    return ViewThatFits(in: .horizontal) {
      HStack(alignment: .firstTextBaseline, spacing: 12) {
        if !qty.isEmpty {
          Text(qty).font(Theme.count).foregroundStyle(Theme.muted).lineLimit(1).fixedSize()
        }
        Text(ing.name).frame(maxWidth: .infinity, alignment: .leading)
      }
      VStack(alignment: .leading, spacing: 2) {
        if !qty.isEmpty {
          Text(qty).font(Theme.count).foregroundStyle(Theme.muted)
            .fixedSize(horizontal: false, vertical: true)
        }
        Text(ing.name).frame(maxWidth: .infinity, alignment: .leading)
      }
    }
    .font(Theme.body)
    .frame(maxWidth: .infinity, alignment: .leading)
  }

  private func servingsRow(_ recipe: RecipeDetail) -> some View {
    ViewThatFits(in: .horizontal) {
      HStack(alignment: .center, spacing: 16) {
        servingAdjuster
        cookTime(recipe)
      }
      VStack(alignment: .leading, spacing: 8) {
        servingAdjuster
        cookTime(recipe)
      }
    }
    .buttonStyle(.borderless)
  }

  private var servingAdjuster: some View {
    HStack(spacing: 8) {
      Button {
        Task { await bumpServings(-1) }
      } label: {
        Image(systemName: "minus.circle")
      }
      .disabled(mealServings <= 1)
      Text("\(mealServings) servings")
        .foregroundStyle(Theme.muted)
        .lineLimit(1)
        .fixedSize(horizontal: true, vertical: false)
      Button {
        Task { await bumpServings(1) }
      } label: {
        Image(systemName: "plus.circle")
      }
      .disabled(mealServings >= 50)
    }
  }

  @ViewBuilder
  private func cookTime(_ recipe: RecipeDetail) -> some View {
    if let mins = recipe.cookingMinutes {
      Text("\(mins) min")
        .foregroundStyle(Theme.muted)
        .lineLimit(1)
        .fixedSize(horizontal: true, vertical: false)
    }
  }

  private func bumpServings(_ delta: Int) async {
    let next = min(50, max(1, mealServings + delta))
    if next == mealServings { return }
    if store.onWeek(id) {
      await store.setServingsForRecipe(id, next)
    } else {
      draftServings = next
    }
  }

  private func favorite(_ current: RecipeDetail) async {
    if let next = await store.setFavorite(id: current.id, on: !current.favorited) {
      recipe = next
    }
  }

  private func tryLater(_ current: RecipeDetail) async {
    if let next = await store.setTryLater(id: current.id, on: !current.toTry) {
      recipe = next
    }
  }

  private func hide(on: Bool) async {
    if let next = await store.setHidden(id: id, on: on) {
      recipe = next
      if on { dismiss() }
    }
  }

  private func addToWeek() async {
    guard !adding else { return }
    let removing = added
    error = nil
    planNotice = nil
    adding = true
    defer { adding = false }
    if removing { await store.removeFromWeek(recipeId: id) }
    else { await store.addToWeek(recipeId: id, servings: mealServings) }
    if added != removing {
      planNotice = removing ? "Removed from this plan" : "Added to this plan"
    } else { error = store.error }
  }

  private func togglePrep(at index: Int) async {
    guard var recipe else { return }
    guard recipe.instructions.indices.contains(index) else { return }
    recipe.instructions[index].prep = !(recipe.instructions[index].prep ?? false)
    self.recipe = recipe
    do {
      let next: RecipeDetail = try await API.send(
        "recipes/\(id)",
        method: "PATCH",
        body: [
          "in_place": true,
          "instructions": recipe.instructions.map { $0.asBody() },
        ]
      )
      self.recipe = next
    } catch {
      self.error = error.localizedDescription
    }
  }
}

private struct CookStepRow: View {
  let index: Int
  let step: InstructionStep
  let onPrep: () -> Void

  var body: some View {
    VStack(alignment: .leading, spacing: 8) {
      HStack(alignment: .center, spacing: 8) {
        Text("\(index + 1).").foregroundStyle(Theme.accent)
        Button(action: onPrep) {
          Text("Prep")
            .font(Theme.chipLabel)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background((step.prep ?? false) ? Theme.accent : Theme.surface)
            .foregroundStyle((step.prep ?? false) ? Color.white : Theme.muted)
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
      }
      stepBody
        .frame(maxWidth: .infinity, alignment: .leading)
      // Far-future feature: keep duration parsing/countdowns out of Cook rendering.
      // StepTimers(text: step.displayText)
      if let ings = step.ings, !ings.isEmpty {
        VStack(alignment: .leading, spacing: 2) {
          ForEach(amountLines(ings), id: \.self) { line in
            Text(line).font(Theme.subtitle).foregroundStyle(Theme.muted)
          }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
      }
    }
    .padding(.bottom, 8)
  }

  @ViewBuilder
  private var stepBody: some View {
    let text = step.displayText
    let lines = text.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
    if let first = lines.first, first.hasSuffix(":"), first.count <= 70 {
      Text(first).font(Theme.action)
      if lines.count > 1 {
        Text(lines.dropFirst().joined(separator: "\n"))
      }
    } else {
      Text(text)
    }
  }

  private func amountLines(_ text: String) -> [String] {
    text
      .replacingOccurrences(of: "\r\n", with: "\n")
      .split(separator: "\n")
      .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
      .filter { !$0.isEmpty }
      .map { line in
        if line.hasPrefix("- ") || line.hasPrefix("• ") { return line }
        return "· \(line)"
      }
  }
}
