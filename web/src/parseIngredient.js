const FRACTIONS = {
  "¼": "1/4",
  "½": "1/2",
  "¾": "3/4",
  "⅓": "1/3",
  "⅔": "2/3",
  "⅛": "1/8",
  "⅜": "3/8",
  "⅝": "5/8",
  "⅞": "7/8",
};

const AMOUNT =
  /^(?:about\s+)?(?:\d+\s+\d+\s*\/\s*\d+|\d+\s*\/\s*\d+|\d+(?:\.\d+)?)/i;
const PAREN = /^\(\s*[\d\s./]+\s*(?:fl\s*oz|ounces?|oz|pounds?|lbs?|grams?|g|ml)\s*\)/i;
const UNIT =
  /^(?:fluid\s+ounces?|fl(?:uid)?\s+oz|tablespoons?|teaspoons?|pounds?|ounces?|cups?|tbsp|tsp|lbs?|oz|cloves?|heads?|pints?|bunches?|bunch|cans?|packages?|pkgs?|pkg|slices?)\b/i;

export function normalizeFractions(s) {
  let out = s || "";
  for (const [glyph, ascii] of Object.entries(FRACTIONS)) {
    out = out.split(glyph).join(` ${ascii} `);
  }
  return out.replace(/\s+/g, " ").trim();
}

function take(re, rest, parts) {
  const m = rest.match(re);
  if (!m) return rest;
  parts.push(m[0].replace(/\s+/g, " ").trim());
  return rest.slice(m[0].length).trimStart();
}

export function parseIngLine(line) {
  const t = normalizeFractions((line || "").replace(/\s+/g, " ").trim());
  if (!t) return null;
  if (/^\d+\s*%/.test(t)) return { quantity: "", name: t };
  const parts = [];
  let rest = t;
  rest = take(AMOUNT, rest, parts);
  rest = take(PAREN, rest, parts);
  rest = take(UNIT, rest, parts);
  rest = take(PAREN, rest, parts);
  if (!parts.length) {
    const m = rest.match(UNIT);
    const leftover = m ? rest.slice(m[0].length).trim() : "";
    if (m && leftover) return { quantity: m[0].trim(), name: leftover };
    return { quantity: "", name: t };
  }
  if (!rest) return { quantity: parts.join(" "), name: "" };
  return { quantity: parts.join(" "), name: rest };
}
