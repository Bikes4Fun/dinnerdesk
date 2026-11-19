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
              Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 32))
                .accessibilityHidden(true)
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
    ViewThatFits(in: .horizontal) {
      row(stacked: false)
      row(stacked: true)
    }
    .frame(maxWidth: .infinity, alignment: .leading)
  }

  private var hasTime: Bool { if let minutes, minutes > 0 { return true }; return false }

  @ViewBuilder
  private func row(stacked: Bool) -> some View {
    if stacked {
      VStack(alignment: .leading, spacing: 2) {
        if hasTime { timeText }
        if reviewed { badge }
      }
    } else {
      HStack(spacing: 4) {
        if hasTime { timeText }
        if hasTime && reviewed { Text("·").foregroundStyle(Theme.muted).accessibilityHidden(true) }
        if reviewed { badge }
      }
      .lineLimit(1)
      .fixedSize(horizontal: true, vertical: false)
    }
  }

  private var timeText: some View {
    Text("\(minutes ?? 0) min").font(.caption).foregroundStyle(Theme.ink)
  }

  private var badge: some View {
    HStack(spacing: 4) {
      Image(systemName: "checkmark.seal.fill").foregroundStyle(Theme.ink)
      Text(Copy.text("recipe.reviewed")).fontWeight(.medium).foregroundStyle(Theme.ink)
    }
    .font(.caption)
    .accessibilityElement(children: .combine)
    .accessibilityLabel(Copy.text("recipe.reviewed.description"))
  }
}
