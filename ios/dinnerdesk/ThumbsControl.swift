import SwiftUI

/// Thumbs up / down. `rating` is 1, -1 or 0; tapping the lit thumb again clears it.
struct ThumbsControl: View {
  let rating: Int
  let subject: String
  var size: CGFloat = 17
  let onRate: (Int) -> Void

  var body: some View {
    HStack(spacing: 0) {
      thumb(up: true)
      thumb(up: false)
    }
  }

  private func thumb(up: Bool) -> some View {
    let value = up ? 1 : -1
    let on = rating == value
    let name = up ? "hand.thumbsup" : "hand.thumbsdown"
    return Button {
      onRate(on ? 0 : value)
    } label: {
      Image(systemName: on ? "\(name).fill" : name)
        .font(.system(size: size, weight: .semibold))
        .foregroundStyle(on ? (up ? Theme.ink : Theme.accent) : Theme.muted)
        .frame(width: 44, height: 36)
        .contentShape(Rectangle())
    }
    .buttonStyle(.plain)
    .accessibilityLabel(up ? "Like \(subject)" : "Dislike \(subject)")
    .accessibilityAddTraits(on ? .isSelected : [])
  }
}
