import SwiftUI

/// A time mentioned in a recipe step ("simmer 10 minutes", "3–4 min", "1 1/2 hours").
/// The web has the same rules in web/src/timers.js; keep the two in step.
struct StepTime: Identifiable, Hashable {
  var id: String { label }
  let label: String
  /// The shorter end of a range: check early, add time if needed.
  let seconds: Int

  private static let amount = #"(?:\d+(?:\.\d+)?(?:\s+\d/\d)?|\d/\d|\d*[½¼¾⅓⅔]|an?|one)"#
  private static let pattern = try! NSRegularExpression(
    pattern: #"(?<![\w.])("# + amount + #")(?:\s*(?:-|–|to)\s*"# + amount
      + #")?\s*(?:more\s+)?(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b"#,
    options: [.caseInsensitive])

  static func find(in text: String) -> [StepTime] {
    let range = NSRange(text.startIndex..., in: text)
    var out: [StepTime] = []
    for match in pattern.matches(in: text, range: range) {
      guard let whole = Range(match.range, in: text),
        let first = Range(match.range(at: 1), in: text),
        // Group 2 is the optional end of a range ("3-4"); group 3 is the unit.
        let unit = Range(match.range(at: 3), in: text)
      else { continue }
      let seconds = Int((value(String(text[first])) * multiplier(String(text[unit]))).rounded())
      let label = String(text[whole]).trimmingCharacters(in: .whitespaces)
      if seconds > 0, seconds <= 24 * 3600, !out.contains(where: { $0.label == label }) {
        out.append(StepTime(label: label, seconds: seconds))
      }
    }
    return out
  }

  private static func multiplier(_ unit: String) -> Double {
    let u = unit.lowercased()
    if u.hasPrefix("h") { return 3600 }
    if u.hasPrefix("m") { return 60 }
    return 1
  }

  private static func value(_ text: String) -> Double {
    let t = text.trimmingCharacters(in: .whitespaces).lowercased()
    if ["a", "an", "one"].contains(t) { return 1 }
    let fractions: [Character: Double] = ["½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3]
    var total = 0.0
    for part in t.split(separator: " ") {
      if let last = part.last, let frac = fractions[last] {
        total += (Double(part.dropLast()) ?? 0) + frac
      } else if part.contains("/") {
        let pieces = part.split(separator: "/").compactMap { Double($0) }
        if pieces.count == 2, pieces[1] != 0 { total += pieces[0] / pieces[1] }
      } else {
        total += Double(part) ?? 0
      }
    }
    return total
  }
}

/// A start button for each time mentioned in a step (Cook mode).
struct StepTimers: View {
  let text: String

  var body: some View {
    let times = StepTime.find(in: text)
    if !times.isEmpty {
      // Wraps onto more lines at large text sizes.
      KitchenFlow(spacing: 8) {
        ForEach(times) { StepTimerButton(time: $0) }
      }
    }
  }
}

private struct StepTimerButton: View {
  let time: StepTime
  @State private var endsAt: Date?

  var body: some View {
    if let endsAt {
      TimelineView(.periodic(from: .now, by: 1)) { context in
        let left = endsAt.timeIntervalSince(context.date)
        let done = left <= 0
        HStack(spacing: 8) {
          Text(done ? "Time's up" : clock(left))
            .font(Theme.action)
            .monospacedDigit()
            .foregroundStyle(done ? Color.white : Theme.ink)
          Button(done ? "Dismiss" : "Stop") { self.endsAt = nil }
            .font(Theme.subtitle)
            .foregroundStyle(done ? Color.white : Theme.accent)
        }
        .padding(.horizontal, 12)
        .frame(minHeight: 36)
        .background(done ? Theme.accent : Theme.surface, in: Capsule())
        .overlay(Capsule().stroke(Theme.line))
        .sensoryFeedback(.success, trigger: done) { _, isDone in isDone }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(done ? "Timer for \(time.label) is done" : "\(clock(left)) left")
      }
    } else {
      Button {
        endsAt = Date().addingTimeInterval(TimeInterval(time.seconds))
      } label: {
        Label(time.label, systemImage: "timer")
          .font(Theme.action)
          .foregroundStyle(Theme.accent)
          .padding(.horizontal, 12)
          .frame(minHeight: 36)
          .background(Theme.surface, in: Capsule())
          .overlay(Capsule().stroke(Theme.line))
      }
      .buttonStyle(.plain)
      .accessibilityLabel("Start a \(time.label) timer")
    }
  }

  private func clock(_ seconds: TimeInterval) -> String {
    let s = max(0, Int(seconds.rounded(.up)))
    let h = s / 3600, m = (s % 3600) / 60, sec = s % 60
    return h > 0 ? String(format: "%d:%02d:%02d", h, m, sec) : String(format: "%d:%02d", m, sec)
  }
}
