(() => {
  const params = new URLSearchParams(location.search);
  if (window.self !== window.top) document.documentElement.classList.add("in-frame");
  if (params.get("chrome") === "app") document.documentElement.classList.add("in-app");

  const SEED_IDS = TASTE_SEEDS;
  const SWIPE_GROUPS = TASTE_GROUPS;
  const AVOIDS = [
    "fish",
    "cilantro",
    "mushrooms",
    "onions",
    "bell peppers",
    "olives",
    "goat cheese",
    "nuts",
    "beans",
    "tofu",
    "eggplant",
    "brussels sprouts",
    "coconut",
    "spicy",
  ];
  const ALLERGENS = [
    ["soy", "Soy"],
    ["peanut", "Peanut"],
    ["tree-nuts", "Tree nuts"],
    ["dairy", "Dairy"],
    ["egg", "Egg"],
    ["gluten", "Gluten"],
    ["sesame", "Sesame"],
    ["fish", "Fish"],
    ["shellfish", "Shellfish"],
  ];
  // Same lists as Settings → Filters (app/domain/diet_filter.py; a test keeps them equal).
  const DIETS = [
    ["omnivore", "Omnivore"],
    ["vegetarian", "Vegetarian"],
    ["vegan", "Vegan"],
    ["pescatarian", "Pescatarian"],
    ["gluten-free", "Gluten-free"],
    ["dairy-free", "Dairy-free"],
  ];
  const MIN_POOL = 8;
  const FREE_MEALS = 4;
  // Suggested plans to judge in one session before "You're set" (#13). More verdicts teach
  // suggestions more; "Done for now" still ends early.
  const PLAN_ROUNDS = 3;
  const app = document.getElementById("app");
  const storedAnon = localStorage.getItem("dinnerdesk-taste-anon") || localStorage.getItem("weekplate-anon");
  const state = {
    screen: "loading",
    catalog: [],
    signedIn: false,
    profile: { diets: ["omnivore"], allergens: [], extraAllergen: "", dislikes: [], extraAvoid: "" },
    deck: [],
    index: 0,
    swipes: [],
    plan: [],
    marks: {},
    swapFrom: null,
    swapChoices: [],
    swapPick: null,
    plans: [],
    lastPlan: [],
    phase: "",
    round: 0,
    quizBack: null,
    sawPlan: false,
    prior: new Set(),
    priorLikes: new Set(),
    planDown: new Set(),
    openOther: { extraAllergen: false, extraAvoid: false },
    shown: {},
    planHits: {},
    sessionId: crypto.randomUUID(),
    anonId: storedAnon || crypto.randomUUID(),
    error: "",
    busy: false,
    didQuiz: false,
  };
  localStorage.setItem("dinnerdesk-taste-anon", state.anonId);

  const byId = (id) => state.catalog.find((r) => String(r.id) === String(id));
  const rid = (recipe) => String(recipe.id);

  const shuffle = (items) => {
    const out = [...items];
    for (let i = out.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  };

  const KEYS = {
    soy: ["soy", "soya", "tofu", "edamame", "tempeh", "miso"],
    peanut: ["peanut"],
    "tree-nuts": ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "macadamia"],
    dairy: ["milk", "butter", "cheese", "cream", "yogurt", "yoghurt", "parmesan", "feta", "mozzarella", "cheddar", "whey", "ghee"],
    egg: ["egg"],
    gluten: ["wheat", "flour", "bread", "pasta", "spaghetti", "linguine", "penne", "couscous", "panko", "breadcrumb", "soy sauce"],
    sesame: ["sesame", "tahini"],
    fish: ["salmon", "tuna", "cod", "halibut", "tilapia", "trout", "anchovy", "fish"],
    shellfish: ["shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster", "scallop"],
    cilantro: ["cilantro", "coriander"],
    mushrooms: ["mushroom"],
    onions: ["onion"],
    "bell peppers": ["bell pepper"],
    olives: ["olive"],
    "goat cheese": ["goat cheese", "chèvre", "chevre"],
    nuts: ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "peanut"],
    beans: ["black bean", "kidney bean", "pinto bean", "white bean", "chickpea", "garbanzo", "lentil", "cannellini"],
    tofu: ["tofu"],
    eggplant: ["eggplant"],
    "brussels sprouts": ["brussels sprout", "brussel sprout"],
    coconut: ["coconut"],
    meat: ["chicken", "beef", "pork", "turkey", "lamb", "bacon", "sausage", "steak", "ham", "prosciutto"],
    spicy: ["spicy", "jalapeño", "jalapeno", "sriracha", "chili flake", "cayenne", "hot sauce"],
  };

  const splitExtra = (raw) =>
    String(raw || "")
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter((s) => s.length >= 3);

  const allergenIds = () => {
    const extra = splitExtra(state.profile.extraAllergen).map((w) => {
      if (KEYS[w]) return w;
      const hit = ALLERGENS.find(([id, label]) => id === w || label.toLowerCase() === w);
      return hit ? hit[0] : w;
    });
    return [...new Set([...state.profile.allergens, ...extra])];
  };

  const dislikeIds = () => [...new Set([...state.profile.dislikes, ...splitExtra(state.profile.extraAvoid)])];

  const textOf = (recipe) =>
    `${recipe.name} ${(recipe.ingredients || []).filter((i) => !/chicken or vegetable broth/i.test(i)).join(" | ")}`.toLowerCase();

  const hitsKeys = (recipe, keys) => {
    const blob = textOf(recipe);
    return keys.some((k) => {
      if (k === "egg") return /(^|[^a-z])eggs?([^a-z]|$)/.test(blob);
      return blob.includes(k);
    });
  };

  const blocked = (recipe) => {
    if (allergenIds().some((id) => hitsKeys(recipe, KEYS[id] || [id]))) return true;
    const diets = state.profile.diets;
    if (diets.includes("vegan") && hitsKeys(recipe, [...KEYS.meat, ...KEYS.fish, ...KEYS.shellfish, ...KEYS.dairy, ...KEYS.egg, "honey"])) return true;
    if (diets.includes("vegetarian") && hitsKeys(recipe, [...KEYS.meat, ...KEYS.fish, ...KEYS.shellfish])) return true;
    if (diets.includes("pescatarian") && hitsKeys(recipe, KEYS.meat)) return true;
    if (diets.includes("gluten-free") && hitsKeys(recipe, KEYS.gluten)) return true;
    if (diets.includes("dairy-free") && hitsKeys(recipe, KEYS.dairy)) return true;
    return dislikeIds().some((id) => hitsKeys(recipe, KEYS[id] || [id]));
  };

  const rejected = (id) => {
    const key = String(id);
    if (state.planDown.has(key)) return true;
    if (state.swipes.some((s) => s.recipe_id === key && !s.liked)) return true;
    return state.prior.has(key) && !state.priorLikes.has(key);
  };

  const eligible = () => state.catalog.filter((r) => !blocked(r) && !rejected(r.id));
  const shownCount = (id) => state.shown[id] || 0;
  const planCount = (id) => state.planHits[id] || 0;
  const stillOpen = (recipe) => shownCount(recipe.id) < 3;
  const openPool = () => eligible().filter((r) => stillOpen(r));
  const planPool = () => openPool().filter((r) => planCount(r.id) < 2);
  const swipedIds = () => new Set(state.swipes.map((s) => s.recipe_id));
  const unswiped = () => openPool().filter((r) => !swipedIds().has(rid(r)) && !state.prior.has(rid(r)));

  const bumpShown = (rows) => {
    for (const r of rows) {
      if (!r) continue;
      state.shown[r.id] = shownCount(r.id) + 1;
    }
  };

  const bumpPlans = (rows) => {
    bumpShown(rows);
    for (const r of rows) {
      if (!r) continue;
      state.planHits[r.id] = planCount(r.id) + 1;
    }
  };

  const likedMeals = () => {
    const ids = [
      ...state.priorLikes,
      ...state.swipes.filter((s) => s.liked).map((s) => s.recipe_id),
      ...state.plans.filter((p) => p.verdict === "up").flatMap((p) => p.recipe_ids || []),
    ];
    return [...new Set(ids)].map(byId).filter((r) => r && !blocked(r) && !rejected(r.id));
  };

  const take = (n, lists, hold = []) => {
    const seen = new Set(hold.map(String));
    const out = [];
    for (const list of lists) {
      for (const r of shuffle(list)) {
        if (out.length >= n) return out;
        if (seen.has(rid(r))) continue;
        out.push(r);
        seen.add(rid(r));
      }
    }
    return out;
  };

  const pickSwipes = (n) => take(n, [unswiped()]);

  const pickGroupedSwipes = () => {
    const seen = swipedIds();
    const from = (ids) =>
      (ids || [])
        .map(byId)
        .filter((r) => r && !blocked(r) && !rejected(r.id) && stillOpen(r) && !seen.has(rid(r)) && !state.prior.has(rid(r)));
    const deck = [];
    for (const g of SWIPE_GROUPS) {
      const rec = shuffle(from(g.ids))[0] || shuffle(from(g.last))[0] || unswiped().find((r) => !seen.has(rid(r)));
      if (!rec) continue;
      seen.add(rid(rec));
      deck.push({ ...rec, group: g.id });
    }
    return deck;
  };

  const pickPlan = (n, hold = []) => {
    const last = new Set(state.lastPlan.map(String));
    const pool = planPool();
    const fresh = pool.filter((r) => !last.has(rid(r)));
    const likes = likedMeals().filter((r) => planCount(r.id) < 2);
    return take(n, [fresh, likes, pool], hold);
  };

  const counts = () => {
    const vote = new Map();
    for (const id of state.prior) vote.set(id, state.priorLikes.has(id));
    for (const swipe of state.swipes) vote.set(swipe.recipe_id, Boolean(swipe.liked));
    let likes = 0;
    let passes = 0;
    for (const up of vote.values()) {
      if (up) likes += 1;
      else passes += 1;
    }
    return { likes, passes };
  };

const macros = (r) => {
    const bits = [];
    if (r.mins) bits.push(`${r.mins} min`);
    if (r.calories) bits.push(`${r.calories} cal`);
    if (r.protein) bits.push(`${r.protein}g protein`);
    return bits.join(" · ");
  };

  const esc = (s) =>
    String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");

  const ICONS = {
    back: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    heart: '<path d="M12 20.5s-7.5-4.6-9.2-9.3C1.6 7.8 3.9 4.5 7.3 4.5c2 0 3.6 1.1 4.7 2.7 1.1-1.6 2.7-2.7 4.7-2.7 3.4 0 5.7 3.3 4.5 6.7-1.7 4.7-9.2 9.3-9.2 9.3z" fill="currentColor" stroke="none"/>',
    swap: '<path d="M7 7h12l-3.5-3.5M17 17H5l3.5 3.5"/>',
    up: '<path d="M7 11v9H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3zm0 0l4-8c1.7 0 3 1.3 3 3v3h5.2a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 18 20H7"/>',
    down: '<path d="M17 13V4h3a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-3zm0 0l-4 8c-1.7 0-3-1.3-3-3v-3H4.8a2 2 0 0 1-2-2.3l1.2-7A2 2 0 0 1 6 4h11"/>',
  };
  const icon = (name) =>
    `<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;

  const photo = (url, name, cls = "") => {
    const letter = esc((name || "?").slice(0, 1));
    if (!url) return `<div class="ph ${cls}">${letter}</div>`;
    return `<img class="${cls}" src="${esc(url)}" alt="" onerror="this.outerHTML='<div class=&quot;ph ${cls}&quot;>${letter}</div>'" />`;
  };

  const heroMeals = () => {
    const seen = new Set();
    const out = [];
    for (const rec of [...SEED_IDS.map(byId), ...state.catalog]) {
      if (!rec?.photo || seen.has(rec.id) || blocked(rec)) continue;
      seen.add(rec.id);
      out.push(rec);
      if (out.length === 3) break;
    }
    return out;
  };

  const steps = (on) =>
    `<div class="steps" aria-hidden="true">${[0, 1, 2, 3]
      .map((i) => `<span class="dot ${i === on ? "is-on" : i < on ? "is-done" : ""}"></span>`)
      .join("")}</div>`;

  const inFrame = window.self !== window.top;
  const tellParent = () => {
    if (!inFrame) return;
    const home = state.screen === "welcome" || state.screen === "loading" || state.screen === "error";
    window.parent.postMessage({ type: "taste-lab", home }, "*");
  };

  const head = (title, step, meta = "") => `
      <div class="top">
        <button type="button" class="lab-back" data-back aria-label="Back">${icon("back")}</button>
        ${title === "Taste Lab" && params.get("chrome") === "app" ? "" : `<h1 class="brand">${esc(title)}</h1>`}
        <div class="top-tools">
          ${step >= 0 ? steps(step) : ""}
          ${meta ? `<p class="progress">${esc(meta)}</p>` : ""}
        </div>
      </div>`;

  const banner = () => (state.error ? `<p class="err" role="alert">${esc(state.error)}</p>` : "");

  const otherValue = (name) => (name === "extraAllergen" ? state.profile.extraAllergen : state.profile.extraAvoid);
  const otherOpen = (name) => state.openOther[name] || Boolean(String(otherValue(name) || "").trim());
  const otherChip = (name) =>
    `<button type="button" class="chip ${otherOpen(name) ? "is-on" : ""}" data-other="${name}">Other</button>`;
  const otherField = (name) =>
    otherOpen(name)
      ? `<input class="field" name="${name}" value="${esc(otherValue(name))}" placeholder="Type a few, separated by commas" />`
      : "";

  const chips = (items, selected, key) =>
    items
      .map((item) => {
        const [id, label] = Array.isArray(item) ? item : [item, item];
        const on = selected.includes(id) ? "is-on" : "";
        return `<button type="button" class="chip ${on}" data-toggle="${key}" data-id="${esc(id)}" aria-pressed="${on ? "true" : "false"}">${esc(label)}</button>`;
      })
      .join("");

  const record = () => ({
    id: state.sessionId,
    created_at: new Date().toISOString(),
    profile: {
      diets: [...state.profile.diets],
      allergens: allergenIds(),
      dislikes: dislikeIds(),
    },
    swipes: state.swipes,
    plans: state.plans,
  });

  const save = async () => {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        anon_id: state.anonId,
        id: state.sessionId,
        kind: "snapshot",
        body: record(),
      }),
    });
    if (!response.ok) throw new Error(`Couldn't save (HTTP ${response.status})`);
    state.error = "";
  };

  // Signed in, these filters are the household's Settings → Filters: one list, edited from either
  // screen. Only the keys Taste Lab shows are sent; the server keeps cook time and anything else.
  const saveFilters = async () => {
    if (!state.signedIn) return;
    const response = await fetch("/api/household", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prefs: {
          filters: { diets: [...state.profile.diets], allergens: allergenIds(), avoids: dislikeIds() },
        },
      }),
    });
    if (!response.ok) throw new Error(`Couldn't save your filters (HTTP ${response.status})`);
  };

  const saveWithFilters = async () => {
    await save();
    await saveFilters();
  };

  const remember = (id, liked) => {
    const key = String(id);
    state.prior.add(key);
    if (liked) state.priorLikes.add(key);
    else state.priorLikes.delete(key);
  };

  const setPlan = (meals) => {
    state.plan = meals.slice(0, 4);
    state.lastPlan = state.plan.map((r) => rid(r));
  };

  const showPlan = (keep = []) => {
    const kept = keep.map(byId).filter((r) => r && !blocked(r) && !rejected(r.id));
    const added = pickPlan(4 - kept.length, kept.map((r) => rid(r)));
    bumpPlans(added);
    setPlan([...kept, ...added]);
    state.swapFrom = null;
    state.swapChoices = [];
    state.swapPick = null;
    if (!state.plan.length) {
      state.screen = "empty";
      render();
      return;
    }
    state.sawPlan = true;
    state.screen = "plan";
    render();
  };

  const swapPool = () => {
    const hold = new Set(state.plan.map((r) => rid(r)));
    return planPool().filter((r) => !hold.has(rid(r)));
  };

  const openSwap = (id) => {
    const choices = shuffle(swapPool()).slice(0, 4);
    if (!choices.length) {
      state.error = "Nothing else fits these filters.";
      render();
      return;
    }
    state.error = "";
    state.swapFrom = String(id);
    state.swapChoices = choices;
    state.swapPick = null;
    render();
  };

  const closeSwapSheet = () => {
    state.swapFrom = null;
    state.swapChoices = [];
    state.swapPick = null;
    render();
  };

  const applySwap = async () => {
    const next = byId(state.swapPick);
    if (!next || !state.swapFrom) return;
    const previous = state.plan.map((r) => rid(r));
    setPlan(state.plan.map((r) => (rid(r) === state.swapFrom ? next : r)));
    bumpPlans([next]);
    try {
      await save();
    } catch (error) {
      state.plan = previous.map(byId).filter(Boolean);
      state.lastPlan = previous;
      state.error = error.message;
      render();
      return;
    }
    state.swapFrom = null;
    state.swapChoices = [];
    state.swapPick = null;
    render();
  };

  const startSeed = () => {
    state.round = 0;
    state.phase = "seed";
    state.quizBack = null;
    state.deck = SEED_IDS.map(byId).filter((r) => r && !blocked(r) && !state.prior.has(rid(r)));
    if (!state.deck.length) {
      if (!state.didQuiz) {
        state.screen = "quiz";
        render();
        return;
      }
      startMore();
      return;
    }
    bumpShown(state.deck);
    state.index = 0;
    state.screen = "swipe";
    render();
  };

  const begin = () => {
    const midSeed = state.phase === "seed" && state.deck.length > 0;
    if (!state.didQuiz && midSeed && state.index < state.deck.length) {
      state.screen = "swipe";
      render();
      return;
    }
    if (!state.didQuiz && midSeed && state.index >= state.deck.length) {
      state.quizBack = null;
      state.screen = "quiz";
      render();
      return;
    }
    if (state.didQuiz && counts().likes + counts().passes > 0) {
      startFreeSwipes();
      return;
    }
    startSeed();
  };

  const startMore = () => {
    state.round = 0;
    state.quizBack = null;
    state.phase = "more";
    state.deck = pickGroupedSwipes();
    bumpShown(state.deck);
    state.index = 0;
    if (!state.deck.length) {
      showPlan();
      return;
    }
    state.screen = "swipe";
    render();
  };

  const startFreeSwipes = () => {
    state.round = 0;
    state.phase = "free";
    state.quizBack = null;
    state.deck = pickSwipes(FREE_MEALS);
    bumpShown(state.deck);
    state.index = 0;
    if (!state.deck.length) {
      showPlan();
      return;
    }
    state.screen = "swipe";
    render();
  };

  const resumeAfterFilters = () => {
    const back = state.quizBack;
    state.quizBack = null;
    if (back === "swipe") {
      state.deck = state.deck.filter((r) => !blocked(r));
      if (state.index >= state.deck.length) {
        if (state.phase === "seed" && !state.didQuiz) {
          state.screen = "quiz";
          render();
          return;
        }
        if (state.phase === "seed") {
          startMore();
          return;
        }
        showPlan();
        return;
      }
      state.screen = "swipe";
      render();
      return;
    }
    if (back === "plan") {
      showPlan(state.plan.filter((r) => !blocked(r)).map((r) => rid(r)));
      return;
    }
    state.screen = "welcome";
    render();
  };

  const afterQuiz = async () => {
    await saveWithFilters();
    state.didQuiz = true;
    if (eligible().length < MIN_POOL) {
      state.screen = "relax";
      render();
      return;
    }
    if (state.quizBack) {
      resumeAfterFilters();
      return;
    }
    startMore();
  };

  const goBack = async () => {
    if (state.swapFrom) {
      closeSwapSheet();
      return;
    }
    if (state.screen === "quiz" || state.screen === "relax") {
      await saveWithFilters();
      if (state.quizBack === "swipe" || state.quizBack === "plan") {
        resumeAfterFilters();
        return;
      }
      state.quizBack = null;
      state.screen = "welcome";
      render();
      return;
    }
    state.screen = "welcome";
    render();
  };

  const renderWelcome = () => {
    const meals = heroMeals();
    const mosaic = meals.length
      ? `<div class="hero-mosaic">${meals
          .map((r, i) => `<div class="hero-cell ${i === 0 ? "big" : ""}">${photo(r.photo, r.name)}</div>`)
          .join("")}</div>`
      : "";
    const { likes, passes } = counts();
    const started = likes + passes > 0;
    const summary = started
      ? `${likes} liked · ${passes} passed. A pass won’t be suggested again.`
      : "Like meals you’d cook. Pass the ones you wouldn’t. A few likes are enough to start.";
    const legal = state.signedIn
      ? "Likes, passes, and filters are saved for your household and used to suggest meals."
      : "Sign in so likes and passes stay with your household. A guest kitchen is shared.";
    return `
    <div class="shell">
      ${mosaic}
      <h1 class="page">${started ? "Pick up where you left off." : "What do you like to cook?"}</h1>
      <p class="lead">${esc(summary)}</p>
      ${banner()}
      ${
        state.catalog.length
          ? `<button type="button" class="btn primary" data-start>${started ? "Keep going" : "Start"}</button>`
          : `<p class="lead">No meals with photos are ready to swipe yet.</p>`
      }
      <button type="button" class="text-link" data-edit-filters>Edit filters</button>
      <p class="legal">${esc(legal)}</p>
    </div>`;
  };

  // Built to fit one iPhone 16 screen at standard text size (#11): flat sections instead of
  // cards, tighter chips, and the button docked at the bottom. Every option stays.
  const renderQuiz = () => `
    <div class="shell quiz">
      ${head("Filters", state.quizBack ? -1 : 1)}
      <p class="lead">We’ll hide meals that don’t fit.${state.signedIn ? " Same filters as Settings." : ""}</p>
      ${banner()}
      <section class="panel">
        <h2 class="block first">Diet</h2>
        <div class="chips">${chips(DIETS, state.profile.diets, "diets")}</div>
      </section>
      <section class="panel">
        <h2 class="block first">Allergies</h2>
        <div class="chips"><button type="button" class="chip ${!state.profile.allergens.length && !state.profile.extraAllergen ? "is-on" : ""}" data-clear="allergens">None</button>${chips(ALLERGENS, state.profile.allergens, "allergens")}${otherChip("extraAllergen")}</div>
        ${otherField("extraAllergen")}
      </section>
      <section class="panel">
        <h2 class="block first">I avoid</h2>
        <div class="chips"><button type="button" class="chip ${!state.profile.dislikes.length && !state.profile.extraAvoid ? "is-on" : ""}" data-clear="dislikes">None</button>${chips(AVOIDS, state.profile.dislikes, "dislikes")}${otherChip("extraAvoid")}</div>
        ${otherField("extraAvoid")}
      </section>
      <div class="quiz-dock"><button type="button" class="btn primary" data-after-quiz>${state.quizBack ? "Save filters" : "Continue"}</button></div>
    </div>`;

  const renderRelax = () => {
    const n = eligible().length;
    const dietChips = state.profile.diets.filter((d) => d !== "omnivore");
    const items = [
      ...dietChips.map((id) => {
        const label = (DIETS.find(([d]) => d === id) || [id, id])[1];
        return `<button type="button" class="chip is-on" data-drop-diet="${esc(id)}">${esc(label)}</button>`;
      }),
      ...dislikeIds().map((id) => `<button type="button" class="chip is-on" data-drop-dislike="${esc(id)}">${esc(id)}</button>`),
    ].join("");
    return `
    <div class="shell">
      ${head("Few meals match", 1)}
      <p class="lead">Only ${n} meal${n === 1 ? "" : "s"} fit. Tap a limit to drop it. Allergies stay on.</p>
      ${banner()}
      <section class="panel">
        <div class="chips">${items || "<p class='hint'>Only allergies are on, so the catalog is just that small.</p>"}</div>
      </section>
      <button type="button" class="btn primary" data-after-relax ${n ? "" : "disabled"}>Continue with ${n}</button>
    </div>`;
  };

  const swipeCard = (r, extra) => `
    <article class="card ${extra}">
      <span class="stamp yes">LIKE</span>
      <span class="stamp no">PASS</span>
      ${photo(r.photo, r.name)}
      <div class="card-shade">
        ${macros(r) ? `<p class="card-meta">${esc(macros(r))}</p>` : ""}
        <h2 class="card-name">${esc(r.name)}</h2>
      </div>
    </article>`;

  const renderSwipe = () => {
    const cur = state.deck[state.index];
    const nxt = state.deck[state.index + 1];
    if (!cur) {
      return `<div class="shell">${head("Keep going", -1)}${banner()}<p class="lead">No meals left to swipe.</p><button type="button" class="btn primary" data-see-plan>See a suggested plan</button></div>`;
    }
    const titles = { seed: "Would you cook this?", more: "A few more", free: "Keep going" };
    const step = state.phase === "seed" ? 0 : state.phase === "more" ? 2 : -1;
    return `
      <div class="shell tall">
        ${head(titles[state.phase] || "Would you cook this?", step, `${state.index + 1} / ${state.deck.length}`)}
        ${banner()}
        <div class="swipe-stage">
          ${nxt ? swipeCard(nxt, "is-next") : ""}
          ${swipeCard(cur, "is-top")}
        </div>
        <div class="swipe-bar">
          <button type="button" class="circle no" data-swipe="0" aria-label="Pass">${icon("x")}</button>
          <button type="button" class="circle yes" data-swipe="1" aria-label="Like">${icon("heart")}</button>
        </div>
        <button type="button" class="text-link" data-edit-filters>Edit filters</button>
        ${state.phase === "seed" ? "" : `<button type="button" class="text-link" data-finish>Done for now</button>`}
      </div>`;
  };

  const mealCard = (r) => `
    <article class="meal">
      <div class="meal-photo">
        ${photo(r.photo, r.name)}
        <span class="swap-badge" aria-hidden="true">${icon("swap")}</span>
      </div>
      <div class="meal-body">
        <h3 title="${esc(r.name)}">${esc(r.name)}</h3>
        <p>${esc(macros(r))}</p>
      </div>
    </article>`;

  const swapSheet = () => {
    if (!state.swapFrom) return "";
    const from = byId(state.swapFrom);
    const rows = state.swapChoices
      .map((r) => {
        const on = state.swapPick === rid(r) ? "is-on" : "";
        return `<button type="button" class="swap-row ${on}" data-choose="${esc(rid(r))}">
          ${photo(r.photo, r.name, "thumb")}
          <span><b>${esc(r.name)}</b><em>${esc(macros(r))}</em></span>
        </button>`;
      })
      .join("");
    return `
      <div class="sheet">
        <button type="button" class="sheet-bg" data-swap-back aria-label="Close"></button>
        <div class="sheet-card">
          <div class="swap-header">
            <button type="button" class="swap-back" data-swap-back aria-label="Back to suggested plan">${icon("back")}</button>
            <p class="kicker">Replace</p>
          </div>
          <h2 class="sheet-title">${from ? esc(from.name) : "This meal"}</h2>
          <div class="swap-list">${rows}</div>
          <div class="row-btns swap-actions">
            <button type="button" class="btn ghost" data-more-swaps>More options</button>
            <button type="button" class="btn primary" data-save-swap ${state.swapPick ? "" : "disabled"}>Save swap</button>
          </div>
        </div>
      </div>`;
  };

  const renderPlan = () => {
    const n = state.plan.length;
    const cards = state.plan
      .map((r) => `<button type="button" class="meal-hit" data-open-swap="${esc(rid(r))}" aria-label="Swap ${esc(r.name)}">${mealCard(r)}</button>`)
      .join("");
    const lead = n === 1 ? "One dinner that fits." : `${n} dinners that fit.`;
    return `
      <div class="shell wide">
        ${head("Suggested dinners", state.phase === "free" ? -1 : 3, `Plan ${Math.min(state.round + 1, PLAN_ROUNDS)} of ${PLAN_ROUNDS}`)}
        <p class="lead">${lead} Tap a meal to swap it. Not for us drops these meals from suggestions.</p>
        ${banner()}
        <div class="plan-grid">${cards}</div>
        <div class="dock">
          <div class="row-btns">
            <button type="button" class="btn bad" data-verdict="down">${icon("down")}<span>Not for us</span></button>
            <button type="button" class="btn ok" data-verdict="up">${icon("up")}<span>This plan works</span></button>
          </div>
          <button type="button" class="text-link" data-edit-filters>Edit filters</button>
          <button type="button" class="text-link" data-finish>Done for now</button>
        </div>
        ${swapSheet()}
      </div>`;
  };

  const renderDone = () => {
    const { likes, passes } = counts();
    return `
    <div class="shell">
      ${head("Taste Lab", -1)}
      <div class="thanks">
        <h1 class="page">You're set.</h1>
        <p class="lead">${likes} liked · ${passes} passed. When you make a meal plan, suggestions follow this.</p>
      </div>
      ${banner()}
      ${
        state.sawPlan
          ? `<button type="button" class="btn primary" data-keep-swiping>Keep swiping</button>`
          : `<button type="button" class="btn primary" data-see-plan>See a suggested plan</button>`
      }
      <button type="button" class="text-link" data-back>Done</button>
    </div>`;
  };

  const renderEmpty = () => `
    <div class="shell">
      ${head("No meals match", -1)}
      ${banner()}
      <section class="recovery" role="status">
        <h2>No more matching dinners</h2>
        <p>You’ve reached the end of meals that fit your filters and passes. Edit your filters to look for more options, or return to Recipes to choose meals yourself.</p>
        <p>Your allergies and passed meals stay saved.</p>
        <button type="button" class="btn primary" data-edit-filters>Edit filters</button>
      </section>
    </div>`;

  const renderError = () => `
    <div class="shell">
      <h1 class="page">Taste Lab didn't load</h1>
      <p class="lead">${esc(state.error || "Something went wrong.")}</p>
      <button type="button" class="btn primary" data-retry>Try again</button>
    </div>`;

  const renderLoading = () => `<div class="shell"><p class="lead">Loading meals…</p></div>`;

  const render = () => {
    const view = {
      loading: renderLoading,
      welcome: renderWelcome,
      quiz: renderQuiz,
      relax: renderRelax,
      swipe: renderSwipe,
      plan: renderPlan,
      done: renderDone,
      empty: renderEmpty,
      error: renderError,
    }[state.screen];
    app.innerHTML = (view || renderError)();
    tellParent();
    if (state.screen === "swipe") bindSwipe();
  };

  const bindSwipe = () => {
    const card = app.querySelector(".card.is-top");
    if (!card) return;
    let sx = 0;
    let dx = 0;
    let dragging = false;
    const yes = card.querySelector(".stamp.yes");
    const no = card.querySelector(".stamp.no");
    const paint = () => {
      card.style.transform = `translate(${dx}px, ${dx * 0.08}px) rotate(${dx / 18}deg)`;
      if (yes) yes.style.opacity = String(Math.min(1, Math.max(0, dx / 90)));
      if (no) no.style.opacity = String(Math.min(1, Math.max(0, -dx / 90)));
    };
    const end = () => {
      dragging = false;
      if (dx > 88) decide(true);
      else if (dx < -88) decide(false);
      else {
        dx = 0;
        card.style.transform = "";
        if (yes) yes.style.opacity = "0";
        if (no) no.style.opacity = "0";
      }
    };
    card.addEventListener("pointerdown", (e) => {
      dragging = true;
      sx = e.clientX;
      card.setPointerCapture(e.pointerId);
    });
    card.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      dx = e.clientX - sx;
      paint();
    });
    card.addEventListener("pointerup", end);
    card.addEventListener("pointercancel", end);
  };

  const decide = async (liked) => {
    if (state.busy || state.screen !== "swipe") return;
    const rec = state.deck[state.index];
    if (!rec) return;
    state.busy = true;
    state.swipes.push({
      recipe_id: rid(rec),
      liked,
      name: rec.name,
      phase: state.phase,
      group: rec.group || null,
    });
    state.index += 1;
    try {
      await save();
    } catch (error) {
      state.swipes.pop();
      state.index -= 1;
      state.busy = false;
      state.error = error.message;
      render();
      return;
    }
    remember(rid(rec), liked);
    state.busy = false;
    if (state.index >= state.deck.length) {
      if (state.phase === "seed" && !state.didQuiz) {
        state.quizBack = null;
        state.screen = "quiz";
        render();
        return;
      }
      if (state.phase === "seed") {
        startMore();
        return;
      }
      showPlan();
      return;
    }
    render();
  };

  const toggle = (list, value) => {
    const i = list.indexOf(value);
    if (i >= 0) list.splice(i, 1);
    else list.push(value);
  };

  const run = (work) => {
    if (state.busy) return;
    state.busy = true;
    Promise.resolve()
      .then(work)
      .catch((error) => {
        state.error = error.message || "Something went wrong.";
        render();
      })
      .finally(() => {
        state.busy = false;
      });
  };

  app.addEventListener("click", (e) => {
    const t = e.target.closest(
      "[data-more-swaps],[data-clear],[data-back],[data-start],[data-toggle],[data-other],[data-after-quiz],[data-after-relax],[data-drop-diet],[data-drop-dislike],[data-edit-filters],[data-swipe],[data-verdict],[data-open-swap],[data-choose],[data-save-swap],[data-swap-back],[data-keep-swiping],[data-see-plan],[data-finish],[data-retry]"
    );
    if (!t || state.busy) return;
    if (t.hasAttribute("data-back")) {
      run(goBack);
      return;
    }
    if (t.dataset.other) {
      const name = t.dataset.other;
      if (otherOpen(name)) {
        state.openOther[name] = false;
        if (name === "extraAllergen") state.profile.extraAllergen = "";
        if (name === "extraAvoid") state.profile.extraAvoid = "";
      } else {
        state.openOther[name] = true;
      }
      render();
      const box = app.querySelector(`[name="${name}"]`);
      if (box) box.focus();
      return;
    }
    if (t.hasAttribute("data-start")) {
      run(begin);
      return;
    }
    if (t.dataset.clear) { state.profile[t.dataset.clear] = []; state.profile[t.dataset.clear === "allergens" ? "extraAllergen" : "extraAvoid"] = ""; render(); return; }
    if (t.dataset.toggle) {
      const key = t.dataset.toggle;
      const style = new Set(["omnivore", "vegetarian", "vegan", "pescatarian"]);
      if (key === "diets" && style.has(t.dataset.id)) {
        state.profile.diets = state.profile.diets.filter((d) => !style.has(d));
        state.profile.diets.push(t.dataset.id);
      } else {
        toggle(state.profile[key], t.dataset.id);
      }
      if (key === "diets" && !state.profile.diets.length) state.profile.diets.push("omnivore");
      render();
      return;
    }
    if (t.hasAttribute("data-after-quiz")) {
      run(afterQuiz);
      return;
    }
    if (t.dataset.dropDiet) {
      state.profile.diets = state.profile.diets.filter((d) => d !== t.dataset.dropDiet);
      if (!state.profile.diets.length) state.profile.diets.push("omnivore");
      render();
      run(saveWithFilters);
      return;
    }
    if (t.dataset.dropDislike) {
      const id = t.dataset.dropDislike;
      state.profile.dislikes = state.profile.dislikes.filter((d) => d !== id);
      state.profile.extraAvoid = splitExtra(state.profile.extraAvoid).filter((d) => d !== id).join(", ");
      render();
      run(saveWithFilters);
      return;
    }
    if (t.hasAttribute("data-after-relax")) {
      run(async () => {
        await saveWithFilters();
        if (state.quizBack) resumeAfterFilters();
        else startMore();
      });
      return;
    }
    if (t.hasAttribute("data-edit-filters")) {
      state.quizBack = state.screen === "welcome" ? "welcome" : state.screen;
      state.screen = "quiz";
      state.error = "";
      render();
      return;
    }
    if (t.dataset.swipe) {
      decide(t.dataset.swipe === "1");
      return;
    }
    if (t.hasAttribute("data-more-swaps")) {
      const previous = new Set(state.swapChoices.map(rid));
      const choices = shuffle(swapPool().filter((r) => !previous.has(rid(r)))).slice(0, 4);
      if (choices.length) { state.swapChoices = choices; state.swapPick = null; }
      else state.error = "No more matching options. Go back and edit filters or choose your own meals in Recipes.";
      render(); return;
    }
    if (t.hasAttribute("data-swap-back")) {
      closeSwapSheet();
      return;
    }
    if (t.dataset.openSwap) {
      openSwap(t.dataset.openSwap);
      return;
    }
    if (t.dataset.choose) {
      state.swapPick = t.dataset.choose;
      render();
      return;
    }
    if (t.hasAttribute("data-save-swap")) {
      run(applySwap);
      return;
    }
    if (t.dataset.verdict) {
      const recipeIds = state.plan.map((r) => rid(r));
      const verdict = t.dataset.verdict;
      state.plans.push({
        recipe_ids: recipeIds,
        names: state.plan.map((r) => r.name),
        verdict,
        swap: [],
      });
      run(async () => {
        try {
          await save();
        } catch (error) {
          state.plans.pop();
          throw error;
        }
        for (const id of recipeIds) {
          const swiped = state.swipes.find((s) => s.recipe_id === id);
          if (swiped && verdict !== "down") continue;
          if (verdict === "down") {
            state.planDown.add(id);
            if (!swiped) remember(id, false);
          } else {
            remember(id, true);
          }
        }
        state.round += 1;
        const more = verdict === "down" || (state.round < PLAN_ROUNDS && planPool().length > 0);
        if (more) showPlan();
        else { state.screen = "done"; render(); }
      });
      return;
    }
    if (t.hasAttribute("data-keep-swiping")) {
      startFreeSwipes();
      return;
    }
    if (t.hasAttribute("data-see-plan")) {
      state.round = 0;
      showPlan();
      return;
    }
    if (t.hasAttribute("data-finish")) {
      run(async () => {
        await save();
        state.screen = "done";
        render();
      });
      return;
    }
    if (t.hasAttribute("data-retry")) {
      state.screen = "loading";
      state.error = "";
      render();
      boot();
    }
  });

  app.addEventListener("input", (e) => {
    if (e.target.name === "extraAvoid") state.profile.extraAvoid = e.target.value;
    if (e.target.name === "extraAllergen") state.profile.extraAllergen = e.target.value;
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.swapFrom) {
      closeSwapSheet();
      return;
    }
    if (state.screen !== "swipe") return;
    if (e.key === "ArrowRight") decide(true);
    if (e.key === "ArrowLeft") decide(false);
  });

  const applyTaste = (data) => {
    state.signedIn = Boolean(data.signed_in);
    state.prior = new Set();
    state.priorLikes = new Set();
    const profile = data.profile;
    if (profile && typeof profile === "object") {
      const knownDiet = new Set(DIETS.map(([id]) => id));
      const diets = (profile.diets || []).map(String).filter((id) => knownDiet.has(id));
      const knownAllergen = new Set(ALLERGENS.map(([id]) => id));
      const allergens = [];
      const extraAllergen = [];
      for (const id of profile.allergens || []) {
        const key = String(id);
        if (knownAllergen.has(key)) allergens.push(key);
        else if (key) extraAllergen.push(key);
      }
      const knownAvoid = new Set(AVOIDS);
      const dislikes = [];
      const extraAvoid = [];
      for (const id of profile.dislikes || []) {
        const key = String(id);
        if (knownAvoid.has(key)) dislikes.push(key);
        else if (key) extraAvoid.push(key);
      }
      state.profile = {
        diets: diets.length ? diets : ["omnivore"],
        allergens,
        extraAllergen: extraAllergen.join(", "),
        dislikes,
        extraAvoid: extraAvoid.join(", "),
      };
      state.openOther.extraAllergen = extraAllergen.length > 0;
      state.openOther.extraAvoid = extraAvoid.length > 0;
    }
    for (const vote of data.votes || []) {
      const id = String(vote.recipe_id || "");
      if (!id) continue;
      state.prior.add(id);
      if (vote.liked) state.priorLikes.add(id);
    }
    const diets = state.profile.diets.filter((d) => d !== "omnivore");
    state.didQuiz = state.prior.size > 0 || diets.length > 0 || allergenIds().length > 0 || dislikeIds().length > 0;
  };

  const boot = () => {
    Promise.all([fetch("/api/catalog"), fetch(`/api/taste?anon=${encodeURIComponent(state.anonId)}`)])
      .then(async ([catalogRes, tasteRes]) => {
        if (!catalogRes.ok) throw new Error(`Couldn't load meals (HTTP ${catalogRes.status})`);
        if (!tasteRes.ok) throw new Error(`Couldn't load your taste (HTTP ${tasteRes.status})`);
        const catalog = await catalogRes.json();
        const taste = await tasteRes.json();
        state.catalog = catalog.recipes || [];
        applyTaste(taste);
        if (params.get("swipe") === "1") {
          begin();
          return;
        }
        state.screen = "welcome";
        render();
      })
      .catch((error) => {
        state.screen = "error";
        state.error = error.message || "Taste Lab didn't load.";
        render();
      });
  };

  render();
  boot();
})();
