import SwiftUI

struct RecipePhoto: View {
  let path: String?
  var large = false
  /// Square tiles expand to the available width; thumbnails default to 56 points.
  var fill = false
  var hideUnavailable = false
  @State private var image: UIImage?
  @State private var failure: String?

  var body: some View {
    Group {
      if !hideUnavailable || image != nil {
        Color.clear.aspectRatio(1, contentMode: .fit)
          .overlay {
            GeometryReader { geometry in
              Group {
                if let image {
                  Image(uiImage: image).resizable().scaledToFill()
                } else {
                  placeholder
                }
              }
              .frame(width: geometry.size.width, height: geometry.size.height)
              .clipped()
            }
          }
          .frame(width: fill || large ? nil : 56)
          .background(Theme.line)
          .clipShape(RoundedRectangle(cornerRadius: large ? 16 : 8, style: .continuous))
      }
    }
    .task(id: path) { await load() }
  }

  private func load() async {
    image = nil
    failure = nil
    guard let url = API.photoURL(path) else { return }
    do {
      let (data, response) = try await URLSession.shared.data(from: url)
      try Task.checkCancellation()
      guard let response = response as? HTTPURLResponse, (200..<300).contains(response.statusCode)
      else {
        throw APIError.http((response as? HTTPURLResponse)?.statusCode ?? 0, "Photo request failed")
      }
      guard let decoded = UIImage(data: data) else {
        throw APIError.http(response.statusCode, "Invalid photo data")
      }
      image = decoded
    } catch {
      if Task.isCancelled || API.isCancellation(error) { return }
      failure = error.localizedDescription
      API.reportFailure(error)
    }
  }

  private var placeholder: some View {
    ZStack {
      Theme.line
      Image(systemName: "photo")
        .font(large ? .title2 : .body)
        .foregroundStyle(Theme.muted)
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
  }
}
