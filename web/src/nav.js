export function go(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

// Admin pages as [path, label, app page]. Without an app page it's plain HTML served by the
// server (app/admin_routes.py), opened as a full page load.
export const ADMIN_PAGES = [
  ["/admin/inbox", "Inbox"],
  ["/admin/users", "Users"],
  ["/settings/recipe-flags", "Recipes to edit", "recipe-flags"],
  ["/admin/recipe-tags", "Recipe tags"],
  ["/settings/ingredients", "Ingredient review", "ingredient-review"],
];

/** New items waiting in the admin Inbox, or 0 when it can't tell. */
export function inboxCount() {
  return fetch("/admin/inbox/count", { credentials: "same-origin" })
    .then((r) => (r.ok ? r.json() : { new: 0 }))
    .then((r) => r.new || 0)
    .catch(() => 0);
}
