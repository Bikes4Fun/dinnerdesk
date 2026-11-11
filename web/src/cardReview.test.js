import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

test("thumbnail review controls are admin-only and expose the saved state", async () => {
  const previousWindow = globalThis.window;
  globalThis.window = { location: { pathname: "/recipes", search: "" }, addEventListener() {} };
  const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
  try {
    const { RecipeCard, RecipeRow } = await server.ssrLoadModule("/src/cards.jsx");
    const { WeekProvider } = await server.ssrLoadModule("/src/week.jsx");
    for (const Card of [RecipeCard, RecipeRow]) {
      for (const coming_soon of [false, true]) {
        const recipe = { id: 1, name: "Soup", reviewed: true, coming_soon };
        const render = (admin) => renderToStaticMarkup(createElement(WeekProvider, null,
          createElement(Card, { recipe, admin, onChange() {} })));
        assert.match(render(true), /aria-pressed="true"[^>]*aria-label="Remove review from Soup"/);
        assert.doesNotMatch(render(false), /Remove review from Soup/);
        assert.match(render(false), /Reviewed by Dinnerdesk/);
      }
    }
  } finally {
    await server.close();
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});
