export function go(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

// Admin review pages: plain HTML served by the server (app/admin_routes.py), not app routes.
export const ADMIN_PAGES = [
  ["/admin/recipe-tags", "Recipe tags"],
  ["/admin/variant-review", "Similar recipes"],
  ["/admin/recipe-reports", "Recipe reports"],
  ["/admin/plan-reports", "Plan reports"],
  ["/admin/prep-feedback", "Prep feedback"],
  ["/admin/users", "Users"],
];
