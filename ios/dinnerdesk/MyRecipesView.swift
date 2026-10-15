import PhotosUI
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
      // A server without the `mine` filter sends every recipe; keep only the kitchen's own.
      recipes = box.recipes.filter { !$0.catalog }
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
  @State private var source = ""
  /// The imported page's photo, copied for this kitchen on save (its link is kept too).
  @State private var siteImage = ""
  @State private var photoPick: PhotosPickerItem?
  /// The cook's own photo, used instead of the site's.
  @State private var ownPhoto: UIImage?

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
          Section {
            if let ownPhoto {
              Image(uiImage: ownPhoto)
                .resizable().scaledToFill()
                .frame(width: 140, height: 140)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            } else if imported, let url = URL(string: siteImage), !siteImage.isEmpty {
              AsyncImage(url: url) { image in
                image.resizable().scaledToFill()
              } placeholder: {
                Theme.chip
              }
              .frame(width: 140, height: 140)
              .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            PhotosPicker(
              ownPhoto == nil ? "Choose your own photo" : "Choose a different photo",
              selection: $photoPick, matching: .images
            )
            if ownPhoto != nil {
              Button(imported && !siteImage.isEmpty ? "Use the site's photo" : "Remove photo", role: .destructive) {
                ownPhoto = nil
                photoPick = nil
              }
            }
          } header: {
            Text("Photo")
          } footer: {
            if ownPhoto == nil && imported && !siteImage.isEmpty {
              Text("This is the photo from that page, saved for your kitchen only. Don't like it? Choose your own.")
            } else if ownPhoto == nil {
              Text("Add a photo you took or one you're free to use.")
            }
          }
          .listRowBackground(Theme.surface)
          if mode == .write {
            Section {
              TextField("https://", text: $source)
                .keyboardType(.URL)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            } header: {
              Text("Source (optional)")
            } footer: {
              Text("Where this recipe came from.")
            }
            .listRowBackground(Theme.surface)
          }
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
      .onChange(of: photoPick) { _, item in
        Task { await loadPhoto(item) }
      }
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
      siteImage = draft.imageUrl ?? ""
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
    var body: [String: Any] = [
      "name": name.trimmingCharacters(in: .whitespaces),
      "servings": servings,
      "cooking_minutes": mins.map { $0 as Any } ?? NSNull(),
      "source_url": (mode == .importURL ? url : source).trimmingCharacters(in: .whitespaces),
      // The server splits "2 cloves garlic" into its amount and item.
      "ingredients": lines.map { ["quantity": "", "name": $0] },
      "instructions": steps
        .map { $0.text.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
        .map { ["text": $0, "prep": false, "ings": ""] },
      "cookware": [String](),
      "tags": [mode == .importURL ? "imported" : "custom"],
      "imported": imported,
      "photo_url": imported ? siteImage : "",
    ]
    if let ownPhoto, let data = Self.photoData(ownPhoto) {
      body["photo_data"] = data
    }
    do {
      let created: CreatedRecipe = try await API.send("recipes", method: "POST", body: body)
      dismiss()
      onSaved(created.id)
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}

extension RecipeFormView {
  private func loadPhoto(_ item: PhotosPickerItem?) async {
    guard let item else { return }
    do {
      guard let data = try await item.loadTransferable(type: Data.self), let image = UIImage(data: data) else {
        error = "Couldn't read that photo."
        return
      }
      ownPhoto = image
      error = nil
    } catch {
      self.error = "Couldn't read that photo."
    }
  }

  /// A JPEG data: URL under the server's 5 MB photo limit.
  fileprivate static func photoData(_ image: UIImage) -> String? {
    let longest = max(image.size.width, image.size.height)
    let scale = min(1, 2000 / max(longest, 1))
    let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
    let format = UIGraphicsImageRendererFormat()
    format.scale = 1
    let resized = UIGraphicsImageRenderer(size: size, format: format).image { _ in
      image.draw(in: CGRect(origin: .zero, size: size))
    }
    for quality in [0.85, 0.7, 0.5] {
      if let jpeg = resized.jpegData(compressionQuality: quality), jpeg.count < 4_800_000 {
        return "data:image/jpeg;base64," + jpeg.base64EncodedString()
      }
    }
    return nil
  }
}

/// A recipe read off a web page by POST /recipes/import; nothing is saved yet.
nonisolated struct RecipeDraft: Decodable, Sendable {
  let name: String
  let servings: Int?
  let cookingMinutes: Int?
  let sourceUrl: String?
  let imageUrl: String?
  let ingredientLines: [String]
  let instructions: [InstructionStep]
}

nonisolated struct CreatedRecipe: Decodable, Sendable {
  let id: Int
}
