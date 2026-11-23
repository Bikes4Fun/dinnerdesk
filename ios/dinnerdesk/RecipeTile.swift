import SwiftUI

// MARK: - RecipeTile (shared template — not wired to screens yet)
//
// Single recipe tile for the whole app. Future callers: Plan list/grid, Recipes browse,
// My Recipes, suggested plan, swap picker, Taste Lab (larger + swipe wrapper), Hidden,
// plan strip, grocery “used in” rows.
//
// Structure:
//   1. Photo (* square crop, shared corner radius; options: size, opacity, open-on-tap)
//   2. Overlays on the photo via RecipeTilePhotoOverlay (* standard circle chrome;
//      options: shown, where, interactive vs static; content inside the circle)
//   3. Body = name (* RecipeCardName) + meta (view under|beside; named content types)
//   4. Context menu (option): press-and-hold; Favorite / plan / To try / Hide / cooked + extras
//
// * = always-on default. Without * = page option.
// REVIEW: defaults below — cook time + kitchen-tested meta on with reserved height;
//         servings off; no overlays / no context menu until a page opts in.
// REVIEW: kitchen-tested as photo badge vs body meta line — both supported; pick per page.
// REVIEW: schedule meta — text vs control when Plan migrates.

/// Where an overlay sits on the photo.
enum RecipeTileCorner: Sendable {
  case topLeading, topTrailing, bottomLeading, bottomTrailing, center
}

/// Interactive button vs static badge — same circle chrome either way.
enum RecipeTileOverlayMode: Sendable {
  case interactive, staticBadge
}

/// One entry in the hold-to-open / context menu. Standard kinds or a page-passed extra.
struct RecipeTileMenuItem: Identifiable {
  let id: String
  let title: String
  var role: ButtonRole? = nil
  let action: () -> Void

  static func favorite(on: Bool, action: @escaping () -> Void) -> RecipeTileMenuItem {
    RecipeTileMenuItem(id: "favorite", title: on ? "Unfavorite" : "Favorite", action: action)
  }
  static func plan(on: Bool, action: @escaping () -> Void) -> RecipeTileMenuItem {
    RecipeTileMenuItem(
      id: "plan", title: on ? Copy.text("ui.remove.from.plan") : Copy.text("ui.add.to.plan"), action: action)
  }
  static func toTry(on: Bool, action: @escaping () -> Void) -> RecipeTileMenuItem {
    // Copy: "To try" (not "To Try"), matching current UI.
    RecipeTileMenuItem(
      id: "toTry", title: on ? Copy.text("ui.remove.from.to.try") : Copy.text("ui.to.try.2"), action: action)
  }
  static func hide(on: Bool, action: @escaping () -> Void) -> RecipeTileMenuItem {
    RecipeTileMenuItem(
      id: "hide", title: on ? Copy.text("ui.unhide.recipe") : Copy.text("ui.hide.recipe"),
      role: on ? nil : .destructive, action: action)
  }
  static func cooked(on: Bool, action: @escaping () -> Void) -> RecipeTileMenuItem {
    RecipeTileMenuItem(
      id: "cooked", title: on ? Copy.text("ui.mark.as.not.cooked") : Copy.text("ui.mark.as.cooked"), action: action)
  }
  /// Page-specific action not in the standard set.
  static func extra(id: String, title: String, role: ButtonRole? = nil, action: @escaping () -> Void)
    -> RecipeTileMenuItem
  {
    RecipeTileMenuItem(id: id, title: title, role: role, action: action)
  }
}

/// Meta under/beside the name. Opted-in types reserve height even when a recipe lacks that value.
struct RecipeTileMeta: Sendable {
  /// REVIEW: default under; beside for list/row layouts.
  var placement: Placement = .under
  var showCookTime = true
  var showKitchenTested = true
  var showServings = false
  var showYourSelection = false
  var showSchedule = false
  var servings: Int? = nil
  var yourSelection = false
  var scheduleLabel: String? = nil

  enum Placement: Sendable {
    case under, beside
  }
}

// MARK: - Photo overlay base (* circle)

/// Universal overlay chrome: standard-size circle, padding, hit target.
/// Content (heart, +, seal, …) goes inside; do not invent a different corner/chrome per type.
struct RecipeTilePhotoOverlay<Content: View>: View {
  var corner: RecipeTileCorner = .topTrailing
  var mode: RecipeTileOverlayMode = .interactive
  var accessibilityLabel: String?
  var action: (() -> Void)?
  @ViewBuilder var content: () -> Content

