import SwiftUI

struct ReviewedBadge: View {
  var body: some View {
    Label(Copy.text("recipe.reviewed"), systemImage: "checkmark.seal.fill")
      .font(.caption.weight(.semibold))
      .padding(.horizontal, 8).padding(.vertical, 4)
      .foregroundStyle(Theme.ink)
      .background(Color.yellow.opacity(0.2), in: RoundedRectangle(cornerRadius: 8))
      .accessibilityLabel(Copy.text("recipe.reviewed.description"))
  }
}
