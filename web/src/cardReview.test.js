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
        const recipe = { id: 1, name: "Soup", cooking_minutes: 25, reviewed: true, to_edit: true, coming_soon };
        const render = (admin) => renderToStaticMarkup(createElement(WeekProvider, null,
          createElement(Card, { recipe, admin, onChange() {} })));
        assert.match(render(true), /aria-pressed="true"[^>]*aria-label="Remove Kitchen-tested from Soup"/);
        assert.doesNotMatch(render(false), /Remove Kitchen-tested from Soup/);
        assert.match(render(true), /aria-pressed="true"[^>]*aria-label="Remove from To edit: Soup"/);
        assert.doesNotMatch(render(false), /Remove from To edit: Soup/);
        assert.equal((render(false).match(/aria-label="Kitchen-tested by Dinnerdesk"/g) || []).length, 1);
        assert.equal((render(true).match(/aria-label="Kitchen-tested by Dinnerdesk"/g) || []).length, 1);
        assert.doesNotMatch(render(false), /photo-reviewed-badge/);
        assert.match(render(false), /recipe-status-line/);
      }
    }
    const { ReviewedBadge, RecipeStatusLine } = await server.ssrLoadModule("/src/ReviewedBadge.jsx");
    for (const reviewed of [false, true]) {
      const metadata = renderToStaticMarkup(createElement(RecipeStatusLine, { recipe: { cooking_minutes: 25, reviewed } }));
      assert.match(metadata, /25 min/);
      assert.equal(metadata.includes("Kitchen-tested"), reviewed);
      assert.equal((metadata.match(/<svg /g) || []).length, Number(reviewed));
      const chip = renderToStaticMarkup(createElement(ReviewedBadge, { reviewed, detail: true }));
      assert.equal(chip.includes('aria-haspopup="dialog"'), reviewed);
      if (reviewed) {
        assert.match(chip, /We cooked this recipe in our own kitchen and made sure it works as written/);
        assert.doesNotMatch(chip, /Cooked start to finish|Times and temperatures checked|Amounts and servings confirmed/);
      } else assert.equal(chip, "");
    }
    const { TemplateCard } = await server.ssrLoadModule("/src/pages/Recipes.jsx");
    const template = renderToStaticMarkup(createElement(TemplateCard, { family: { id: "bowls", name: "Bowls" } }));
    assert.match(template, /aria-disabled="true"/);
    assert.match(template, /Coming soon/);
    assert.doesNotMatch(template, /<button|<a /);
    const { RecipeGallery } = await server.ssrLoadModule("/src/RecipeGallery.jsx");
    const shared = JSON.parse(readFileSync(new URL("../../tests/fixtures/recipe_photo_status.json", import.meta.url), "utf8"));
    const gallery = renderToStaticMarkup(createElement(RecipeGallery, { recipe: shared, canEdit: false }));
    assert.doesNotMatch(gallery, /Kitchen-tested|Developer tested|reviewed-badge/);
    assert.equal((gallery.match(/<img /g) || []).length, shared.photos.length);
    const noPhoto = renderToStaticMarkup(createElement(RecipeGallery, { recipe: { ...shared, photos: [] }, canEdit: false }));
    assert.doesNotMatch(noPhoto, /Kitchen-tested|Developer tested|reviewed-badge/);
    for (const reviewed of [false, true]) {
      for (const tested of [false, true]) {
        const recipe = { id: 1, name: "Soup", reviewed,
          photos: [{ path: "food/soup.jpg", primary: true, tested, ai: false, shared: false }] };
        const markup = renderToStaticMarkup(createElement(RecipeGallery, { recipe, canEdit: false }));
        assert.doesNotMatch(markup, /Kitchen-tested|Developer tested|reviewed-badge/);
        assert.equal((markup.match(/<img /g) || []).length, 1);
        assert.doesNotMatch(markup, /photo-status-badges/);
      }
    }
  } finally {
    await server.close();
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});
