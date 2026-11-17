const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function loadLab() {
  const calls = [];
  const app = {
    innerHTML: '', firstElementChild: {},
    addEventListener() {}, querySelector() { return null; },
    insertAdjacentHTML(_, html) { this.innerHTML += html; },
  };
  const window = { addEventListener() {} };
  window.self = window.top = window;
  const context = vm.createContext({
    URLSearchParams, location: { search: '?chrome=app' }, window,
    document: { getElementById() { return app; }, documentElement: { classList: { add() {} } } },
    localStorage: { getItem() { return null; }, setItem() {} },
    crypto: { randomUUID() { return 'test-session'; } },
    TASTE_SEEDS: [], TASTE_GROUPS: [],
    fetch: async (url, options) => { calls.push({ url, options }); return { ok: true }; },
  });
  const source = fs.readFileSync(path.join(__dirname, '../../tastelab/web/app.js'), 'utf8');
  // Expose the real engine without booting network requests or adding production test hooks.
  vm.runInContext(source.replace('  render();\n  boot();\n})();',
    '  globalThis.lab = { state, renderPlan, swipeCard, sendPhotoReport, decide, bindSwipe };\n})();'), context);
  return { ...context.lab, calls, app, context };
}

const recipe = { id: 'archive-12', recipe_id: 987, name: 'Lemon <chicken>', photo: '/meal.jpg', mins: 25 };

test('photo report uses the database recipe ID and photo reason, with trimmed optional notes', async () => {
  const lab = loadLab();
  Object.assign(lab.state, { screen: 'swipe', deck: [recipe], photoReport: recipe, photoReportNote: '  Wrong dish  ' });
  await lab.sendPhotoReport();
  assert.equal(lab.calls[0].url, '/api/recipes/987/report');
  assert.deepEqual(JSON.parse(lab.calls[0].options.body), { reason: 'photo', note: 'Wrong dish' });
  assert.equal(lab.state.photoReport, null);
  assert.equal(lab.state.reportedPhotos.has(recipe.id), true);
  assert.equal(lab.state.index, 0);
});

test('a failed photo report preserves the recipe and note and can be retried', async () => {
  const lab = loadLab();
  Object.assign(lab.state, { screen: 'swipe', deck: [recipe], photoReport: recipe, photoReportNote: 'My note' });
  lab.context.fetch = async () => ({ ok: false });
  await lab.sendPhotoReport();
  assert.match(lab.state.photoReportError, /try again/);
  assert.equal(lab.state.photoReport, recipe);
  assert.equal(lab.state.photoReportNote, 'My note');
  assert.equal(lab.state.photoReportSending, false);
  lab.context.fetch = async () => ({ ok: true });
  await lab.sendPhotoReport();
  assert.equal(lab.state.reportedPhotos.has(recipe.id), true);
});

test('reporting prevents advancing the swipe deck and ignores duplicate sends', async () => {
  const lab = loadLab();
  Object.assign(lab.state, { screen: 'swipe', deck: [recipe], photoReport: recipe });
  await lab.decide(true);
  assert.equal(lab.state.index, 0);
  assert.equal(lab.calls.length, 0);
  lab.state.photoReportSending = true;
  await lab.sendPhotoReport();
  assert.equal(lab.calls.length, 0);
});

test('only the signed-in current swipe card offers reporting, and success is visible', () => {
  const lab = loadLab();
  assert.doesNotMatch(lab.swipeCard(recipe, 'is-top'), /data-report-photo/);
  lab.state.signedIn = true;
  assert.match(lab.swipeCard(recipe, 'is-top'), /Report photo: Lemon &lt;chicken&gt;/);
  assert.doesNotMatch(lab.swipeCard(recipe, 'is-next'), /data-report-photo/);
  lab.state.reportedPhotos.add(recipe.id);
  assert.match(lab.swipeCard(recipe, 'is-top'), /Photo reported.*disabled/);
});

test('pressing report does not capture the pointer or begin swiping', () => {
  const lab = loadLab();
  const events = {};
  const card = { querySelector() { return null; }, addEventListener(name, fn) { events[name] = fn; },
    setPointerCapture() { assert.fail('button must retain its pointer'); } };
  lab.app.querySelector = () => card;
  lab.bindSwipe();
  events.pointerdown({ target: { closest() { return {}; } } });
  events.pointerup();
  assert.equal(lab.calls.length, 0);
});

test('plan tiles show the full escaped name and cooking time without extra nutrition', () => {
  const lab = loadLab();
  lab.state.plan = [{ ...recipe, calories: 700, protein: 40 }, { ...recipe, id: '2', mins: null }];
  const html = lab.renderPlan();
  assert.match(html, /Review your suggestions/);
  assert.match(html, /Lemon &lt;chicken&gt;/);
  assert.equal((html.match(/25 min/g) || []).length, 1);
  assert.doesNotMatch(html, /700 cal|40g protein|null min/);
});
