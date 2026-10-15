import SwiftUI

/// The kitchen's own recipes: ones written here, imported from a website, or saved as copies.
struct MyRecipesView: View {
  @State private var recipes: [RecipeSummary] = []
  @State private var loaded = false
  @State private var error: String?
  @State private var form: RecipeFormView.Mode?
  @State private var openId: Int?

  var body: some View {
    List {
      if let error {
        ErrorBanner(message: error).themeBareRow()
      }
      if loaded && recipes.isEmpty {
        EmptyState(
          title: "No recipes of your own yet",
          message: "Write one out, or import one from a recipe website with the + button.",
          systemImage: "book.closed"
        )
        .themeBareRow()
      }
      ForEach(recipes) { recipe in
        NavigationLink {
          RecipeDetailView(id: recipe.id)
        } label: {
          HStack(spacing: 12) {
            RecipePhoto(path: recipe.photoPath)
              .frame(width: 56, height: 56)
              .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
              Text(recipe.name)
                .font(Theme.rowTitle)
                .foregroundStyle(Theme.ink)
                .lineLimit(2)
              if let minutes = recipe.cookingMinutes {
                Text("\(minutes) min")
                  .font(Theme.subtitle)
                  .foregroundStyle(Theme.muted)
              }
            }
          }
        }
        .themeRows()
      }
      .onDelete { offsets in
        let gone = offsets.map { recipes[$0] }
        recipes.remove(atOffsets: offsets)
        Task { await delete(gone) }
      }
    }
    .themeList()
    .navigationTitle("My recipes")
    .navigationBarTitleDisplayMode(.inline)
    .toolbar {
      ToolbarItem(placement: .primaryAction) {
        Menu {
          Button("Write your own", systemImage: "square.and.pencil") { form = .write }
          Button("Import from a website", systemImage: "link") { form = .importURL }
        } label: {
          Image(systemName: "plus")
        }
        .accessibilityLabel("Add recipe")
      }
    }
    .sheet(item: $form) { mode in
      RecipeFormView(mode: mode) { id in
        Task {
          await load()
          openId = id
        }
      }
    }
    .navigationDestination(item: $openId) { id in
      RecipeDetailView(id: id)
    }
    .task { await load() }
    .refreshable { await load() }
  }

  private func load() async {
    do {
      let box: RecipeList = try await API.get("recipes", query: ["mine": "true", "limit": "500"])
      recipes = box.recipes
      error = nil
    } catch {
      if !API.isCancellation(error) { self.error = KitchenAPI.message(error) }
    }
    loaded = true
  }

  private func delete(_ gone: [RecipeSummary]) async {
    for recipe in gone {
      do {
        let _: Ok = try await API.send("recipes/\(recipe.id)", method: "DELETE")
      } catch {
        self.error = KitchenAPI.message(error)
        await load()
        return
      }
    }
  }
}

/// Write a recipe box by box, or read one off a public recipe page and check it before saving.
struct RecipeFormView: View {
  enum Mode: String, Identifiable {
    case write, importURL
    var id: String { rawValue }
  }

  let mode: Mode
  let onSaved: (Int) -> Void
  @Environment(\.dismiss) private var dismiss

  @State private var url = ""
  @State private var importing = false
  @State private var imported = false
  @State private var typing = false
  @State private var name = ""
  @State private var servings = 4
  @State private var minutes = ""
  @State private var ingredients = ""
  @State private var steps: [StepDraft] = [StepDraft()]
  @State private var saving = false
  @State private var error: String?

  struct StepDraft: Identifiable {
    let id = UUID()
    var text = ""
  }

  /// URL mode shows the boxes once the page is read, or once the cook chooses to type it in.
  private var showBoxes: Bool { mode == .write || imported || typing }
  private var canSave: Bool {
    !name.trimmingCharacters(in: .whitespaces).isEmpty && !saving && !importing
  }

