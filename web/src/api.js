async function req(path, options = {}) {
  // Screens handle recoverable request errors; unhandled failures reach App's boundary.
  return request(path, options);
}

const BASE = "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      if (res.ok) {
        const err = new Error(res.statusText || "Request failed");
        err.status = res.status;
        throw err;
      }
      data = { error: "bad_response", detail: text.slice(0, 120) };
    }
  }
  if (!res.ok) {
    const detail = data && data.detail;
    const usable = typeof detail === "string" && !detail.trim().startsWith("<");
    const messages = {
      401: "Please sign in again to continue.",
      403: "You don't have access to this action.",
      404: "This action is currently unavailable. Please try again later. If it keeps happening, contact Dinnerdesk support.",
      405: "This action is currently unavailable. Please try again later. If it keeps happening, contact Dinnerdesk support.",
    };
    const message = messages[res.status] || (res.status >= 500
      ? "The server couldn't complete this action. Please try again shortly."
      : usable ? detail : "Couldn't complete this action. Please try again.");
    const err = new Error(message);
    err.status = res.status;
    err.body = data;
    throw err;
  }
  return data;
}

export const api = {
  recipes: (params = {}) => {
    const q = new URLSearchParams();
    if (params.q) q.set("q", params.q);
    if (params.tag) q.set("tag", params.tag);
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    if (params.hidden) q.set("hidden", "true");
    const qs = q.toString();
    return req(`/api/recipes${qs ? `?${qs}` : ""}`);
  },
  recipe: (id) => req(`/api/recipes/${id}`),
  createRecipe: (body) => req("/api/recipes", { method: "POST", body: JSON.stringify(body) }),
  tags: () => req("/api/tags"),
  plan: () => req("/api/plans/current"),
  plans: () => req("/api/plans"),
  suggestedRecipes: () => req("/api/suggestions/recipes"),
  suggestionCapabilities: () => req("/api/suggestions/capabilities"),
  pendingSuggestion: () => req("/api/suggestions/current"),
  decideSuggestion: (id, decision) => req(`/api/plans/${id}/decision/${decision}`, { method: "POST" }),
  resizeSuggestion: (id, count) => req(`/api/plans/${id}/resize`, { method: "POST", body: JSON.stringify({ meal_count: count }) }),
  swapOptions: (id, slot, q = "") => req(`/api/plans/${id}/swap-options/${slot}?${new URLSearchParams({ q })}`),
  swapSuggestion: (id, slot, recipeId) => req(`/api/plans/${id}/swap/${slot}`, { method: "POST", body: JSON.stringify(recipeId ? { recipe_id: recipeId } : {}) }),
  deletePlan: (id) => req(`/api/plans/${id}`, { method: "DELETE" }),
  createPlan: (body) => req("/api/plans", { method: "POST", body: JSON.stringify(body) }),
  putSlots: (planId, slots) =>
    req(`/api/plans/${planId}/slots`, { method: "PUT", body: JSON.stringify({ slots }) }),
  patchSlot: (slotId, body) =>
    req(`/api/slots/${slotId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteSlot: (slotId) => req(`/api/slots/${slotId}`, { method: "DELETE" }),
  grocery: (planId) => req(`/api/plans/${planId}/grocery`),
  rebuildGrocery: (planId) => req(`/api/plans/${planId}/grocery`, { method: "POST" }),
  addGroceryLine: (planId, body) =>
    req(`/api/plans/${planId}/grocery/lines`, { method: "POST", body: JSON.stringify(body) }),
  patchGrocery: (lineId, body) =>
    req(`/api/grocery/lines/${lineId}`, { method: "PATCH", body: JSON.stringify(body) }),
  groceryItems: (q = "", limit = 12) => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    p.set("limit", String(limit));
    return req(`/api/grocery-items?${p}`);
  },
  placements: () => req("/api/grocery/places"),
  setPlacement: (body) => req("/api/grocery/places", { method: "PUT", body: JSON.stringify(body) }),
  pantry: () => req("/api/pantry"),
  pantryCatalog: () => req("/api/pantry/catalog"),
  putPantry: (items) => req("/api/pantry", { method: "PUT", body: JSON.stringify({ items }) }),
  upsertPantry: (body) => req("/api/pantry/items", { method: "POST", body: JSON.stringify(body) }),
  patchPantry: (id, body) =>
    req(`/api/pantry/items/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deletePantry: (id) => req(`/api/pantry/items/${id}`, { method: "DELETE" }),
  overrides: () => req("/api/overrides"),
  addOverride: (body) => req("/api/overrides", { method: "POST", body: JSON.stringify(body) }),
  deleteOverride: (id) => req(`/api/overrides/${id}`, { method: "DELETE" }),
  prep: (planId) => req(`/api/plans/${planId}/prep`),
  rateMeal: (recipeId, rating) =>
    req(`/api/recipes/${recipeId}/rating`, { method: "PUT", body: JSON.stringify({ rating }) }),
  ratePrepStep: (body) => req(`/api/prep/feedback`, { method: "PUT", body: JSON.stringify(body) }),
  patchPrep: (id, done) =>
    req(`/api/prep/${id}`, { method: "PATCH", body: JSON.stringify({ done }) }),
  checkPrepItem: (id, body) =>
    req(`/api/prep/${id}/steps`, { method: "PUT", body: JSON.stringify(body) }),
  patchRecipe: (id, body) =>
    req(`/api/recipes/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  restoreRecipe: (id) => req(`/api/recipes/${id}/edit`, { method: "DELETE" }),
  favorite: (id, on) =>
    req(`/api/recipes/${id}/favorite`, { method: "PUT", body: JSON.stringify({ on }) }),
  hideRecipe: (id, on) =>
    req(`/api/recipes/${id}/hidden`, { method: "PUT", body: JSON.stringify({ on }) }),
  tryLater: (id, on) =>
    req(`/api/recipes/${id}/try`, { method: "PUT", body: JSON.stringify({ on }) }),
  putDevNotes: (id, text) =>
    req(`/api/recipes/${id}/dev-notes`, { method: "PUT", body: JSON.stringify({ text }) }),
  ingredientReview: () => req("/api/dev/ingredient-review"),
  flaggedRecipes: () => req("/api/dev/ingredient-review/flagged"),
  putIngredientReviewNotes: (groupId, notes) =>
    req(`/api/dev/ingredient-review/${groupId}/notes`, {
      method: "PUT",
      body: JSON.stringify({ notes }),
    }),
  putIngredientReviewAnswer: (groupId, body) =>
    req(`/api/dev/ingredient-review/${groupId}/answer`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  putIngredientReviewAudit: (groupId, body) =>
    req(`/api/dev/ingredient-review/${groupId}/audit`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  putIngredientReviewAuditResolution: (groupId, resolution) =>
    req(`/api/dev/ingredient-review/${groupId}/audit-resolution`, {
      method: "PUT",
      body: JSON.stringify({ resolution }),
    }),
  household: () => req("/api/household"),
  putHousehold: (body) => req("/api/household", { method: "PUT", body: JSON.stringify(body) }),
  templates: () => req("/api/templates"),
  auth: {
    status: () => req("/api/auth/status"),
    me: () => req("/api/auth/me"),
    signup: (body) => req("/api/auth/signup", { method: "POST", body: JSON.stringify(body) }),
    login: (body) => req("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
    forgotPassword: (body) =>
      req("/api/auth/forgot-password", { method: "POST", body: JSON.stringify(body) }),
    resetPassword: (body) =>
      req("/api/auth/reset-password", { method: "POST", body: JSON.stringify(body) }),
    logout: () => req("/api/auth/logout", { method: "POST" }),
    logoutEverywhere: () => req("/api/auth/logout-everywhere", { method: "POST" }),
    changePassword: (body) =>
      req("/api/auth/change-password", { method: "POST", body: JSON.stringify(body) }),
  },
  householdMembers: () => req("/api/household/members"),
  removeHouseholdMember: (userId) =>
    req(`/api/household/members/${userId}`, { method: "DELETE" }),
  createHouseholdInvite: () => req("/api/household/invites", { method: "POST" }),
  previewInvite: (token) => req(`/api/household/invites/${token}`),
  acceptInvite: (body) =>
    req("/api/household/accept-invite", { method: "POST", body: JSON.stringify(body) }),
};

export function photoSrc(path) {
  if (!path) return "";
  return path.startsWith("/") ? path : `/${path}`;
}
