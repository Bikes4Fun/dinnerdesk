import SwiftUI

// Shared look for the kitchen, settings, tour and sign-in screens (shared across the app):
// plain lists on the app background, hairline separators, small grey all-caps section headers,
// grey outline icons, Fraunces for big titles and DM Sans for everyday text, and the accent only on actions.

enum KitchenStyle {
  static let ok = Theme.ok
  static let bigTitle = Theme.bigTitle
  static let title = Theme.tourTitle
}

/// Section header that stops pinning once the type size would eat the screen.
struct KitchenSection<Content: View, Footer: View>: View {
  let title: String
  let content: Content
  let footer: Footer
  @Environment(\.dynamicTypeSize) private var typeSize

  init(
    _ title: String, @ViewBuilder content: () -> Content, @ViewBuilder footer: () -> Footer
  ) {
    self.title = title
    self.content = content()
    self.footer = footer()
  }

  private var pin: Bool { typeSize < .accessibility1 }

  var body: some View {
    if pin {
      Section {
        content
      } header: {
        KitchenHeader(title)
      } footer: {
        footer
      }
    } else {
      Section {
        KitchenHeader(title)
          .listRowInsets(EdgeInsets(top: 18, leading: 20, bottom: 4, trailing: 20))
          .kitchenBareRow()
        content
      } footer: {
        footer
      }
    }
  }
}

extension KitchenSection where Footer == EmptyView {
  init(_ title: String, @ViewBuilder content: () -> Content) {
    self.init(title, content: content, footer: { EmptyView() })
  }
}

/// Small grey all-caps section header, like PRODUCE on the grocery list.
struct KitchenHeader: View {
  let text: String

  init(_ text: String) {
    self.text = text
  }

  var body: some View {
    Text(text.uppercased())
      .font(Theme.title)
      .tracking(0.8)
      .foregroundStyle(Theme.muted.opacity(0.85))
      .textCase(nil)
      .padding(.top, 6)
  }
}

/// Grey outline icon, bold label, optional grey value on the right.
struct KitchenIconRow: View {
  let title: String
  let systemImage: String
  var value: String?
  @Environment(\.dynamicTypeSize) private var typeSize

  var body: some View {
    if typeSize.isAccessibilitySize {
      // Large text: the value goes under the title, so the title keeps the full width
      // instead of being squeezed into a column beside "5 aisles".
      HStack(alignment: .top, spacing: 14) {
        icon.padding(.top, 6)
        VStack(alignment: .leading, spacing: 2) {
          titleText
          if let value { valueText(value) }
        }
        Spacer(minLength: 0)
      }
      .frame(minHeight: 44)
    } else {
      HStack(spacing: 14) {
        icon
        titleText
        Spacer(minLength: 8)
        if let value { valueText(value).lineLimit(1) }
      }
      .frame(minHeight: 44)
    }
  }

  private var icon: some View {
    Image(systemName: systemImage)
      .font(.system(size: 19))
      .foregroundStyle(Theme.muted)
      .frame(width: 26)
      .accessibilityHidden(true)
  }

  private var titleText: some View {
    Text(title)
      .font(Theme.mealName)
      .foregroundStyle(Theme.ink)
      .fixedSize(horizontal: false, vertical: true)
  }

  private func valueText(_ value: String) -> some View {
    Text(value)
      .foregroundStyle(Theme.muted)
      .monospacedDigit()
  }
}

/// "+ Add item" row in the accent color.
struct KitchenAddRow: View {
  let title: String
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      Label(title, systemImage: "plus")
        .font(Theme.mealName)
        .foregroundStyle(Theme.accent)
    }
  }
}

extension View {
  /// Plain list on the app background with hairline separators.
  func kitchenList() -> some View {
    listStyle(.plain)
      .scrollContentBackground(.hidden)
      .background(Theme.bg)
      .environment(\.defaultMinListRowHeight, 56)
  }

  /// Row background and separator color for rows in a `kitchenList`.
  func kitchenRows() -> some View {
    listRowBackground(Theme.bg)
      .listRowSeparatorTint(Theme.line)
  }

  /// A row that shouldn't look like a row (banners, explanations, chip clouds).
  func kitchenBareRow() -> some View {
    listRowBackground(Theme.bg)
      .listRowSeparator(.hidden)
  }

  /// Forms use the same page color as the lists, including the grouped card behind them.
  func kitchenForm() -> some View {
    scrollContentBackground(.hidden)
      .background(Theme.bg)
  }
}
