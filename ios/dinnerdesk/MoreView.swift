import SwiftUI

/// Everything that isn't Plan, Recipes or Grocery: one list of grey-icon rows in a shared settings layout.
struct MoreView: View {
  @EnvironmentObject private var session: Session

  var body: some View {
    NavigationStack {
      List {
        Section {
          NavigationLink {
            PrepView()
          } label: {
            ThemeIconRow(title: "Weekend prep", systemImage: "list.bullet.clipboard")
          }
          NavigationLink {
            KitchenView()
          } label: {
            ThemeIconRow(title: "My kitchen and Groceries", systemImage: "refrigerator")
          }
          NavigationLink {
            TasteLabView()
          } label: {
            ThemeIconRow(title: "Taste Lab", systemImage: "hand.draw")
          }
          Button {
            session.showTour = true
          } label: {
            ThemeIconRow(title: "Quick start tour", systemImage: "arrow.counterclockwise")
          }
          .accessibilityHint("Replays the first-run tour")
          NavigationLink {
              SettingsView()
            } label: {
              ThemeIconRow(title: "Settings", systemImage: "gearshape")
            }
        }
        .themeRows()
      }
      .themeList()
      .tint(Theme.accent)
      .navigationTitle("More")
      .largeNavigationTitle()
    }
  }
}

