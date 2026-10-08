import SwiftUI

struct EmptyState: View {
  let title: String
  let message: String
  var systemImage = "fork.knife"

  var body: some View {
    VStack(spacing: 10) {
      Image(systemName: systemImage)
        .font(.system(size: 32))
        .foregroundStyle(Theme.accent)
      Text(title)
        .font(Theme.mealName)
        .foregroundStyle(Theme.ink)
      Text(message)
        .font(Theme.subtitle)
        .foregroundStyle(Theme.muted)
        .multilineTextAlignment(.center)
    }
    .frame(maxWidth: .infinity)
    .padding(.vertical, 28)
    .padding(.horizontal, 20)
  }
}
