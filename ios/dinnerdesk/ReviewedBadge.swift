import SwiftUI

struct ReviewedBadge: View {
  var detail = false
  @State private var showing = false
  @State private var sheetHeight: CGFloat = 0

  var body: some View {
    Group {
      if detail {
        Button { showing = true } label: {
          HStack(spacing: 6) {
            label
            Image(systemName: "chevron.right").font(.caption)
          }
          .padding(.horizontal, 12).frame(minHeight: 44)
          .background(Theme.aubergineTint, in: Capsule())
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showing) {
          ScrollView {
            VStack(spacing: 16) {
              label
                .font(.system(size: 28))
                .frame(width: 72, height: 72)
                .background(Theme.aubergineTint, in: Circle())
              Text(Copy.text("recipe.reviewed")).font(Theme.title)
              Text(Copy.text("recipe.kitchen-tested.explanation"))
                .font(Theme.body)
                .multilineTextAlignment(.center)
              Button { showing = false } label: {
                Text("Got it")
                  .font(Theme.action)
                  .foregroundStyle(Theme.surface)
                  .frame(maxWidth: .infinity, minHeight: 48)
                  .background(Theme.ink, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
              }
              .buttonStyle(.plain)
            }
            .padding(24)
            .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { sheetHeight = $0 }
          }
          .scrollBounceBehavior(.basedOnSize)
          .foregroundStyle(Theme.ink)
          .presentationDetents([.height(sheetHeight > 0 ? sheetHeight + 28 : 280), .large])
          .presentationDragIndicator(.visible)
          .presentationBackground(Theme.surface)
        }
      } else { label }
    }
    .font(.caption.weight(.semibold))
    .foregroundStyle(Theme.ink)
    .accessibilityLabel(Copy.text("recipe.reviewed.description"))
  }

  private var label: some View {
    Label(Copy.text("recipe.reviewed"), systemImage: "checkmark.seal.fill")
  }
}

struct RecipeStatusLine: View {
  let minutes: Int?
  let reviewed: Bool

  var body: some View {
    HStack(spacing: 4) {
      if let minutes, minutes > 0 { Text("\(minutes) min").foregroundStyle(Theme.muted) }
      if reviewed {
        if let minutes, minutes > 0 { Text("·").accessibilityHidden(true) }
        ReviewedBadge()
      }
    }
    .font(.caption).foregroundStyle(Theme.ink)
  }
}