  var body: some View {
    Group {
      if mode == .interactive, let action {
        Button(action: action) { chrome }.buttonStyle(.borderless)
      } else {
        chrome.accessibilityHidden(mode == .staticBadge && accessibilityLabel == nil)
      }
    }
    .accessibilityLabel(accessibilityLabel ?? "")
    .accessibilityAddTraits(mode == .interactive ? .isButton : [])
  }

  private var chrome: some View {
    // * Standard circle + 44pt hit target. REVIEW: 28pt glyph circle matches browse add/heart.
    content()
      .frame(width: 28, height: 28)
      .background(Color.white, in: Circle())
      .shadow(color: .black.opacity(0.18), radius: 2, y: 1)
      .frame(width: 44, height: 44)
      .contentShape(Rectangle())
      .padding(4)
  }
}

// MARK: - Overlay content wrappers

/// Positions overlay content in a corner of the photo (fill the photo, then align).
private struct RecipeTileOverlaySlot<Content: View>: View {
  var corner: RecipeTileCorner
  @ViewBuilder var content: () -> Content

  var body: some View {
    Color.clear
      .frame(maxWidth: .infinity, maxHeight: .infinity)
      .overlay(alignment: corner.alignment) { content() }
  }
}

extension RecipeTileCorner {
  var alignment: Alignment {
    switch self {
    case .topLeading: return .topLeading
    case .topTrailing: return .topTrailing
    case .bottomLeading: return .bottomLeading
    case .bottomTrailing: return .bottomTrailing
    case .center: return .center
    }
  }
}

struct RecipeTileAddButton: View {
  var onPlan: Bool
  var action: () -> Void
  var corner: RecipeTileCorner = .topTrailing

  var body: some View {
    RecipeTileOverlaySlot(corner: corner) {
      RecipeTilePhotoOverlay(
        corner: corner, mode: .interactive,
        accessibilityLabel: onPlan ? Copy.text("ui.remove.from.this.plan") : Copy.text("ui.add.to.this.plan"),
        action: action
      ) {
        // Glyph inside * circle chrome (not circle.fill — that would double the ring).
        Image(systemName: onPlan ? "checkmark" : "plus")
          .font(.system(size: 14, weight: .bold))
          .foregroundStyle(onPlan ? Theme.accent : Theme.ink)
      }
    }
  }
}

struct RecipeTileHeartButton: View {
  var on: Bool
  var action: () -> Void
  var corner: RecipeTileCorner = .topLeading

  var body: some View {
    RecipeTileOverlaySlot(corner: corner) {
      RecipeTilePhotoOverlay(
        corner: corner, mode: .interactive,
        accessibilityLabel: on ? Copy.text("ui.remove.from.your.favorites") : Copy.text("ui.save.to.your.favorites"),
        action: action
      ) {
        Image(systemName: on ? "heart.fill" : "heart")
          .font(.system(size: 14, weight: .semibold))
          .foregroundStyle(on ? Color.red : Theme.muted)
      }
    }
  }
}

struct RecipeTileSwapButton: View {
  var action: () -> Void
  var disabled = false
  var corner: RecipeTileCorner = .topTrailing

  var body: some View {
    RecipeTileOverlaySlot(corner: corner) {
      RecipeTilePhotoOverlay(
        corner: corner, mode: .interactive,
        accessibilityLabel: Copy.text("ui.swap.meal"),
        action: disabled ? nil : action
      ) {
        Image(systemName: "arrow.triangle.2.circlepath")
          .font(.system(size: 13, weight: .semibold))
          .foregroundStyle(Theme.accent)
          .opacity(disabled ? 0.4 : 1)
      }
      .disabled(disabled)
      .opacity(disabled ? 0.4 : 1)
    }
  }
}

struct RecipeTileSaveForLaterButton: View {
  var on: Bool
  var action: () -> Void
  var corner: RecipeTileCorner = .topLeading

  var body: some View {
    RecipeTileOverlaySlot(corner: corner) {
      RecipeTilePhotoOverlay(
        corner: corner, mode: .interactive,
        accessibilityLabel: on ? Copy.text("ui.remove.from.to.try") : Copy.text("ui.save.to.to.try"),
        action: action
      ) {
        Image(systemName: on ? "bookmark.fill" : "bookmark")
          .font(.system(size: 14, weight: .semibold))
          .foregroundStyle(on ? Theme.accent : Theme.muted)
      }
    }
  }
}

struct RecipeTileCookedButton: View {
  var on: Bool
  var action: () -> Void
  var corner: RecipeTileCorner = .topTrailing

