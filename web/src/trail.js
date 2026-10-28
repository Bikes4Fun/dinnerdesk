// The last few screens visited and errors hit, oldest first. A bug report sends them along
// (api.sendFeedback) so it shows what led up to the problem. Kept in memory only.
const MAX = 10;
const pages = [];
const errors = [];

function push(list, entry) {
  list.push(entry);
  if (list.length > MAX) list.shift();
}

function stamp() {
  return new Date().toISOString().slice(11, 19);
}

// Invite, reset and confirm links carry one-time tokens; they never go in a report.
function redact(text) {
  return text.replace(/\/(join|reset|verify|invites)\/[^\s/?#:]+/g, "/$1/[token]");
}

export function recordPage() {
  const path = redact(window.location.pathname + window.location.search);
  if (pages.at(-1)?.endsWith(` ${path}`)) return;
  push(pages, `${stamp()} ${path}`.slice(0, 200));
}

export function recordError(text) {
  push(errors, `${stamp()} ${redact(text)}`.slice(0, 500));
}

export function trail() {
  return { pages: [...pages], errors: [...errors] };
}

recordPage();
window.addEventListener("popstate", recordPage);
window.addEventListener("error", (e) => recordError(e.message || "Script error"));
window.addEventListener("unhandledrejection", (e) => recordError(String(e.reason?.message || e.reason || "Unhandled rejection")));
