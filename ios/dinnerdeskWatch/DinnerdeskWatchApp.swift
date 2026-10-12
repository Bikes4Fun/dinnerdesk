import SwiftUI

@main
struct DinnerdeskWatchApp: App {
    @StateObject private var store = Store()
    
    init() {
        _ = WatchConnectivityManager.shared
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
        }
    }
}
