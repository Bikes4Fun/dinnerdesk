import SwiftUI

/// A tip: help text that explains a feature, shown with a purple ★ on a pale aubergine panel
/// (docs/DESIGN.md, UI principles). The words come from copy.json by `id`, and the
/// `tip.<id>` identifier lets scripts/list_tips.py find every tip.
struct StarTip: View {
  let id: String

  /// Purple for the star. #7A3B73 on the aubergine tint is about 6.7:1.
  static let star = Color(hex: 0x7A3B73)

  var body: some View {
    HStack(alignment: .firstTextBaseline, spacing: 8) {
      Image(systemName: "star.fill")
        .font(Theme.subtitle)
        .foregroundStyle(Self.star)
        .accessibilityHidden(true)
      Text(Copy.text(id))
        .font(Theme.subtitle)
        .foregroundStyle(Theme.ink)
        .fixedSize(horizontal: false, vertical: true)
    }
    .padding(.horizontal, 12)
    .padding(.vertical, 8)
    .frame(maxWidth: .infinity, alignment: .leading)
    .background(Theme.aubergineTint, in: RoundedRectangle(cornerRadius: 10))
    .accessibilityElement(children: .combine)
    .accessibilityIdentifier("tip.\(id)")
  }
}
