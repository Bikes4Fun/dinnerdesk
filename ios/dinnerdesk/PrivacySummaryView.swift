import SwiftUI

/// "Your household can see all of it, including your allergies, likes, dislikes and Taste Lab history."
struct HouseholdSharingNote: View {
  var body: some View {
    (Text(Copy.text("privacy.household.lead")).fontWeight(.semibold) + Text(" " + Copy.text("privacy.household")))
      .font(Theme.subtitle)
      .foregroundStyle(Theme.ink)
      .fixedSize(horizontal: false, vertical: true)
      .padding(12)
      .frame(maxWidth: .infinity, alignment: .leading)
      .background(Theme.aubergineTint, in: RoundedRectangle(cornerRadius: 12))
  }
}

/// The short version of the privacy policy: what we keep, what we never collect, who else can see it.
/// Full at the top of Privacy; `compact` is the one-screen version for first open (sign up uses privacy.signup.note).
/// Words: privacy.* in copy.json, shared with web (PrivacySummary.jsx) and Android (PrivacySummary).
struct PrivacySummaryView: View {
  var compact = false

  private func rows(_ prefix: String, _ count: Int) -> [(title: String, body: String)] {
    (1...count).map { (Copy.text("\(prefix).\($0).title"), Copy.text("\(prefix).\($0)")) }
  }

  private func header(_ id: String) -> some View {
    Text(Copy.text(id).uppercased())
      .font(Theme.sectionHeader)
      .tracking(0.6)
      .foregroundStyle(Theme.muted)
      .padding(.top, compact ? 4 : 10)
  }

  private func promise(_ id: String) -> some View {
    Text(Copy.text(id))
      .font(Theme.action)
      .foregroundStyle(Theme.bg)
      .padding(.horizontal, 14)
      .padding(.vertical, compact ? 12 : 14)
      .frame(maxWidth: .infinity, alignment: .leading)
      .background(Theme.ink, in: RoundedRectangle(cornerRadius: 14))
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
        .padding(.vertical, 10)
        if index < items.count - 1 { Divider().overlay(Theme.line) }
      }
    }
    .accessibilityElement(children: .contain)
  }

  private func bullet(_ text: Text) -> some View {
    HStack(alignment: .firstTextBaseline, spacing: 8) {
      Text("•").foregroundStyle(Theme.muted)
      text.fixedSize(horizontal: false, vertical: true)
    }
    .font(Theme.body)
    .foregroundStyle(Theme.ink)
  }

  /// One screen: the don't-sell line, four bullets, the household note, one "never" sentence.
  private var short: some View {
    VStack(alignment: .leading, spacing: 8) {
      promise("privacy.short.sell")
      header("privacy.short.keep.title")
      VStack(alignment: .leading, spacing: 4) {
        bullet(Text(Copy.text("privacy.short.keep.1")))
        bullet(Text(Copy.text("privacy.short.keep.2")))
        bullet(Text(Copy.text("privacy.short.keep.3") + " ")
          + Text(Copy.text("privacy.short.keep.3.note")).foregroundColor(Theme.muted))
        bullet(Text(Copy.text("privacy.short.keep.4")))
      }
      HouseholdSharingNote()
      header("privacy.short.never.title")
      Text(Copy.text("privacy.short.never"))
        .font(Theme.body)
        .foregroundStyle(Theme.ink)
        .fixedSize(horizontal: false, vertical: true)
    }
  }

  private var full: some View {
    VStack(alignment: .leading, spacing: 8) {
      promise("privacy.sell")

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

      header("privacy.shared.title")
      list(rows("privacy.shared", 3))
    }
  }

  var body: some View {
    if compact { short } else { full }
  }
}
