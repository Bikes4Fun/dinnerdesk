import SwiftUI

/// Everything that isn't Plan, Recipes or Grocery: one list of grey-icon rows in a shared settings layout.
struct MoreView: View {
  @EnvironmentObject private var session: Session
  @Environment(\.dynamicTypeSize) private var textSize
  @State private var isBeta = false

  var body: some View {
    NavigationStack {
      List {
        Section {

          NavigationLink {
            KitchenView()
          } label: {
            ThemeIconRow(title: "My Kitchen", systemImage: "refrigerator")
          }
          if !ContentView.showsPrepTab(textSize) {
            NavigationLink {
              PrepView()
            } label: {
              ThemeIconRow(title: "Weekend prep", systemImage: "list.bullet.clipboard")
            }
          }
          NavigationLink {
            TasteLabView()
          } label: {
            ThemeIconRow(title: "Taste Lab", systemImage: "hand.draw")
          }
          NavigationLink {
            AccountView()
          } label: {
            ThemeIconRow(
              title: "Account & security",
              systemImage: "person.crop.circle",
              value: session.status?.email ?? "Guest"
            )
          }
          NavigationLink {
            FeedbackView()
          } label: {
            ThemeIconRow(title: "Report a bug or suggest a feature", systemImage: "exclamationmark.bubble")
          }
          
          if isBeta {
            Button {
              session.showFeedbackTip = true
            } label: {
              ThemeIconRow(title: "Send a screenshot to the developer", systemImage: "exclamationmark.bubble")
            }
          }
          NavigationLink {
              SettingsView()
            } label: {
              ThemeIconRow(title: "More", systemImage: "gearshape")
            }
          
        }
        .themeRows()
      }
      .themeList()
      .tint(Theme.accent)
      .safeAreaInset(edge: .top, spacing: 0) { TabHeader("More") }
      .task { isBeta = await FeedbackTipView.isBeta() }
    }
  }
}

