import SwiftUI

/// Everything that isn't Plan, Recipes or Grocery: one list of grey-icon rows in a shared settings layout.
struct MoreView: View {
  @EnvironmentObject private var session: Session
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
          NavigationLink {
            TasteLabView()
          } label: {
            ThemeIconRow(title: "Taste Lab", systemImage: "hand.draw")
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
              ThemeIconRow(title: "Account and More", systemImage: "gearshape")
            }
          
          NavigationLink {
            PrepView()
          } label: {
            ThemeIconRow(title: "Weekend prep", systemImage: "list.bullet.clipboard")
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

