import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

test("thumbnail admin controls and Coming soon previews expose the correct states", async () => {
  const previousWindow = globalThis.window;
  globalThis.window = { location: { pathname: "/recipes", search: "" }, addEventListener() {} };
  const server = await createServer({ root: fileURLToPath(new URL("../", import.meta.url)),
    server: { middlewareMode: true }, appType: "custom" });
  try {
    const { RecipeCard, RecipeRow } = await server.ssrLoadModule("/src/cards.jsx");
    const { WeekProvider } = await server.ssrLoadModule("/src/week.jsx");
    for (const Card of [RecipeCard, RecipeRow]) {
      for (const coming_soon of [false, true]) {
        const recipe = { id: 1, name: "Soup", reviewed: true, to_edit: true, coming_soon };
        const render = (admin) => renderToStaticMarkup(createElement(WeekProvider, null,
          createElement(Card, { recipe, admin, onChange() {} })));
        assert.match(render(true), /aria-pressed="true"[^>]*aria-label="Remove review from Soup"/);
        assert.doesNotMatch(render(false), /Remove review from Soup/);
        assert.match(render(true), /aria-pressed="true"[^>]*aria-label="Remove from To edit: Soup"/);
        assert.doesNotMatch(render(false), /Remove from To edit: Soup/);
        assert.equal((render(false).match(/aria-label="Reviewed by Dinnerdesk"/g) || []).length, 1);
        assert.equal((render(true).match(/aria-label="Reviewed by Dinnerdesk"/g) || []).length, 0);
        assert.match(render(false), /class="reviewed-badge photo-reviewed-badge"/);
      }
    }
    const { TemplateCard } = await server.ssrLoadModule("/src/pages/Recipes.jsx");
    const template = renderToStaticMarkup(createElement(TemplateCard, { family: { id: "bowls", name: "Bowls" } }));
    assert.match(template, /aria-disabled="true"/);
    assert.match(template, /Coming soon/);
    assert.doesNotMatch(template, /<button|<a /);
    const { RecipeGallery } = await server.ssrLoadModule("/src/RecipeGallery.jsx");
    const shared = JSON.parse(readFileSync(new URL("../../tests/fixtures/recipe_photo_status.json", import.meta.url), "utf8"));
    const gallery = renderToStaticMarkup(createElement(RecipeGallery, { recipe: shared, canEdit: false }));
    assert.match(gallery, /Reviewed by Dinnerdesk/);
    assert.match(gallery, /Developer tested:/);
    assert.equal((gallery.match(/<img /g) || []).length, shared.photos.length);
    const noPhoto = renderToStaticMarkup(createElement(RecipeGallery, { recipe: { ...shared, photos: [] }, canEdit: false }));
    assert.equal((noPhoto.match(/aria-label="Reviewed by Dinnerdesk"/g) || []).length, 1);
    for (const reviewed of [false, true]) {
      for (const tested of [false, true]) {
        const recipe = { id: 1, name: "Soup", reviewed,
          photos: [{ path: "food/soup.jpg", primary: true, tested, ai: false, shared: false }] };
        const markup = renderToStaticMarkup(createElement(RecipeGallery, { recipe, canEdit: false }));
        assert.equal(markup.includes('aria-label="Reviewed by Dinnerdesk"'), reviewed);
        assert.equal(markup.includes('aria-label="Developer tested:'), tested);
        assert.equal((markup.match(/<img /g) || []).length, 1);
        if (reviewed || tested) assert.match(markup, /photo-status-badges/);
      }
    }
  } finally {
    await server.close();
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});
