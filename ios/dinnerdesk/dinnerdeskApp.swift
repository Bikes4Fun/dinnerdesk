import SwiftUI

@main
struct dinnerdeskApp: App {
  init() {
    Theme.registerFonts()
    Theme.configureAppearance()
    Copy.validate()
    
    // Initialize the connectivity bridge on app boot-up
    _ = WatchConnectivityManager.shared
  }

  var body: some Scene {
    WindowGroup {
      ContentView()
        .font(Theme.body)
        .onReceive(
          NotificationCenter.default.publisher(
            for: UIContentSizeCategory.didChangeNotification
          )
        ) { _ in
          Theme.configureAppearance()
        }
    }
  }
}
