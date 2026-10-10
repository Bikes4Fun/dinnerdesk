import SwiftUI

/// One row in a ⋯ menu sheet.
struct MenuSheetItem: Identifiable {
  let id = UUID()
  let title: String
  let systemImage: String
  var destructive = false
  var dismissOnSelection = true
  var isOn: Bool? = nil
  var status: String? = nil
  var accent = false
  let action: () -> Void
}

extension View {
  /// Reusable ⋯ menu: a short bottom sheet of outline-icon rows with hairlines and a round × to close.
  /// The tapped row's action runs after the sheet is gone, so it can push screens or open other sheets.
  func menuSheet(isPresented: Binding<Bool>, items: @escaping () -> [MenuSheetItem]) -> some View {
    modifier(MenuSheetModifier(isPresented: isPresented, items: items))
  }
}

private struct MenuSheetModifier: ViewModifier {
  @Binding var isPresented: Bool
  let items: () -> [MenuSheetItem]
  @State private var pending: (() -> Void)?
  /// Measured height of the rows. Large text makes rows taller, so the sheet follows the content.
  @State private var contentHeight: CGFloat = 0

  func body(content: Content) -> some View {
    content.sheet(
      isPresented: $isPresented,
      onDismiss: {
        let run = pending
        pending = nil
        run?()
      }
    ) {
      let rows = items()
      MenuSheetBody(items: rows, height: $contentHeight, close: { isPresented = false }) { item in
        if item.dismissOnSelection {
          pending = item.action
          isPresented = false
        } else {
          item.action()
        }
      }
      .presentationDetents([.height(contentHeight > 0 ? contentHeight : CGFloat(rows.count) * 60 + 76)])
      .presentationDragIndicator(.hidden)
      .presentationCornerRadius(24)
      .presentationBackground(Theme.surface)
    }
  }
}

private struct MenuSheetBody: View {
  let items: [MenuSheetItem]
  @Binding var height: CGFloat
  let close: () -> Void
  let pick: (MenuSheetItem) -> Void

  var body: some View {
    // Scrolls when the rows are taller than the screen (accessibility text sizes).
    ScrollView {
      rows
        .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { height = $0 }
    }
    .scrollBounceBehavior(.basedOnSize)
  }

  private var rows: some View {
    VStack(spacing: 0) {
      HStack {
        Spacer()
        Button(action: close) {
          Image(systemName: "xmark")
            .font(.system(size: 14, weight: .bold))
            .foregroundStyle(Theme.muted)
            .frame(width: 32, height: 32)
            .background(Circle().fill(Theme.chip))
        }
        .accessibilityLabel("Close")
      }
      .padding(.horizontal, 16)
      .padding(.top, 14)
      .padding(.bottom, 6)

      ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
        if item.accent {
          Button {
            pick(item)
          } label: {
            Label(item.title, systemImage: item.systemImage)
          }
          .buttonStyle(.borderedProminent)
          .tint(Theme.accent)
          .padding(.bottom, 8)
        } else {
          Button {
            pick(item)
          } label: {
            HStack(spacing: 16) {
              Image(systemName: item.systemImage)
                .font(.system(size: 20))
                .foregroundStyle(item.destructive ? Color.red : Theme.muted)
                .frame(width: 28)
              Text(item.title)
                .font(Theme.rowTitle)
                .foregroundStyle(item.destructive ? Color.red : Theme.ink)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)
              Spacer(minLength: 0)
              if let on = item.isOn {
                Image(systemName: on ? "checkmark.circle.fill" : "circle")
                  .foregroundStyle(on ? Theme.accent : Theme.muted)
              }
              if let status = item.status {
                Text(status).font(Theme.subtitle).foregroundStyle(Theme.accent)
              }
            }
            .padding(.vertical, 8)
            .frame(minHeight: 60)
            .contentShape(Rectangle())
            .padding(.horizontal, 20)
          }
          .buttonStyle(.plain)
        }
        if index < items.count - 1 && !item.accent {
          Rectangle()
            .fill(Theme.line)
            .frame(height: 1)
            .padding(.leading, 64)
        }
      }
    }
    .padding(.bottom, 8)
  }
}
