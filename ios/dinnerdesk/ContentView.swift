import SwiftUI
import UIKit

enum AppTab: Hashable {
  case plan, recipes, grocery, prep, more
}

private struct SelectTabKey: EnvironmentKey {
  static let defaultValue: (AppTab) -> Void = { _ in }
}

extension EnvironmentValues {
  var selectTab: (AppTab) -> Void {
    get { self[SelectTabKey.self] }
    set { self[SelectTabKey.self] = newValue }
  }
}

struct ContentView: View {
  @StateObject private var store = Store()
  @Environment(\.dynamicTypeSize) private var textSize
  // @State private var planNavigationID = UUID()
  @State private var navigationIDs: [AppTab: UUID] = [:]
  @State private var tab: AppTab = .plan

  /// Meals on this week's plan that aren't cooked yet.
  private var mealsLeft: Int {
    (store.plan?.slots ?? []).filter { !$0.cooked }.count
  }

  /// Grocery items still to buy (staples and checked items don't count).
  private var itemsLeft: Int {
    store.grocery.filter { !$0.checked && !$0.neverShop }.count
  }

  @Environment(\.scenePhase) private var scenePhase

  var body: some View {
    AuthGate {
      TabView(selection: $tab) {
        PlanView()
          .id(navigationIDs[.plan])
          .tabItem { Label("Plan", systemImage: "calendar") }
          .badge(mealsLeft)
          .tag(AppTab.plan)
        RecipesView()
          .id(navigationIDs[.recipes])
          .tabItem { Label("Recipes", systemImage: "book") }
          .tag(AppTab.recipes)
        GroceryView()
          .id(navigationIDs[.grocery])
          .tabItem { Label("Grocery", systemImage: "cart") }
          .badge(itemsLeft)
          .tag(AppTab.grocery)
        if UIScreen.main.bounds.width >= 390 && !textSize.isAccessibilitySize {
          NavigationStack { PrepView() }
            .id(navigationIDs[.prep])
            .tabItem { Label("Prep", systemImage: "list.bullet.clipboard") }
            .tag(AppTab.prep)
        }
        MoreView()
          .id(navigationIDs[.more])
          .tabItem { Label("More", systemImage: "ellipsis.circle") }
          .tag(AppTab.more)
      }
      .tint(Theme.accent)
      // iOS 18+ cross-fades tab content. Keep switches immediate.
      .animation(nil, value: tab)
      .background {
        InstantTabSwitch()
          .frame(width: 0, height: 0)
      }
      .environmentObject(store)
      .environment(\.selectTab) { showTab($0) }
      .task { await store.loadAll() }
       .onChange(of: tab) { previous, _ in
        navigationIDs[previous] = UUID()
        store.error = nil
        store.proposalError = nil
      }
      .onChange(of: scenePhase) { _, next in
        if next == .background {
          showTab(.plan)
        }
        // planNavigationID = UUID(); navigationIDs[.plan] = planNavigationID }
      }
    }
  }

  /// Same tab change as `tab =`, without the system cross-fade.
  private func showTab(_ next: AppTab) {
    var transaction = Transaction(animation: nil)
    transaction.disablesAnimations = true
    withTransaction(transaction) { tab = next }
  }
}

/// Stops UITabBarController's cross-fade. SwiftUI's `.animation(nil)` does not reach it.
private struct InstantTabSwitch: UIViewRepresentable {
  func makeUIView(context: Context) -> TabSwitchProbe {
    let view = TabSwitchProbe()
    view.isHidden = true
    view.isUserInteractionEnabled = false
    view.onWindow = { [weak view] in context.coordinator.install(from: view) }
    return view
  }

  func updateUIView(_ uiView: TabSwitchProbe, context: Context) {
    uiView.onWindow = { [weak uiView] in context.coordinator.install(from: uiView) }
    context.coordinator.install(from: uiView)
  }

  func makeCoordinator() -> Coordinator { Coordinator() }

  final class Coordinator: NSObject, UITabBarControllerDelegate {
    private var next: (any UITabBarControllerDelegate)?
    private var nextObject: NSObject?
    private var checkingResponds = false

    func install(from view: UIView?) {
      guard let tabBar = view?.nearestTabBarController() else { return }
      if tabBar.delegate === self { return }
      guard let existing = tabBar.delegate as? NSObject else { return }
      next = tabBar.delegate
      nextObject = existing
      tabBar.delegate = self
    }

    func tabBarController(_ tabBarController: UITabBarController, shouldSelectTab tab: UITab)
      -> Bool
    {
      guard tabBarController.selectedTab !== tab else {
        return next?.tabBarController?(tabBarController, shouldSelectTab: tab) ?? true
      }
      let allowed = next?.tabBarController?(tabBarController, shouldSelectTab: tab) ?? true
      guard allowed else { return false }
      let previous = tabBarController.selectedTab
      UIView.performWithoutAnimation {
        tabBarController.selectedTab = tab
      }
      next?.tabBarController?(tabBarController, didSelectTab: tab, previousTab: previous)
      return false
    }

    func tabBarController(
      _ tabBarController: UITabBarController,
      shouldSelect viewController: UIViewController
    ) -> Bool {
      guard tabBarController.selectedViewController !== viewController else {
        return next?.tabBarController?(tabBarController, shouldSelect: viewController) ?? true
      }
      let allowed = next?.tabBarController?(tabBarController, shouldSelect: viewController) ?? true
      guard allowed else { return false }
      UIView.performWithoutAnimation {
        tabBarController.selectedViewController = viewController
      }
      next?.tabBarController?(tabBarController, didSelect: viewController)
      return false
    }

    override func responds(to aSelector: Selector!) -> Bool {
      if super.responds(to: aSelector) { return true }
      if checkingResponds { return false }
      checkingResponds = true
      let answer = nextObject?.responds(to: aSelector) ?? false
      checkingResponds = false
      return answer
    }

    override func forwardingTarget(for aSelector: Selector!) -> Any? {
      if super.responds(to: aSelector) { return nil }
      return nextObject
    }
  }
}

private final class TabSwitchProbe: UIView {
  var onWindow: (() -> Void)?

  override func didMoveToWindow() {
    super.didMoveToWindow()
    guard window != nil else { return }
    onWindow?()
  }
}

extension UIView {
  fileprivate func nearestTabBarController() -> UITabBarController? {
    var responder: UIResponder? = self
    while let current = responder {
      if let tabBar = current as? UITabBarController { return tabBar }
      if let controller = current as? UIViewController, let tabBar = controller.tabBarController {
        return tabBar
      }
      responder = current.next
    }
    guard let root = window?.rootViewController else { return nil }
    return Self.findTabBar(in: root)
  }

  private static func findTabBar(in controller: UIViewController) -> UITabBarController? {
    if let tabBar = controller as? UITabBarController { return tabBar }
    for child in controller.children {
      if let found = findTabBar(in: child) { return found }
    }
    return nil
  }
}

#Preview {
  ContentView()
}
