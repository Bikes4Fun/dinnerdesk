import SwiftUI

/// A small drawn picture of the screen a quick-start card describes (#25), so the card isn't
/// blank under its text. Drawn, not a screenshot, so it never goes stale or shows real photos.
/// Decorative: the card's text says the same thing, so VoiceOver skips it.
/// Mirrors web/src/TourPicture.jsx.
struct TourScreenPicture: View {
  /// 0 suggestions, 1 this plan, 2 grocery, 3 weekend prep (the order of tour.how.N).
  let index: Int

  private let coralTint = Color(hex: 0xFDE6DD)
  private let warm = Color(hex: 0xF3EBE8)
  private let coral = Color(hex: 0xFA7E5A)

  var body: some View {
    VStack(alignment: .leading, spacing: 10) {
      switch index {
      case 0: suggestions
      case 1: thisPlan
      case 2: grocery
      default: prep
      }
      Spacer(minLength: 0)
    }
    .padding(14)
    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    .background(Theme.bg, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Theme.line))
    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    .accessibilityHidden(true)
  }

  // MARK: Screens

  private var suggestions: some View {
    VStack(alignment: .leading, spacing: 10) {
      label("SUGGESTED FOR YOU")
      HStack(spacing: 8) {
        mealTile(coralTint, 0.8)
        mealTile(Theme.aubergineTint, 0.6)
      }
      HStack(spacing: 8) {
        mealTile(warm, 0.7)
        mealTile(coralTint, 0.5)
      }
      HStack(spacing: 8) {
        pill("Swap", fill: Theme.surface, text: Theme.ink, outlined: true)
        pill("Approve plan", fill: Theme.ink, text: Theme.surface)
      }
    }
  }

  private var thisPlan: some View {
    VStack(alignment: .leading, spacing: 10) {
      label("THIS WEEK")
      planRow(coralTint, 0.75, day: "Mon")
      planRow(Theme.aubergineTint, 0.55, day: "Schedule")
      planRow(warm, 0.65, day: "Schedule")
    }
  }

  private var grocery: some View {
    VStack(alignment: .leading, spacing: 9) {
      label("PRODUCE")
      groceryRow(checked: false, 0.5)
      groceryRow(checked: false, 0.35)
      groceryRow(checked: true, 0.45)
      label("PANTRY")
      groceryRow(checked: true, 0.4)
    }
  }

  private var prep: some View {
    VStack(alignment: .leading, spacing: 9) {
      label("CHOP & SLICE")
      prepRow(done: true, 0.4)
      prepRow(done: false, 0.55)
      prepRow(done: false, 0.35)
      label("SAUCES")
      prepRow(done: false, 0.6)
    }
  }

  // MARK: Pieces

  private func label(_ text: String) -> some View {
    Text(text)
      .font(.system(size: 10, weight: .bold))
      .tracking(0.6)
      .foregroundStyle(Theme.muted)
  }

  private func line(_ fraction: CGFloat, _ color: Color = Theme.line, height: CGFloat = 7) -> some View {
    GeometryReader { geo in
      Capsule().fill(color).frame(width: geo.size.width * fraction, height: height)
    }
    .frame(height: height)
  }

  private func mealTile(_ tint: Color, _ name: CGFloat) -> some View {
    VStack(alignment: .leading, spacing: 5) {
      RoundedRectangle(cornerRadius: 8, style: .continuous).fill(tint).frame(height: 46)
      line(name, Theme.ink.opacity(0.35))
    }
    .frame(maxWidth: .infinity)
  }

  private func planRow(_ tint: Color, _ name: CGFloat, day: String) -> some View {
    HStack(spacing: 10) {
      RoundedRectangle(cornerRadius: 7, style: .continuous).fill(tint).frame(width: 40, height: 40)
      VStack(alignment: .leading, spacing: 6) {
        line(name, Theme.ink.opacity(0.35))
        line(0.3)
      }
      Text(day)
        .font(.system(size: 10, weight: .semibold))
        .foregroundStyle(Theme.ink)
        .padding(.horizontal, 7)
        .padding(.vertical, 4)
        .overlay(Capsule().stroke(Theme.line))
    }
  }

  private func groceryRow(checked: Bool, _ name: CGFloat) -> some View {
    HStack(spacing: 10) {
      Image(systemName: checked ? "checkmark.circle.fill" : "circle")
        .font(.system(size: 15))
        .foregroundStyle(checked ? Theme.accent : Theme.muted)
      line(name, checked ? Theme.line : Theme.ink.opacity(0.35))
      Capsule().fill(Theme.line).frame(width: 26, height: 7)
    }
    .opacity(checked ? 0.6 : 1)
  }

  private func prepRow(done: Bool, _ name: CGFloat) -> some View {
    HStack(spacing: 10) {
      Image(systemName: done ? "checkmark.circle.fill" : "circle")
        .font(.system(size: 15))
        .foregroundStyle(done ? coral : Theme.muted)
      line(name, done ? Theme.line : Theme.ink.opacity(0.35))
    }
    .opacity(done ? 0.6 : 1)
  }

  private func pill(_ text: String, fill: Color, text color: Color, outlined: Bool = false) -> some View {
    Text(text)
      .font(.system(size: 11, weight: .semibold))
      .foregroundStyle(color)
      .frame(maxWidth: .infinity, minHeight: 26)
      .background(fill, in: Capsule())
      .overlay(Capsule().stroke(outlined ? Theme.line : .clear))
  }
}
