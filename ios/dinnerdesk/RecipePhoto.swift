import SwiftUI

struct RecipePhoto: View {
  let path: String?
  var large = false
  var bannerHeight: CGFloat = 220
  /// Size to whatever frame the parent gives (thumbnails, tiles) instead of a fixed banner height.
  /// Without this a 220pt-tall photo gets cropped down to a small box and looks zoomed in.
  var fill = false
  @State private var image: UIImage?
  @State private var failure: String?

  var body: some View {
    let size: CGFloat = large ? bannerHeight : 56
    Group {
      if let image {
        Image(uiImage: image).resizable().scaledToFill()
      } else if let failure {
        Text("Photo failed: \(failure)").font(Theme.subtitle).foregroundStyle(.red)
      } else {
        placeholder
      }
    }
    .task(id: path) { await load() }
    .frame(width: fill || large ? nil : size, height: fill ? nil : size)
    .frame(maxWidth: fill || large ? .infinity : nil, maxHeight: fill ? .infinity : nil)
    .background(Theme.line)
    .clipped()
    .clipShape(RoundedRectangle(cornerRadius: large ? 16 : 8, style: .continuous))
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
