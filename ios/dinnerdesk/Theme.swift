import CoreText
import SwiftUI

/// One look for the whole app: warm background, aubergine for dominant actions and
/// primary text, deep coral for link/text actions, and subtle tints for specialized UI states.
///
// Custom Extension for Hex
extension Color {
  init(hex: UInt) {
    self.init(
      .sRGB,
      red: Double((hex >> 16) & 0xff) / 255,
      green: Double((hex >> 8) & 0xff) / 255,
      blue: Double(hex & 0xff) / 255
    )
  }
}

enum Theme {
  // MARK: - Core Palette
  static let bg = Color(red: 255 / 255, green: 251 / 255, blue: 246 / 255)  // #FFFBF6 Page background
  static let surface = Color(red: 255 / 255, green: 253 / 255, blue: 249 / 255)  // #FFFDF9 Cards, list rows, tab bar
  static let line = Color(red: 236 / 255, green: 226 / 255, blue: 220 / 255)  // #ECE2DC Hairlines, chip borders

  static let ink = Color(red: 74 / 255, green: 22 / 255, blue: 70 / 255)  // #4A1646 Aubergine: Titles, main buttons, active tabs
  static let muted = Color(red: 122 / 255, green: 106 / 255, blue: 118 / 255)  // #7A6A76 Subtitles, counts

  static let accent = Color(red: 194 / 255, green: 70 / 255, blue: 42 / 255)  // #C2462A Deep Coral: Text links (+ Add a meal, Edit)

  // MARK: - Tints
  static let aubergineTint = Color(red: 241 / 255, green: 231 / 255, blue: 239 / 255)  // #F1E7EF Tips, badges, quiet chips

  // MARK: - Legacy / UI Helpers
  static let ok = Color(red: 63 / 255, green: 107 / 255, blue: 74 / 255)  // #3F6B4A Kept for validation / system status if needed

  /// Quieter, unselected chips use the newly introduced pale aubergine tint.
  static let chip = aubergineTint

  // MARK: - Typography
  static let bigTitle = Font.custom("Fraunces72pt-Bold", size: 34, relativeTo: .largeTitle)
  static let tourTitle = Font.custom("Fraunces72pt-SemiBold", size: 28, relativeTo: .title)
  static let recipeTitle = Font.custom("Fraunces72pt-SemiBold", size: 26, relativeTo: .title2)
  static let title = Font.custom("DMSans-Bold", size: 20, relativeTo: .title3)
  static let action = Font.custom("DMSans-SemiBold", size: 17, relativeTo: .body)
  static let mealName = action
  static let recipeCardName = Font.custom("DMSans-SemiBold", size: 15, relativeTo: .subheadline)
  static let rowTitle = Font.custom("DMSans-Medium", size: 17, relativeTo: .body)
  static let body = Font.custom("DMSans-Regular", size: 17, relativeTo: .body)
  static let chipLabel = Font.custom("DMSans-SemiBold", size: 15, relativeTo: .subheadline)
  static let subtitle = Font.custom("DMSans-Regular", size: 13, relativeTo: .footnote)
  static let count = Font.custom("DMSans-Medium", size: 13, relativeTo: .footnote)
  /// Small all-caps section headers (aisles, days, settings groups). Scales with footnote text,
  /// so it stays smaller than row titles at every text size.
  static let sectionHeader = Font.custom("DMSans-Bold", size: 14, relativeTo: .footnote)

  static func registerFonts() {
    let fonts = [
      ("Fraunces_72pt-Bold", "Fraunces72pt-Bold"),
      ("Fraunces_72pt-SemiBold", "Fraunces72pt-SemiBold"),
      ("DMSans-Regular", "DMSans-Regular"),
      ("DMSans-Medium", "DMSans-Medium"),
      ("DMSans-SemiBold", "DMSans-SemiBold"),
      ("DMSans-Bold", "DMSans-Bold"),
    ]
    for (file, name) in fonts {
      guard let url = Bundle.main.url(forResource: file, withExtension: "ttf") else {
        preconditionFailure("Missing bundled font: \(file).ttf")
      }
      var error: Unmanaged<CFError>?
      guard CTFontManagerRegisterFontsForURL(url as CFURL, .process, &error) else {
        preconditionFailure(
          "Cannot register \(file): \(String(describing: error?.takeRetainedValue()))")
      }
      guard UIFont(name: name, size: 17) != nil else {
        preconditionFailure("Font is unavailable after registration: \(name)")
      }
    }
  }

  static func scaledFont(_ name: String, size: CGFloat, style: UIFont.TextStyle) -> UIFont {
    guard let font = UIFont(name: name, size: size) else {
      preconditionFailure("Required font is unavailable: \(name)")
    }
    return UIFontMetrics(forTextStyle: style).scaledFont(for: font)
  }