  var body: some View {
    RecipeTileOverlaySlot(corner: corner) {
      RecipeTilePhotoOverlay(
        corner: corner, mode: .interactive,
        accessibilityLabel: on ? Copy.text("ui.mark.as.not.cooked") : Copy.text("ui.mark.as.cooked"),
        action: action
      ) {
        Image(systemName: on ? "checkmark.circle.fill" : "circle")
          .font(.system(size: 22))
          .foregroundStyle(on ? Theme.accent : Theme.muted)
      }
    }
  }
}

struct RecipeTileFlagButton: View {
  var action: () -> Void
  var corner: RecipeTileCorner = .topTrailing

  var body: some View {
    RecipeTileOverlaySlot(corner: corner) {
      RecipeTilePhotoOverlay(
        corner: corner, mode: .interactive,
        accessibilityLabel: Copy.text("ui.report.photo"),
        action: action
      ) {
        Image(systemName: "flag")
          .font(.system(size: 13, weight: .semibold))
          .foregroundStyle(Theme.muted)
      }
    }
  }
}

struct RecipeTileKitchenTestedBadge: View {
  var corner: RecipeTileCorner = .topLeading

  var body: some View {
    RecipeTileOverlaySlot(corner: corner) {
      RecipeTilePhotoOverlay(
        corner: corner, mode: .staticBadge,
        accessibilityLabel: Copy.text("recipe.reviewed.description")
      ) {
        Image(systemName: "checkmark.seal.fill")
          .font(.system(size: 14))
          .foregroundStyle(Theme.ink)
      }
    }
  }
}

struct RecipeTileComingSoonBadge: View {
  var body: some View {
    Text(Copy.text("ui.coming.soon"))
      .font(.footnote.weight(.bold))
      .foregroundStyle(.white)
      .shadow(color: .black.opacity(0.6), radius: 3)
  }
}

/// Future tag e.g. "Low carb" — static overlay; same circle/pill chrome.
struct RecipeTileTagBadge: View {
  let label: String
  var corner: RecipeTileCorner = .bottomLeading

  var body: some View {
    RecipeTileOverlaySlot(corner: corner) {
      RecipeTilePhotoOverlay(corner: corner, mode: .staticBadge, accessibilityLabel: label) {
        Text(label)
          .font(.caption2.weight(.semibold))
          .foregroundStyle(Theme.ink)
          .lineLimit(1)
          .padding(.horizontal, 4)
      }
    }
  }
}

// MARK: - Meta (reserved height)

/// Named meta lines under the name. Opted-in types keep a stable height when empty.
struct RecipeTileMetaBlock: View {
  let minutes: Int?
  let reviewed: Bool
  var meta: RecipeTileMeta

  var body: some View {
    VStack(alignment: .leading, spacing: 2) {
      if meta.showCookTime || meta.showKitchenTested {
        // * Reserved height so missing time / kitchen-tested does not shift tiles in a row.
        RecipeStatusLine(
          minutes: meta.showCookTime ? minutes : nil,
          reviewed: meta.showKitchenTested && reviewed
        )
        .frame(minHeight: 16, alignment: .leading)
        .opacity(statusVisible ? 1 : 0)
        .accessibilityHidden(!statusVisible)
      }
      if meta.showServings {
        Group {
          if let servings = meta.servings {
            RecipeCardServings(servings: servings)
          } else {
            RecipeCardServings(servings: 0).hidden()
          }
        }
        .frame(minHeight: 16, alignment: .leading)
      }
      if meta.showYourSelection {
        Text(Copy.text("ui.your.selection"))
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .opacity(meta.yourSelection ? 1 : 0)
          .accessibilityHidden(!meta.yourSelection)
          .frame(minHeight: 16, alignment: .leading)
      }
      if meta.showSchedule {
        Text(meta.scheduleLabel ?? "Schedule")
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .opacity(meta.scheduleLabel != nil ? 1 : 0)
          .accessibilityHidden(meta.scheduleLabel == nil)
          .frame(minHeight: 16, alignment: .leading)
      }
    }
    .frame(maxWidth: .infinity, alignment: .leading)
  }

  private var statusVisible: Bool {
    let hasTime = meta.showCookTime && (minutes ?? 0) > 0
    let hasBadge = meta.showKitchenTested && reviewed
    return hasTime || hasBadge
  }
}

// MARK: - RecipeTile

/// Shared recipe tile. Pass photo path, name, and options; overlays are views placed on the photo.
struct RecipeTile<Overlay: View>: View {
  let name: String
  var photoPath: String? = nil
  /// Side length when non-nil; otherwise the photo fills the available width (square).
  var photoSide: CGFloat? = nil
  var photoOpacity: Double = 1
  var photoGrayscale: Double = 0
  var comingSoon = false
  var openEnabled = true
  var nameLineLimit: Int? = 2
  var nameReservesSpace = true
  var minutes: Int? = nil
  var reviewed = false
  var meta = RecipeTileMeta()
  var menuItems: [RecipeTileMenuItem] = []
  var onOpen: (() -> Void)? = nil
  @ViewBuilder var overlays: () -> Overlay

