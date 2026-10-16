import StoreKit
import SwiftUI

/// How to send a screenshot to the developer from TestFlight. Shown once on this device before
/// the quick start tour (skipping the tour doesn't skip it), again after creating an account,
/// and any time from More. Only in TestFlight builds, where Share Beta Feedback exists.
struct FeedbackTipView: View {
  private struct Step: Identifiable {
    let id: Int
    let systemImage: String
  }

  // feedback-tip.N in copy.json.
  private static let steps = ["camera.viewfinder", "hand.tap", "exclamationmark.bubble", "paperplane"]
    .enumerated().map { Step(id: $0.offset + 1, systemImage: $0.element) }

  @Environment(\.dismiss) private var dismiss

  var body: some View {
    VStack(spacing: 0) {
      ScrollView {
        VStack(alignment: .leading, spacing: 18) {
          Text(Copy.text("feedback-tip.title"))
            .font(Theme.tourTitle)
            .foregroundStyle(Theme.ink)
            .fixedSize(horizontal: false, vertical: true)
          StarTip(id: "feedback-tip.intro")
          ForEach(Self.steps) { step in
            HStack(alignment: .top, spacing: 14) {
              Image(systemName: step.systemImage)
                .font(Theme.title)
                .foregroundStyle(Theme.accent)
                .frame(width: 28)
                .accessibilityHidden(true)
              VStack(alignment: .leading, spacing: 4) {
                Text("\(step.id). \(Copy.text("feedback-tip.\(step.id).title"))")
                  .font(Theme.mealName)
                  .foregroundStyle(Theme.ink)
                Text(Copy.text("feedback-tip.\(step.id)"))
                  .font(Theme.body)
                  .foregroundStyle(Theme.ink)
                  .fixedSize(horizontal: false, vertical: true)
              }
            }
            .accessibilityElement(children: .combine)
            if step.id == 3 { screenshots }
          }
        }
        .padding(24)
      }
      Button {
        dismiss()
      } label: {
        Text("Got it")
          .font(Theme.action)
          .frame(maxWidth: .infinity)
          .frame(minHeight: 50)
      }
      .buttonStyle(.borderedProminent)
      .buttonBorderShape(.capsule)
      .tint(Theme.accent)
      .padding(.horizontal, 20)
      .padding(.vertical, 12)
    }
    .background(Theme.bg)
    .presentationDragIndicator(.visible)
  }

  /// The two ways to reach Share Beta Feedback, side by side, each with its full screenshot.
  private var screenshots: some View {
    HStack(alignment: .top, spacing: 12) {
      way("A", text: "feedback-tip.3.done", image: "FeedbackDoneMenu")
      way("B", text: "feedback-tip.3.share", image: "FeedbackShareSheet")
    }
    .padding(.leading, 42)
  }

  private func way(_ letter: String, text: String, image: String) -> some View {
    VStack(alignment: .leading, spacing: 8) {
      Text("Way \(letter)")
        .font(Theme.chipLabel)
        .foregroundStyle(Theme.accent)
      Text(Copy.text(text))
        .font(Theme.subtitle)
        .foregroundStyle(Theme.ink)
        .fixedSize(horizontal: false, vertical: true)
      Image(image)
        .resizable()
        .scaledToFit()
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .accessibilityHidden(true)
    }
    .frame(maxWidth: .infinity, alignment: .topLeading)
    .accessibilityElement(children: .combine)
  }

  /// True in TestFlight, where Share Beta Feedback is available. To try it from Xcode, add the
  /// environment variable DD_FEEDBACK_TIP=1 to the scheme.
  static func isBeta() async -> Bool {
    #if DEBUG
      return ProcessInfo.processInfo.environment["DD_FEEDBACK_TIP"] == "1"
    #else
      guard case .verified(let transaction)? = try? await AppTransaction.shared else { return false }
      return transaction.environment == .sandbox
    #endif
  }
}
