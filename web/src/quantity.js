export function scaleAmount(text, base, servings) {
  if (!text || !base || base === servings) return text || "";
  const fractions = { "¼": "1/4", "½": "1/2", "¾": "3/4", "⅓": "1/3", "⅔": "2/3", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8" };
  const normalized = text.replace(/[¼½¾⅓⅔⅛⅜⅝⅞]/g, (glyph) => ` ${fractions[glyph]} `).replace(/\s+/g, " ").trim();
  const amount = String.raw`(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)`;
  const match = normalized.match(new RegExp(`^(${amount})(?:\\s*([-–])\\s*(${amount}))?`));
  if (!match) return text;
  function scaled(raw) {
    const value = raw.split(/\s+/).reduce((sum, part) => {
      const [n, d] = part.split("/").map(Number);
      if (d === 0) throw new Error("Invalid zero-denominator ingredient quantity");
      return sum + (d === undefined ? n : n / d);
    }, 0);
    return String(Number((value * servings / base).toFixed(3)));
  }
  return scaled(match[1]) + (match[3] ? match[2] + scaled(match[3]) : "") + normalized.slice(match[0].length);
}