  var body: some View {
    NavigationStack {
      Form {
        if let error {
          Section { Text(error).foregroundStyle(Theme.accent) }
            .listRowBackground(Theme.surface)
        }
        if mode == .importURL {
          Section {
            TextField("https://", text: $url)
              .keyboardType(.URL)
              .textContentType(.URL)
              .textInputAutocapitalization(.never)
              .autocorrectionDisabled()
              .onSubmit { Task { await runImport() } }
            Button(importing ? "Reading…" : imported ? "Read again" : "Import") {
              Task { await runImport() }
            }
            .disabled(importing || url.trimmingCharacters(in: .whitespaces).isEmpty)
          } header: {
            Text("Recipe page")
          } footer: {
            if imported {
              Text("Check it over before you save. The ingredients and steps came from that site.")
            } else if !typing {
              VStack(alignment: .leading, spacing: 6) {
                Text("Paste a link to a recipe on a public website.")
                Button("Type it in instead") { typing = true }
                  .foregroundStyle(Theme.accent)
              }
            }
          }
          .listRowBackground(Theme.surface)
        }
        if showBoxes {
          Section("Recipe") {
            TextField("Name", text: $name)
            Stepper("Servings: \(servings)", value: $servings, in: 1...50)
            TextField("Minutes (optional)", text: $minutes)
              .keyboardType(.numberPad)
          }
          .listRowBackground(Theme.surface)
          Section {
            TextField("1 onion\n2 cloves garlic", text: $ingredients, axis: .vertical)
              .lineLimit(5...30)
          } header: {
            Text("Ingredients")
          } footer: {
            Text("One per line, amount first.")
          }
          .listRowBackground(Theme.surface)
          Section("Steps") {
            ForEach($steps) { $step in
              HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("\((steps.firstIndex { $0.id == step.id } ?? 0) + 1).")
                  .font(Theme.count)
                  .foregroundStyle(Theme.muted)
                TextField("What to do", text: $step.text, axis: .vertical)
                  .lineLimit(2...12)
              }
            }
            .onDelete { steps.remove(atOffsets: $0) }
            Button("Add step", systemImage: "plus") { steps.append(StepDraft()) }
          }
          .listRowBackground(Theme.surface)
        }
      }
      .themeForm()
      .navigationTitle(mode == .write ? "New recipe" : "Import a recipe")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button("Cancel") { dismiss() }
        }
        if showBoxes {
          ToolbarItem(placement: .confirmationAction) {
            Button(saving ? "Saving…" : "Save") { Task { await save() } }
              .disabled(!canSave)
          }
        }
      }
    }
  }

  private func runImport() async {
    let link = url.trimmingCharacters(in: .whitespaces)
    guard !link.isEmpty, !importing else { return }
    importing = true
    error = nil
    defer { importing = false }
    do {
      let draft: RecipeDraft = try await API.send("recipes/import", method: "POST", body: ["url": link])
      name = draft.name
      servings = draft.servings ?? 4
      minutes = draft.cookingMinutes.map(String.init) ?? ""
      ingredients = draft.ingredientLines.joined(separator: "\n")
      let read = draft.instructions.map { StepDraft(text: $0.displayText) }
      steps = read.isEmpty ? [StepDraft()] : read
      url = draft.sourceUrl ?? link
      imported = true
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }

  private func save() async {
    saving = true
    error = nil
    defer { saving = false }
    let lines = ingredients
      .split(whereSeparator: \.isNewline)
      .map { $0.trimmingCharacters(in: .whitespaces) }
      .filter { !$0.isEmpty }
    let mins = Int(minutes.trimmingCharacters(in: .whitespaces))
    let body: [String: Any] = [
      "name": name.trimmingCharacters(in: .whitespaces),
      "servings": servings,
      "cooking_minutes": mins.map { $0 as Any } ?? NSNull(),
      "source_url": mode == .importURL ? url.trimmingCharacters(in: .whitespaces) : "",
      // The server splits "2 cloves garlic" into its amount and item.
      "ingredients": lines.map { ["quantity": "", "name": $0] },
      "instructions": steps
        .map { $0.text.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
        .map { ["text": $0, "prep": false, "ings": ""] },
      "cookware": [String](),
      "tags": [mode == .importURL ? "imported" : "custom"],
      "imported": imported,
    ]
    do {
      let created: CreatedRecipe = try await API.send("recipes", method: "POST", body: body)
      dismiss()
      onSaved(created.id)
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}

/// A recipe read off a web page by POST /recipes/import; nothing is saved yet.
nonisolated struct RecipeDraft: Decodable, Sendable {
  let name: String
  let servings: Int?
  let cookingMinutes: Int?
  let sourceUrl: String?
  let ingredientLines: [String]
  let instructions: [InstructionStep]
}

nonisolated struct CreatedRecipe: Decodable, Sendable {
  let id: Int
}