  init(
    name: String,
    photoPath: String? = nil,
    photoSide: CGFloat? = nil,
    photoOpacity: Double = 1,
    photoGrayscale: Double = 0,
    comingSoon: Bool = false,
    openEnabled: Bool = true,
    nameLineLimit: Int? = 2,
    nameReservesSpace: Bool = true,
    minutes: Int? = nil,
    reviewed: Bool = false,
    meta: RecipeTileMeta = RecipeTileMeta(),
    menuItems: [RecipeTileMenuItem] = [],
    onOpen: (() -> Void)? = nil,
    @ViewBuilder overlays: @escaping () -> Overlay
  ) {
    self.name = name
    self.photoPath = photoPath
    self.photoSide = photoSide
    self.photoOpacity = photoOpacity
    self.photoGrayscale = photoGrayscale
    self.comingSoon = comingSoon
    self.openEnabled = openEnabled && !comingSoon
    self.nameLineLimit = nameLineLimit
    self.nameReservesSpace = nameReservesSpace
    self.minutes = minutes
    self.reviewed = reviewed
    self.meta = meta
    self.menuItems = menuItems
    self.onOpen = onOpen
    self.overlays = overlays
  }

  var body: some View {
    let tile = Group {
      if meta.placement == .beside {
        HStack(alignment: .top, spacing: 12) {
          photo
          bodyColumn
        }
      } else {
        VStack(alignment: .leading, spacing: 8) {
          photo
          bodyColumn
        }
      }
    }
    .contentShape(Rectangle())
    .onTapGesture {
      guard openEnabled else { return }
      onOpen?()
    }
    if menuItems.isEmpty {
      tile
    } else {
      tile.contextMenu {
        ForEach(menuItems) { item in
          Button(item.title, role: item.role, action: item.action)
        }
      }
    }
  }

  private var bodyColumn: some View {
    VStack(alignment: .leading, spacing: 4) {
      // * Name always uses RecipeCardName default typography.
      if comingSoon {
        Text(name)
          .font(Theme.recipeCardServing)
          .foregroundStyle(Theme.muted)
          .lineLimit(nameLineLimit)
      } else {
        RecipeCardName(name: name, lineLimit: nameLineLimit, reservesSpace: nameReservesSpace)
      }
      RecipeTileMetaBlock(minutes: minutes, reviewed: reviewed, meta: meta)
    }
    .frame(maxWidth: .infinity, alignment: .leading)
  }

  private var photo: some View {
    // Beside defaults to swap-picker thumb size when photoSide is omitted.
    let side = photoSide ?? (meta.placement == .beside ? 70 : nil)
    let square = Color.clear.aspectRatio(1, contentMode: .fit)
    return Group {
      if let side {
        square.frame(width: side, height: side)
      } else {
        square.frame(maxWidth: .infinity)
      }
    }
    .overlay {
      RecipePhoto(path: photoPath, fill: true)
        .opacity(comingSoon ? min(photoOpacity, 0.6) : photoOpacity)
        .grayscale(comingSoon ? max(photoGrayscale, 0.6) : photoGrayscale)
        .allowsHitTesting(false)
    }
    .overlay {
      if comingSoon { RecipeTileComingSoonBadge() }
    }
    // Caller stacks self-positioned overlay buttons (each fills the photo and aligns to a corner).
    .overlay { overlays() }
    .clipped()
    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
  }
}

extension RecipeTile where Overlay == EmptyView {
  init(
    name: String,
    photoPath: String? = nil,
    photoSide: CGFloat? = nil,
    photoOpacity: Double = 1,
    photoGrayscale: Double = 0,
    comingSoon: Bool = false,
    openEnabled: Bool = true,
    nameLineLimit: Int? = 2,
    nameReservesSpace: Bool = true,
    minutes: Int? = nil,
    reviewed: Bool = false,
    meta: RecipeTileMeta = RecipeTileMeta(),
    menuItems: [RecipeTileMenuItem] = [],
    onOpen: (() -> Void)? = nil
  ) {
    self.init(
      name: name, photoPath: photoPath, photoSide: photoSide, photoOpacity: photoOpacity,
      photoGrayscale: photoGrayscale, comingSoon: comingSoon, openEnabled: openEnabled,
      nameLineLimit: nameLineLimit, nameReservesSpace: nameReservesSpace, minutes: minutes,
      reviewed: reviewed, meta: meta, menuItems: menuItems, onOpen: onOpen
    ) { EmptyView() }
  }
}
