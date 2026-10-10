import FoodPhoto from "../FoodPhoto.jsx";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { RecipeCard, RecipeRow, hasTag } from "../cards.jsx";
import { Icon } from "../icons.jsx";
import { go } from "../nav.js";

const FILTERS = [
  ["all", "All"],
  ["pantry", "Uses pantry"],
  ["fav", "Your favorites"],
  ["try", "To try"],
  ["popular", "Popular"],
  ["quick", "Quick"],
  ["hidden", "Hidden"],
];
const SORTS = [
  ["name", "A–Z"],
  ["time", "Time"],
];
const STAPLE = /^(salt|black pepper|pepper|olive oil|extra virgin olive oil|vegetable oil|neutral cooking oil|canola oil|oil|water|cooking spray)$/;

const LIST_TITLES = {
  suggestions: "Suggestions",
  fav: "Your Favorites",
  try: "To try",
  popular: "Most Popular",
  mine: "Your Recipes",
  simple: "Super simple",
  budget: "Budget friendly",
  pantry: "Uses pantry",
  sauces: "Sauces & dressings",
  hidden: "Hidden",
  templates: "Templates",
  all: "All recipes",
};

function prettyFamily(id) {
  return String(id || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function browseQuery() {
  const p = new URLSearchParams(window.location.search);
  return {
    list: p.get("list"),
    family: p.get("family") || p.get("tag"),
  };
}

function recipesForFamily(family, pool) {
  if (!family) return [];
  const byId = new Map(pool.map((r) => [r.id, r]));
  return (family.recipes || []).map((item) => byId.get(item.id)).filter(Boolean);
}

function norm(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const STOP = new Set(["a", "an", "and", "the", "with", "or", "of", "in", "for", "on", "to"]);

function searchTokens(s) {
  return norm(s)
    .split(" ")
    .filter((t) => t.length > 1 && !STOP.has(t));
}

function ingredientText(recipe) {
  return (recipe.ingredients || [])
    .map((i) => (typeof i === "string" ? i : i?.name || ""))
    .join(" ");
}

function recipeHay(recipe) {
  return `${norm(recipe.name)} ${norm(ingredientText(recipe))}`;
}

function tokenHit(hay, token) {
  if (hay.includes(token)) return true;
  return hay.split(" ").some((w) => w.startsWith(token) || token.startsWith(w));
}

function scoreRecipe(recipe, tokens) {
  const name = norm(recipe.name);
  const hay = recipeHay(recipe);
  let score = 0;
  let hits = 0;
  for (const t of tokens) {
    const inName = tokenHit(name, t);
    const inHay = inName || tokenHit(hay, t);
    if (!inHay) continue;
    hits += 1;
    score += inName ? 10 : 4;
    if (name.split(" ").includes(t)) score += 6;
  }
  return { recipe, score, hits, needed: tokens.length };
}

function rankSearch(pool, query) {
  const tokens = searchTokens(query);
  if (!tokens.length) return { rows: pool, note: "" };
  const scored = pool.map((r) => scoreRecipe(r, tokens)).filter((x) => x.hits > 0);
  scored.sort((a, b) => b.score - a.score || a.recipe.name.localeCompare(b.recipe.name));
  if (!scored.length) return { rows: [], note: "none" };
  const all = scored.filter((x) => x.hits === x.needed);
  if (all.length) return { rows: all.map((x) => x.recipe), note: "" };
  return {
    rows: scored.map((x) => x.recipe),
    note: "closest",
  };
}

function suggestionPool(popular, meals, decorated) {
  const seen = new Set();
  const out = [];
  for (const r of [...popular, ...meals, ...decorated]) {
    if (!r || seen.has(r.id)) continue;
    seen.add(r.id);
    out.push(r);
    if (out.length >= 12) break;
  }
  return out;
}

function isExtra(r) {
  const tags = r.tags || [];
  if (tags.includes("main_dish") || tags.includes("full_meal")) return false;
  return tags.some((t) => t === "sauce" || t === "dressing" || t === "component");
}

function isMeal(r) {
  return !isExtra(r);
}

function nameHits(ingredient, pantryHave) {
  if (pantryHave.has(ingredient)) return true;
  for (const p of pantryHave) {
    if (p.length < 3) continue;
    if (ingredient === p || ingredient.startsWith(`${p} `) || ingredient.endsWith(` ${p}`) || ingredient.includes(` ${p} `)) {
      return true;
    }
  }
  return false;
}

function usesPantry(r, pantryHave) {
  if (!pantryHave.size) return false;
  const ings = (r.ingredients || []).map(norm).filter(Boolean);
  if (!ings.length) return false;
  const hits = ings.filter((n) => nameHits(n, pantryHave)).length;
  return hits >= 2 || (hits >= 1 && hits / ings.length >= 0.4);
}

function isBudget(r) {
  const n = (r.ingredients || []).map(norm).filter((x) => x && !STAPLE.test(x)).length;
  return n > 0 && n <= 8;
}

function browseOrder(rows) {
  const seed = Math.floor(Date.now() / 86400000);
  const score = (recipe) => { const value = recipe.id ^ seed; return (Math.imul(value ^ (value >>> 16), 0x45d9f3b) >>> 0); };
  return [...rows].sort((a, b) => score(a) - score(b));
}

function Row({ title, onSeeAll, children, empty }) {
  const has = Boolean(children);
  if (!has && !empty) return null;
  return (
    <section className="recipe-browse-row">
      <div className="section-head flush">
        <h2>{title}</h2>
        {onSeeAll ? (
          <button type="button" className="text-link" aria-label={`See all ${title}`} onClick={onSeeAll}>
            See all
          </button>
        ) : null}
      </div>
      <div className="h-scroll">{has ? children : <p className="help" data-tip="recipes.row-empty">{empty}</p>}</div>
    </section>
  );
}

function TemplateCard({ family, onOpen }) {
  return (
    <div className="card">
      <div className="card-img">
        <button type="button" className="card-open" onClick={() => onOpen(family)}>
          <FoodPhoto path={family.photo_path} />
        </button>
      </div>
      <button type="button" className="card-open" onClick={() => onOpen(family)}>
        <p className="card-name">{prettyFamily(family.name || family.id)}</p>
        <p className="card-meta">Template</p>
      </button>
    </div>
  );
}

export function Recipes() {
  const searchRef = useRef(null);
  const addRef = useRef(null);
  const [showSearch, setShowSearch] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState([]);
  const [sort, setSort] = useState("name");
  const [list, setList] = useState(null);
  const [suggestedIds, setSuggestedIds] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [hiddenRecipes, setHiddenRecipes] = useState([]);
  const [families, setFamilies] = useState([]);
  const [familyId, setFamilyId] = useState(null);
  const [pantryHave, setPantryHave] = useState(new Set());
  const [err, setErr] = useState("");

  useEffect(() => { api.suggestedRecipes().then((box) => setSuggestedIds(box.recipe_ids)).catch((e) => setErr(e.message)); }, []);
  useEffect(() => {
    function apply() {
      const { list: listParam, family } = browseQuery();
      if (family) {
        setFamilyId(family);
        setList(null);
        setShowSearch(false);
        return;
      }
      setFamilyId(null);
      if (
        listParam === "fav" ||
        listParam === "mine" ||
        listParam === "try" ||
        listParam === "sauces" ||
        listParam === "hidden" ||
        listParam === "templates"
      ) {
        setList(listParam);
      }
    }
    apply();
    window.addEventListener("popstate", apply);
    return () => window.removeEventListener("popstate", apply);
  }, []);

  useEffect(() => {
    Promise.all([
      api.recipes({ limit: 500 }),
      api.recipes({ limit: 500, hidden: true }),
      api.pantry(),
      api.templates(),
    ])
      .then(([rec, hidden, pantry, tmpl]) => {
        setRecipes(rec.recipes);
        setHiddenRecipes(hidden.recipes || []);
        setFamilies(tmpl.families || []);
        setPantryHave(
          new Set(
            (pantry.items || [])
              .filter((i) => i.have && !i.never_shop)
              .map((i) => norm(i.name))
              .filter(Boolean),
          ),
        );
      })
      .catch((e) => setErr(e.message));
  }, []);

  const decorated = useMemo(
    () =>
      recipes.map((r) => ({
        ...r,
        usesPantry: usesPantry(r, pantryHave),
        budget: isBudget(r),
      })),
    [recipes, pantryHave],
  );

  function patchRecipe(next) {
    setRecipes((cur) => cur.map((r) => (r.id === next.id ? { ...r, ...next } : r)));
  }

  const yours = decorated.filter((r) => r.favorited);
  const toTry = decorated.filter((r) => r.to_try);
  const meals = decorated.filter(isMeal);
  const sauces = decorated.filter(isExtra);
  const popular = meals.filter((r) => hasTag(r, "popular"));
  const mine = decorated.filter((r) => !r.catalog);
  const hiddenList = hiddenRecipes;
  const simple = meals.filter((r) => (r.cooking_minutes || 99) <= 20);
  const budget = meals.filter((r) => r.budget);
  const pantryRow = meals.filter((r) => r.usesPantry);

  const inList = Boolean(list) || showSearch || Boolean(familyId);

  const { visible, searchNote } = useMemo(() => {
    const needle = q.trim();
    const buckets = {
      fav: yours,
      suggestions: suggestedIds.map((id) => recipes.find((r) => r.id === id)).filter(Boolean),
      try: toTry,
      popular,
      mine,
      pantry: pantryRow,
      simple,
      budget,
      sauces,
      hidden: hiddenList,
      all: meals,
    };
    let rows = meals;
    if (showSearch) {
      const hiddenOn = filters.includes("hidden");
      rows = hiddenOn
        ? hiddenList.map((r) => ({
            ...r,
            usesPantry: usesPantry(r, pantryHave),
            budget: isBudget(r),
          }))
        : decorated;
      if (filters.includes("fav")) rows = rows.filter((r) => r.favorited);
      if (filters.includes("try")) rows = rows.filter((r) => r.to_try);
      if (filters.includes("popular")) rows = rows.filter((r) => hasTag(r, "popular"));
      if (filters.includes("pantry")) rows = rows.filter((r) => r.usesPantry);
      if (filters.includes("quick")) rows = rows.filter((r) => (r.cooking_minutes || 99) <= 30);
    } else if (familyId) {
      rows = recipesForFamily(
        families.find((f) => f.id === familyId),
        decorated,
      );
    } else if (list && buckets[list]) {
      rows = buckets[list];
    }
    let note = "";
    if (showSearch && needle) {
      let ranked = rankSearch(rows, needle);
      if (!ranked.rows.length && filters.length) {
        ranked = rankSearch(decorated, needle);
        if (ranked.rows.length) note = "Nothing in this filter. Matches from all recipes:";
        else note = ranked.note;
      } else {
        note = ranked.note;
      }
      rows = ranked.rows;
      if (!rows.length) {
        rows = suggestionPool(popular, meals, decorated);
        note = "none";
      }
    } else if (!familyId) {
      rows = [...rows].sort((a, b) => {
        if (showSearch && sort === "time") return (a.cooking_minutes || 999) - (b.cooking_minutes || 999);
        return a.name.localeCompare(b.name);
      });
    }
    if (showSearch && needle && sort === "time") {
      rows = [...rows].sort((a, b) => (a.cooking_minutes || 999) - (b.cooking_minutes || 999));
    }
    return { visible: rows, searchNote: note };
  }, [
    suggestedIds,
    recipes,
    decorated,
    yours,
    toTry,
    popular,
    mine,
    pantryRow,
    simple,
    budget,
    sauces,
    hiddenList,
    meals,
    list,
    familyId,
    families,
    q,
    filters,
    sort,
    showSearch,
    pantryHave,
  ]);

  useEffect(() => {
    if (!showAdd) return undefined;
    function onDoc(e) {
      if (!addRef.current?.contains(e.target)) setShowAdd(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [showAdd]);

  function openSearch() {
    setShowSearch(true);
    setShowAdd(false);
    setList(null);
    setFamilyId(null);
    setTimeout(() => searchRef.current?.focus(), 0);
  }

  function backToBrowse() {
    setList(null);
    setFamilyId(null);
    setQ("");
    setFilters([]);
    setSort("name");
    setShowSearch(false);
    go("/recipes");
  }

  function openFamily(family) {
    setShowSearch(false);
    setShowAdd(false);
    setList(null);
    setFamilyId(family.id);
    go(`/recipes?family=${encodeURIComponent(family.id)}`);
  }

  function openTemplates() {
    setShowSearch(false);
    setShowAdd(false);
    setFamilyId(null);
    setList("templates");
    go("/recipes?list=templates");
  }

  return (
    <section className="screen">
      <header className="top between">
        {inList ? (
          <button type="button" className="icon-btn" onClick={backToBrowse} aria-label="Back">
            ×
          </button>
        ) : (
          <h1 className="top-title flush">Recipes</h1>
        )}
        <div className="top-actions">
          {!showSearch && (
            <button type="button" className="icon-btn is-search" onClick={openSearch} aria-label="Search">
              <Icon name="search" size={26} />
            </button>
          )}
          <div className="add-menu-wrap" ref={addRef}>
            <button
              type="button"
              className="icon-btn is-add"
              onClick={() => setShowAdd((v) => !v)}
              aria-label="Add recipe"
              aria-expanded={showAdd}
              aria-haspopup="menu"
            >
              <Icon name="plus" size={24} />
            </button>
            {showAdd && (
              <div className="add-menu" role="menu">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setShowAdd(false);
                    go("/recipes/new?from=url");
                  }}
                >
                  Add by URL
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setShowAdd(false);
                    go("/recipes/new");
                  }}
                >
                  Custom add
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setShowAdd(false);
                    openTemplates();
                  }}
                >
                  From a template
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
      {inList && !showSearch && (
        <h1 className="top-title list-title">
          {familyId ? prettyFamily(familyId) : LIST_TITLES[list] || "Recipes"}
        </h1>
      )}
      {showSearch && (
        <div className="scroll-pad-x">
          <input
            ref={searchRef}
            className="field-input tight"
            placeholder="Search recipes or ingredients"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <div className="chip-row flush-chips">
            {FILTERS.map(([k, label]) => {
              const on = k === "all" ? filters.length === 0 : filters.includes(k);
              return (
                <button
                  key={k}
                  type="button"
                  className={`chip${on ? " is-on" : ""}`}
                  aria-pressed={on}
                  onClick={() => {
                    if (k === "all") {
                      setFilters([]);
                      return;
                    }
                    setFilters((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]));
                  }}
                >
                  {label}
                </button>
              );
            })}
            {SORTS.map(([k, label]) => (
              <button key={k} type="button" className={`chip${sort === k ? " is-on" : ""}`} onClick={() => setSort(k)}>
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        {!inList && (
          <>
            {!!suggestedIds.length && <Row title="Suggestions" onSeeAll={() => setList("suggestions")}>
              {suggestedIds.map((id) => recipes.find((r) => r.id === id)).filter(Boolean).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />)}
            </Row>}
            <Row title="Your Favorites" onSeeAll={() => setList("fav")} empty="Heart a recipe to keep it here.">
              {yours.length ? browseOrder(yours).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />) : null}
            </Row>
            <Row title="To try" onSeeAll={() => setList("try")}>
              {toTry.length ? browseOrder(toTry).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />) : null}
            </Row>
            <Row title="Create from a template" onSeeAll={openTemplates}>
              {families.some((f) => (f.recipes || []).length)
                ? families
                    .filter((f) => (f.recipes || []).length)
                    .map((f) => <TemplateCard key={f.id} family={f} onOpen={openFamily} />)
                : null}
            </Row>
            <Row title="Most Popular" onSeeAll={() => setList("popular")}>
              {popular.length ? browseOrder(popular).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />) : null}
            </Row>
            <Row title="Your Recipes" onSeeAll={() => setList("mine")}>
              {mine.length ? browseOrder(mine).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />) : null}
            </Row>
            <Row title="Super simple" onSeeAll={() => setList("simple")}>
              {simple.length ? browseOrder(simple).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />) : null}
            </Row>
            <Row title="Budget friendly" onSeeAll={() => setList("budget")}>
              {budget.length ? browseOrder(budget).slice(0, 16).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />) : null}
            </Row>
            <Row title="Uses pantry" onSeeAll={() => setList("pantry")}>
              {pantryRow.length ? browseOrder(pantryRow).slice(0, 12).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />) : null}
            </Row>
            <Row title="Sauces & dressings" onSeeAll={() => setList("sauces")}>
              {sauces.length ? browseOrder(sauces).map((r) => <RecipeCard key={r.id} recipe={r} onChange={patchRecipe} />) : null}
            </Row>
            <div className="section-head flush">
              <h2>All recipes</h2>
            </div>
            <div className="recipe-list">
              {meals
                .slice()
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((r) => (
                  <RecipeRow key={r.id} recipe={r} onChange={patchRecipe} />
                ))}
            </div>
            {hiddenList.length > 0 ? (
              <p className="help">
                <button type="button" className="text-link" onClick={() => setList("hidden")}>
                  Hidden recipes ({hiddenList.length})
                </button>
              </p>
            ) : null}
          </>
        )}
        {inList && list === "templates" && (
          <div>
            {families.map((f) => (
              <button key={f.id} type="button" className="list-link" onClick={() => openFamily(f)}>
                {prettyFamily(f.name || f.id)}
                <em>{(f.recipes || []).length}</em>
              </button>
            ))}
          </div>
        )}
        {inList && list !== "templates" && (
          <div className="recipe-list">
            {showSearch && q.trim() && searchNote === "closest" && (
              <p className="search-note">No recipe used every word. Closest matches:</p>
            )}
            {showSearch && q.trim() && searchNote === "none" && (
              <p className="search-note">No matches for “{q.trim()}”. Here are some ideas:</p>
            )}
            {showSearch && searchNote.startsWith("Nothing in this filter") && (
              <p className="search-note">{searchNote}</p>
            )}
            {visible.map((r) => (
              <RecipeRow key={r.id} recipe={r} onChange={patchRecipe} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
