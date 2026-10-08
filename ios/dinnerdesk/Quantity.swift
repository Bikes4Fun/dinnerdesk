import Foundation

/// Scale amounts and ranges while preserving units and package dimensions.
func scaleAmount(_ text: String, from base: Int?, to servings: Int) -> String {
  guard let base, base > 0, base != servings else { return text }
  var normalized = text
  for (glyph, fraction) in [
    "¼": "1/4", "½": "1/2", "¾": "3/4", "⅓": "1/3", "⅔": "2/3", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8",
    "⅞": "7/8",
  ] {
    normalized = normalized.replacingOccurrences(of: glyph, with: " \(fraction) ")
  }
  normalized = normalized.replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
    .trimmingCharacters(in: .whitespaces)
  let amountPattern = #"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"#
  let regex = try! NSRegularExpression(
    pattern: "^(\(amountPattern))(?:\\s*([-–])\\s*(\(amountPattern)))?")
  guard
    let match = regex.firstMatch(
      in: normalized, range: NSRange(normalized.startIndex..., in: normalized)),
    let full = Range(match.range, in: normalized),
    let first = Range(match.range(at: 1), in: normalized)
  else { return text }
  func scaled(_ raw: Substring) -> String {
    let value =
      raw.split(whereSeparator: { $0.isWhitespace }).reduce(0.0) { sum, part in
        let fraction = part.split(separator: "/")
        if fraction.count == 2 {
          let denominator = Double(fraction[1])!
          precondition(denominator != 0, "Invalid zero-denominator ingredient quantity")
          return sum + Double(fraction[0])! / denominator
        }
        return sum + Double(part)!
      } * Double(servings) / Double(base)
    return String(format: "%.3f", locale: Locale(identifier: "en_US_POSIX"), value)
      .replacingOccurrences(of: #"\.?0+$"#, with: "", options: .regularExpression)
  }
  var result = scaled(normalized[first])
  if let second = Range(match.range(at: 3), in: normalized),
    let separator = Range(match.range(at: 2), in: normalized)
  {
    result += normalized[separator] + scaled(normalized[second])
  }
  return result + normalized[full.upperBound...]
}
