import StoreKit
import SwiftUI

/// How to send a screenshot to the developer from TestFlight, then how to quiet TestFlight's
/// emails and notifications. Shown once on this device before the quick start tour (skipping the
/// tour doesn't skip it), again after creating an account, and any time from More. Only in
/// TestFlight builds, where Share Beta Feedback exists.
struct FeedbackTipView: View {
  private struct Step: Identifiable {
    let id: Int
    let systemImage: String
  }

  // feedback-tip.N in copy.json.
  private static let steps = ["camera.viewfinder", "hand.tap", "exclamationmark.bubble", "paperplane"]
    .enumerated().map { Step(id: $0.offset + 1, systemImage: $0.element) }
  // tester-alerts.N in copy.json.
  private static let alertSteps = ["airplane", "envelope", "bell.slash", "arrow.down.circle"]
    .enumerated().map { Step(id: $0.offset + 1, systemImage: $0.element) }

  @Environment(\.dismiss) private var dismiss
  /// Second page: how to turn TestFlight's emails and notifications off.
  @State private var showAlerts = false

  var body: some View {
    VStack(spacing: 0) {
      ScrollView {
        if showAlerts {
          page("tester-alerts", steps: Self.alertSteps) { _ in EmptyView() }
          if let testFlight = URL(string: "itms-beta://") {
            Link(destination: testFlight) {
              Label(Copy.text("tester-alerts.open"), systemImage: "arrow.up.right.square")
                .font(Theme.action)
                .foregroundStyle(Theme.accent)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 24)
            .padding(.bottom, 24)
          }
        } else {
          page("feedback-tip", steps: Self.steps) { id in
            if id == 3 { screenshots }
          }
        }
      }
      Button {
        if showAlerts { dismiss() } else { withAnimation { showAlerts = true } }
      } label: {
        Text(showAlerts ? "Got it" : "Next")
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

  /// A title, a tip, then numbered steps; `extra` adds a picture under a step.
  private func page<Extra: View>(
    _ prefix: String, steps: [Step], @ViewBuilder extra: @escaping (Int) -> Extra
  ) -> some View {
    VStack(alignment: .leading, spacing: 18) {
      Text(Copy.text("\(prefix).title"))
        .font(Theme.tourTitle)
        .foregroundStyle(Theme.ink)
        .fixedSize(horizontal: false, vertical: true)
      StarTip(id: "\(prefix).intro")
      ForEach(steps) { step in
        HStack(alignment: .top, spacing: 14) {
          Image(systemName: step.systemImage)
            .font(Theme.title)
            .foregroundStyle(Theme.accent)
            .frame(width: 28)
            .accessibilityHidden(true)
          VStack(alignment: .leading, spacing: 4) {
            Text("\(step.id). \(Copy.text("\(prefix).\(step.id).title"))")
              .font(Theme.mealName)
              .foregroundStyle(Theme.ink)
            Text(Copy.text("\(prefix).\(step.id)"))
              .font(Theme.body)
              .foregroundStyle(Theme.ink)
              .fixedSize(horizontal: false, vertical: true)
          }
        }
        .accessibilityElement(children: .combine)
        extra(step.id)
      }
    }
    .padding(24)
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
