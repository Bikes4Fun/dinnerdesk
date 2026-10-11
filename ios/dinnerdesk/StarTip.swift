import SwiftUI

/// A tip: help text that explains a feature, shown with a purple ★ on a pale aubergine panel
/// (docs/DESIGN.md, UI principles). The words come from copy.json by `id`, and the
/// `tip.<id>` identifier lets scripts/list_tips.py find every tip.
struct StarTip: View {
  let id: String

  /// Purple for the star. #7A3B73 on the aubergine tint is about 6.7:1.
  static let star = Color(hex: 0x7A3B73)

  // Kept in source for scripts/list_tips.py and the future tour (#103).
  var body: some View { EmptyView() }
}