  static func configureAppearance() {
    let titleAttrs: [NSAttributedString.Key: Any] = [
      .foregroundColor: UIColor(ink)
    ]

    // Fraunces on the expanded title. Inline title color stays on this global
    // scroll-edge appearance so pushed inline screens keep a visible title.
    let largeAttrs = largeTitleAttributes
    // A filled scroll-edge bar sits above the large title and leaves a tall empty
    // band under the status bar. The resting bar stays clear so the title can sit up.
    let navigation = UINavigationBarAppearance()
    if #available(iOS 26, *) {
      navigation.configureWithDefaultBackground()
    } else {
      navigation.configureWithOpaqueBackground()
      navigation.backgroundColor = UIColor(bg)
      navigation.shadowColor = UIColor(line)
    }
    navigation.titleTextAttributes = titleAttrs
    navigation.largeTitleTextAttributes = largeAttrs
    let edge = UINavigationBarAppearance()
    edge.configureWithTransparentBackground()
    edge.shadowColor = .clear
    edge.titleTextAttributes = titleAttrs
    edge.largeTitleTextAttributes = largeAttrs
    UINavigationBar.appearance().standardAppearance = navigation
    UINavigationBar.appearance().scrollEdgeAppearance = edge
    UINavigationBar.appearance().compactAppearance = navigation
    let buttonFont = scaledFont("DMSans-SemiBold", size: 17, style: .body)
    UIBarButtonItem.appearance().setTitleTextAttributes([.font: buttonFont], for: .normal)
    UIBarButtonItem.appearance().setTitleTextAttributes([.font: buttonFont], for: .highlighted)
    let bar = UITabBarAppearance()
    // iOS 26 draws the selected tab as a glass pill. On top of our opaque bar, and with
    // labels and badges that grew with Dynamic Type, the pill spilled past the bar and
    // clipped the Grocery badge (#23). Use the system bar there, like the navigation bar.
    if #available(iOS 26, *) {
      bar.configureWithDefaultBackground()
    } else {
      bar.configureWithOpaqueBackground()
      bar.backgroundColor = UIColor(surface)
      bar.shadowColor = UIColor(line)
    }
    // Tab labels and badges keep a fixed size, like the system's: at large text, a long
    // press shows the enlarged label (Large Content Viewer) instead of the bar growing.
    let tabFont = UIFont(name: "DMSans-Medium", size: 10) ?? .systemFont(ofSize: 10, weight: .medium)
    let selectedTabFont = UIFont(name: "DMSans-Bold", size: 10) ?? .systemFont(ofSize: 10, weight: .bold)
    let badgeFont = UIFont(name: "DMSans-Medium", size: 12) ?? .systemFont(ofSize: 12, weight: .medium)
    for item in [
      bar.stackedLayoutAppearance, bar.inlineLayoutAppearance, bar.compactInlineLayoutAppearance,
    ] {
      item.normal.badgeBackgroundColor = UIColor(muted)
      item.selected.badgeBackgroundColor = UIColor(accent)
      item.normal.badgeTextAttributes = [.font: badgeFont]
      item.selected.badgeTextAttributes = [.font: badgeFont]
      item.normal.iconColor = UIColor(muted)
      item.normal.titleTextAttributes = [.font: tabFont, .foregroundColor: UIColor(muted)]
      item.selected.titleTextAttributes = [.font: selectedTabFont, .foregroundColor: UIColor(accent)]
    }
    UITabBar.appearance().standardAppearance = bar
    UITabBar.appearance().scrollEdgeAppearance = bar
  }

  /// Expanded-title attributes. Inline `titleTextAttributes` are intentionally absent
  /// from the per-bar scroll-edge appearance that uses this.
  static var largeTitleAttributes: [NSAttributedString.Key: Any] {
    [
      .font: scaledFont("Fraunces72pt-Bold", size: 34, style: .largeTitle),
      .foregroundColor: UIColor(ink),
    ]
  }

  /// Transparent scroll-edge bar for an expanded large title. No inline title
  /// attributes, so UIKit can drop the compact-title row while the large title shows.
  static func largeTitleScrollEdgeAppearance() -> UINavigationBarAppearance {
    let edge = UINavigationBarAppearance()
    edge.configureWithTransparentBackground()
    edge.shadowColor = .clear
    edge.largeTitleTextAttributes = largeTitleAttributes
    return edge
  }
}

// MARK: - Shared list chrome
// Reused on Grocery, Kitchen, More, Settings, Pantry, Plan drafts, Tour.

/// Section header that stops pinning once the type size would eat the screen.
struct ThemeSection<Content: View, Footer: View>: View {
  let title: String
  let content: Content
  let footer: Footer
  @Environment(\.dynamicTypeSize) private var typeSize

  init(
    _ title: String, @ViewBuilder content: () -> Content, @ViewBuilder footer: () -> Footer
  ) {
    self.title = title
    self.content = content()
    self.footer = footer()
  }

  private var pin: Bool { typeSize < .accessibility1 }

  var body: some View {
    if pin {
      Section {
        content
      } header: {
        ThemeHeader(title)
      } footer: {
        footer
      }
    } else {
      Section {
        ThemeHeader(title)
          .listRowInsets(EdgeInsets(top: 18, leading: 20, bottom: 4, trailing: 20))
          .themeBareRow()
        content
      } footer: {
        footer
      }
    }
  }
}

