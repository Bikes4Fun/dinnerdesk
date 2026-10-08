// Times mentioned in a recipe step ("simmer 10 minutes", "3–4 min", "1 1/2 hours").
// iOS has the same rules in StepTimer.swift; keep the two in step.

const UNIT = { s: 1, sec: 1, secs: 1, second: 1, seconds: 1, m: 60, min: 60, mins: 60, minute: 60, minutes: 60, h: 3600, hr: 3600, hrs: 3600, hour: 3600, hours: 3600 };
const FRACTION = { "½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3 };
const AMOUNT = String.raw`(?:\d+(?:\.\d+)?(?:\s+\d\/\d)?|\d\/\d|\d*[½¼¾⅓⅔]|an?|one)`;
const PATTERN = new RegExp(
  String.raw`(?<![\w.])(${AMOUNT})(?:\s*(?:-|–|to)\s*(${AMOUNT}))?\s*(?:more\s+)?(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b`,
  "gi",
);

function amount(text) {
  const t = text.trim().toLowerCase();
  if (t === "a" || t === "an" || t === "one") return 1;
  let total = 0;
  for (const part of t.split(/\s+/)) {
    const frac = part.match(/^(\d*)([½¼¾⅓⅔])$/);
    if (frac) total += Number(frac[1] || 0) + FRACTION[frac[2]];
    else if (part.includes("/")) {
      const [n, d] = part.split("/").map(Number);
      total += d ? n / d : 0;
    } else total += Number(part) || 0;
  }
  return total;
}

/** [{label, seconds}] for each time in the step, shortest bound when it's a range. */
export function parseTimers(text) {
  const out = [];
  for (const m of String(text || "").matchAll(PATTERN)) {
    const seconds = Math.round(amount(m[1]) * UNIT[m[3].toLowerCase()]);
    if (seconds > 0 && seconds <= 24 * 3600 && !out.some((t) => t.label === m[0])) {
      out.push({ label: m[0].trim(), seconds });
    }
  }
  return out;
}

export function clock(seconds) {
  const s = Math.max(0, Math.ceil(seconds));
  const h = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(h ? 2 : 1, "0");
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}
