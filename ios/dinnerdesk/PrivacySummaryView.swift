import SwiftUI

/// The short version of the privacy policy: what we keep, what we never collect, who else can see it.
/// Shown at the top of Privacy, on sign up, and on the first-open agreement screen. Words: privacy.*
/// in copy.json, shared with web (PrivacySummary.jsx) and Android (PrivacySummary).
struct PrivacySummaryView: View {
  /// Leaves out "Who else can see it" where space is tight (sign up, first open).
  var compact = false

  private func rows(_ prefix: String, _ count: Int) -> [(title: String, body: String)] {
    (1...count).map { (Copy.text("\(prefix).\($0).title"), Copy.text("\(prefix).\($0)")) }
  }

  private func header(_ id: String) -> some View {
    Text(Copy.text(id).uppercased())
      .font(Theme.sectionHeader)
      .tracking(0.6)
      .foregroundStyle(Theme.muted)
      .padding(.top, 10)
  }

  private func list(_ items: [(title: String, body: String)]) -> some View {
    VStack(alignment: .leading, spacing: 0) {
      ForEach(Array(items.enumerated()), id: \.offset) { index, row in
        VStack(alignment: .leading, spacing: 2) {
          Text(row.title).font(Theme.rowTitle).foregroundStyle(Theme.ink)
          Text(row.body).font(Theme.subtitle).foregroundStyle(Theme.muted)
            .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, compact ? 6 : 10)
        if index < items.count - 1 { Divider().overlay(Theme.line) }
      }
    }
    .accessibilityElement(children: .contain)
  }

  var body: some View {
    VStack(alignment: .leading, spacing: 8) {
      Text(Copy.text("privacy.sell"))
        .font(Theme.action)
        .foregroundStyle(Theme.bg)
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.ink, in: RoundedRectangle(cornerRadius: 14))

      header("privacy.keep.title")
      list(rows("privacy.keep", 4))
      Text(Copy.text("privacy.keep.use")).font(Theme.subtitle).foregroundStyle(Theme.muted)

      header("privacy.never.title")
      LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible())], alignment: .leading, spacing: 8) {
        ForEach(Copy.text("privacy.never").components(separatedBy: " · "), id: \.self) { item in
          Text(item)
            .font(Theme.chipLabel)
            .foregroundStyle(Theme.ink)
            .padding(.horizontal, 12).padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
        }
      }
      Text(Copy.text("privacy.health"))
        .font(Theme.subtitle)
        .foregroundStyle(Theme.ink)
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.aubergineTint, in: RoundedRectangle(cornerRadius: 12))

      if !compact {
        header("privacy.shared.title")
        list(rows("privacy.shared", 3))
      }
    }
  }
}