extension ThemeSection where Footer == EmptyView {
  init(_ title: String, @ViewBuilder content: () -> Content) {
    self.init(title, content: content, footer: { EmptyView() })
  }
}

/// Small grey all-caps section header, like PRODUCE on the grocery list.
struct ThemeHeader: View {
  let text: String

  init(_ text: String) {
    self.text = text
  }

  var body: some View {
    Text(text.uppercased())
      .font(Theme.sectionHeader)
      .tracking(0.8)
      .foregroundStyle(Theme.muted.opacity(0.85))
      .textCase(nil)
      .padding(.top, 6)
  }
}

/// Grey outline icon, bold label, optional grey value on the right.
struct ThemeIconRow: View {
  let title: String
  let systemImage: String
  var value: String?
  @Environment(\.dynamicTypeSize) private var typeSize

  var body: some View {
    if typeSize.isAccessibilitySize {
      // Large text: the value goes under the title, so the title keeps the full width
      // instead of being squeezed into a column beside "5 aisles".
      HStack(alignment: .top, spacing: 14) {
        icon.padding(.top, 6)
        VStack(alignment: .leading, spacing: 2) {
          titleText
          if let value { valueText(value) }
        }
        Spacer(minLength: 0)
      }
      .frame(minHeight: 44)
    } else {
      HStack(spacing: 14) {
        icon
        titleText
        Spacer(minLength: 8)
        if let value { valueText(value).lineLimit(1) }
      }
      .frame(minHeight: 44)
    }
  }

  private var icon: some View {
    Image(systemName: systemImage)
      .font(.system(size: 19))
      .foregroundStyle(Theme.muted)
      .frame(width: 26)
      .accessibilityHidden(true)
  }

  private var titleText: some View {
    Text(title)
      .font(Theme.mealName)
      .foregroundStyle(Theme.ink)
      .fixedSize(horizontal: false, vertical: true)
  }

  private func valueText(_ value: String) -> some View {
    Text(value)
      .foregroundStyle(Theme.muted)
      .monospacedDigit()
  }
}

/// "+ Add item" row in the accent color. Pantry, Always checked off, Stores aisles, Substitutions.
struct ThemeAddRow: View {
  let title: String
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      Label(title, systemImage: "plus")
        .font(Theme.mealName)
        .foregroundStyle(Theme.accent)
    }
  }
}

extension View {
  /// `.toolbarTitleDisplayMode(.large)` and a per-bar scroll-edge appearance that
  /// hides the compact title row only while this screen is visible.
  func largeNavigationTitle() -> some View {
    toolbarTitleDisplayMode(.large)
      .background {
        LargeTitleScrollEdge()
          .allowsHitTesting(false)
      }
  }

  /// Plain list on the app background with hairline separators.
  func themeList() -> some View {
    listStyle(.plain)
      .scrollContentBackground(.hidden)
      .background(Theme.bg)
      .environment(\.defaultMinListRowHeight, 56)
  }

  /// Row background and separator color for rows in a `themeList`.
  func themeRows() -> some View {
    listRowBackground(Theme.bg)
      .listRowSeparatorTint(Theme.line)
  }

  /// A row that shouldn't look like a row (banners, explanations, chip clouds).
  func themeBareRow() -> some View {
    listRowBackground(Theme.bg)
      .listRowSeparator(.hidden)
  }

  /// Forms use the same page color as the lists, including the grouped card behind them.
  func themeForm() -> some View {
    scrollContentBackground(.hidden)
      .background(Theme.bg)
  }
}

/// Installs `Theme.largeTitleScrollEdgeAppearance()` on this screen's navigation bar
/// for as long as the screen is visible, then puts the global scroll-edge appearance back.
private struct LargeTitleScrollEdge: UIViewControllerRepresentable {
  func makeUIViewController(context: Context) -> LargeTitleScrollEdgeController {
    LargeTitleScrollEdgeController()
  }

  func updateUIViewController(_ controller: LargeTitleScrollEdgeController, context: Context) {}
}

private final class LargeTitleScrollEdgeController: UIViewController {
  override func loadView() {
    let view = UIView()
    view.backgroundColor = .clear
    view.isUserInteractionEnabled = false
    self.view = view
  }

  override func viewWillAppear(_ animated: Bool) {
    super.viewWillAppear(animated)
    applyLargeTitleScrollEdge()
  }

  override func viewDidAppear(_ animated: Bool) {
    super.viewDidAppear(animated)
    // Retry when the bar was not in the hierarchy yet, and after a covered
    // screen's viewWillDisappear restored the global appearance.
    applyLargeTitleScrollEdge()
  }

  override func viewWillDisappear(_ animated: Bool) {
    super.viewWillDisappear(animated)
    guard let bar = navigationController?.navigationBar else { return }
    bar.scrollEdgeAppearance = UINavigationBar.appearance().scrollEdgeAppearance
  }

  private func applyLargeTitleScrollEdge() {
    guard let bar = navigationController?.navigationBar else { return }
    bar.scrollEdgeAppearance = Theme.largeTitleScrollEdgeAppearance()
  }
}
