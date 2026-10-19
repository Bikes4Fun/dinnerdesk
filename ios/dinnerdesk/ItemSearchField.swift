import SwiftUI

/// Search foods and pick several: each match is a "+ name" chip that adds to `selected`.
/// Shared by Filters (allergies, not a fan of) and the Kitchen pickers (pantry, always checked off).
/// Return adds the first match and keeps the field open for the next one.
struct ItemSearchField: View {
  let label: String
  var placeholder = "Search foods, e.g. bell peppers or ground"
  var dashed = false
  var autofocus = false
  var presets: [String] = []
  var taken: Set<String> = []
  @Binding var selected: [String]
  var onCommit: () -> Void = {}
  /// Defaults to diet-filter foods.
  var search: ((String) async throws -> [String])?
  @State private var query = ""
  @State private var matches: [String] = []
  @State private var loading = false
  @State private var error: String?
  @FocusState private var focused: Bool

  /// Foods for diet filters (allergies, dislikes).
  static func filterItems(_ query: String) async throws -> [String] {
    let box: KitchenItemSearch = try await API.get("filter-items", query: ["q": query], reportErrors: false)
    return box.items.map(\.name)
  }

  private var presetHits: [String] {
    let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !q.isEmpty else { return [] }
    return presets.filter { $0.localizedCaseInsensitiveContains(q) && !selected.contains($0) && !taken.contains($0) }
  }

  private var searchHits: [String] {
    matches.filter { !selected.contains($0) && !taken.contains($0) && !presetHits.contains($0) }
  }

  var body: some View {
    VStack(alignment: .leading, spacing: 10) {
      TextField(placeholder, text: $query)
        .textInputAutocapitalization(.never)
        .autocorrectionDisabled()
        .font(Theme.body)
        .focused($focused)
        .submitLabel(.done)
        .onSubmit {
          if let first = presetHits.first ?? searchHits.first { add(first, clear: true) }
          focused = true
        }
        .padding(.horizontal, dashed ? 14 : 12)
        .frame(height: dashed ? 46 : nil)
        .padding(.vertical, dashed ? 0 : 12)
        .background(dashed ? Color(hex: 0xFBF6EE) : Theme.surface, in: RoundedRectangle(cornerRadius: dashed ? 23 : 12))
        .overlay(
          RoundedRectangle(cornerRadius: dashed ? 23 : 12)
            .stroke(dashed ? Color(hex: 0xD9C9D3) : Theme.line, style: StrokeStyle(lineWidth: 1, dash: dashed ? [4, 3] : []))
        )
        .accessibilityLabel("Search \(label.lowercased())")
      if loading { ProgressView() }
      if let error { Text(error).font(Theme.subtitle) }
      // Matches as chips (#85): tap one to add it; it moves up with the other picked chips.
      KitchenFlow(spacing: 6) {
        ForEach(presetHits, id: \.self) { name in
          FilterChip(label: "+ \(name)", on: false) { add(name, clear: true) }
            .accessibilityLabel("Add \(name)")
        }
        ForEach(searchHits, id: \.self) { name in
          FilterChip(label: "+ \(name)", on: false) { add(name, clear: false) }
            .accessibilityLabel("Add \(name)")
        }
      }
      if !loading && error == nil && !query.isEmpty && matches.isEmpty && presetHits.isEmpty {
        Text("No matching foods. Try another name.").font(Theme.subtitle)
      }
    }
    .onAppear { if autofocus { focused = true } }
    .task(id: query) {
      matches = []
      error = nil
      let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
      guard !q.isEmpty else { loading = false; return }
      loading = true
      do {
        try await Task.sleep(for: .milliseconds(250))
        let hits = try await (search ?? Self.filterItems)(q)
        try Task.checkCancellation()
        matches = hits
        loading = false
      } catch {
        if !API.isCancellation(error) {
          self.error = "Couldn't search foods. Please try again."
          loading = false
        }
      }
    }
  }

  private func add(_ name: String, clear: Bool) {
    guard !selected.contains(name) else { return }
    selected.append(name)
    if clear { query = "" }
    onCommit()
  }
}
