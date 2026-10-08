import SwiftUI

struct ErrorBanner: View {
  let message: String

  var body: some View {
    Text(message)
      .font(Theme.subtitle)
      .foregroundStyle(Color(red: 179 / 255, green: 59 / 255, blue: 50 / 255))
      .frame(maxWidth: .infinity, alignment: .leading)
      .padding(.horizontal, 14)
      .padding(.vertical, 11)
      .background(Color(red: 248 / 255, green: 228 / 255, blue: 224 / 255))
      .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
  }
}
