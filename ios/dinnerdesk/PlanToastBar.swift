import SwiftUI

/// What a recipe card's ＋ or ✓ just did. Those icons have no room for a label (#35), so the
/// bar says it in words and offers one Undo. It mirrors the Prep tab's check-off bar, and web
/// and Android show the same thing.
struct PlanToastBar: View {
  @EnvironmentObject private var store: Store
  @Environment(\.accessibilityReduceMotion) private var reduceMotion

  private static let coral = Color(hex: 0xFA7E5A)
  private static let coralTint = Color(hex: 0xFDE6DD)

  var body: some View {
    bar.animation(reduceMotion ? nil : .easeOut(duration: 0.2), value: store.planToast?.id)
  }

  @ViewBuilder private var bar: some View {
    if let toast = store.planToast {
      HStack(spacing: 10) {
        Image(systemName: toast.undoAdds ? "minus.circle.fill" : "checkmark.circle.fill")
          .foregroundStyle(Self.coral)
          .accessibilityHidden(true)
        Text(toast.text)
          .font(Theme.subtitle)
          .lineLimit(2)
          .foregroundStyle(Theme.surface)
          .frame(maxWidth: .infinity, alignment: .leading)
        Button("Undo") {
          Task { await store.undoPlanToast() }
        }
        .font(Theme.action)
        .foregroundStyle(Self.coralTint)
        .underline()
        .frame(minHeight: 44)
        Button {
          store.planToast = nil
        } label: {
          Image(systemName: "xmark")
            .foregroundStyle(Theme.aubergineTint)
            .frame(width: 44, height: 44)
        }
        .accessibilityLabel("Dismiss")
      }
      .padding(.leading, 16)
      .padding(.trailing, 6)
      .padding(.vertical, 8)
      .background(Theme.ink, in: RoundedRectangle(cornerRadius: 20))
      .shadow(color: Theme.ink.opacity(0.25), radius: 14, y: 6)
      .padding(.horizontal, 12)
      .padding(.bottom, 12)
      .transition(reduceMotion ? .opacity : .move(edge: .bottom).combined(with: .opacity))
      .task(id: toast.id) {
        // VoiceOver doesn't move to a bar that appears on its own, so read it out.
        AccessibilityNotification.Announcement(toast.text).post()
        do { try await Task.sleep(for: .seconds(4)) } catch { return }
        if store.planToast?.id == toast.id { store.planToast = nil }
      }
    }
  }
}

extension View {
  /// Shows the plan toast above this screen, clear of the tab bar.
  func planToast() -> some View {
    overlay(alignment: .bottom) { PlanToastBar() }
  }
}
