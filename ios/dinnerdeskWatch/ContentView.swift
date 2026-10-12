import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var store: Store
    @ObservedObject private var connection = WatchConnectivityManager.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Group {
            if connection.hasPhoneSession {
                TabView {
                    WatchPlanView()
                    WatchGroceryView()
                }
                .tabViewStyle(.page)
            } else {
                ContentUnavailableView {
                    Label("Sign in on iPhone", systemImage: "iphone")
                } description: {
                    Text("Open Dinnerdesk on your paired iPhone to sync your account.")
                } actions: {
                    Button("Try again") { connection.requestPhoneSession() }
                }
            }
        }
        .task { connection.requestPhoneSession() }
        .task(id: connection.sessionRevision) {
            guard connection.sessionRevision > 0 else { return }
            await store.switchAccount(load: connection.hasPhoneSession)
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { connection.requestPhoneSession() }
        }
    }
}
