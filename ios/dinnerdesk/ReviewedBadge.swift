import SwiftUI

struct ReviewedBadge: View {
  var detail = false
  @State private var showing = false

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
          VStack(alignment: .leading, spacing: 16) {
            label.font(Theme.title)
            Text(Copy.text("recipe.kitchen-tested.explanation")).font(Theme.body)
            Button("Done") { showing = false }.frame(minHeight: 44)
          }
          .padding(24).foregroundStyle(Theme.ink)
          .presentationDetents([.medium, .large])
          .presentationDragIndicator(.visible)
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
