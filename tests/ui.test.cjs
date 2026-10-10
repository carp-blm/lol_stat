const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');
const fixture = path.join(__dirname, '..', 'test-results', 'ui-fixture');
const original = JSON.parse(fs.readFileSync(path.join(fixture, 'site.json'), 'utf8'));
const details = JSON.parse(fs.readFileSync(path.join(fixture, 'details.json'), 'utf8'));
const flush = () => new Promise(resolve => setImmediate(resolve));

function page(publisher = false) {
  let html = fs.readFileSync(path.join(fixture, 'index.html'), 'utf8');
  if (publisher) html = html.replace('id="runtime-data">{"publisher":false}', 'id="runtime-data">{"publisher":true,"token":"test-csrf"}');
  const state = { published: structuredClone(original), errors: [], requests: [], rejectDetails: false };
  const console = new VirtualConsole();
  console.on('jsdomError', error => state.errors.push(error.message));
  const dom = new JSDOM(html, {
    url: 'https://counter-note.test/lol_stat/', runScripts: 'dangerously', virtualConsole: console,
    beforeParse(window) {
      window.structuredClone = structuredClone;
      window.matchMedia = () => ({matches: false, addEventListener() {}, removeEventListener() {}});
      window.HTMLElement.prototype.scrollIntoView = function () {};
      window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
      window.HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new window.Event('close')); };
      window.fetch = async (url, options = {}) => {
        state.requests.push({ url, options });
        let value;
        if (url === '/api/edits') {
          assert.equal(options.headers['X-Counter-Token'], 'test-csrf');
          value = JSON.parse(options.body);
          state.published = { ...state.published, board: value.board, revision: 'saved-revision' };
          value = state.published;
        } else if (url.startsWith('release.json')) value = { revision: state.published.revision };
        else if (url.startsWith('data/site.json')) value = state.published;
        else if (url.endsWith('bottom-Tristana.json')) {
          if (state.rejectDetails) throw new Error('테스트 연결 실패');
          value = details;
        } else throw new Error('Unexpected request ' + url);
        return { ok: true, json: async () => structuredClone(value) };
      };
    }
  });
  const document = dom.window.document;
  const click = selector => { const target = document.querySelector(selector); assert.ok(target, selector); target.click(); };
  const chooseMatchup = () => { click('[data-lane="bottom"]'); click('#champ-opponent-Tristana'); };
  return { dom, document, state, click, chooseMatchup };
}

test('visitors can inspect matchup-specific choices and all build stages without editing access', async () => {
  const p = page();
  try {
    assert.equal(p.document.querySelector('[data-action="edit"]'), null);
    assert.match(p.document.querySelector('.data-meta').textContent, /패치 16.19/);
    p.chooseMatchup();
    assert.ok(p.document.querySelector('[data-zone="both"] .early-warning'));
    p.click('[data-zone="both"] [data-id="Ashe"]');
    await flush();
    assert.equal(p.document.querySelector('#stats-dialog').open, true);
    assert.match(p.document.querySelector('#stats-title').textContent, /트리스타나.*애쉬/);
    assert.equal(p.document.querySelectorAll('.metric-card').length, 4);
    assert.equal(p.document.querySelectorAll('[data-recommend-feature]').length, 5);
    assert.ok(p.document.querySelector('tr.significant .fdr-badge'));
    p.click('[data-recommend-feature="build"]');
    assert.equal(p.document.querySelectorAll('[data-build-stage]').length, 5);
    p.click('[data-build-stage="1"]');
    assert.ok(p.document.querySelector('tr.significant .fdr-badge'));
    p.click('[data-build-stage="5"]');
    assert.equal(p.document.querySelectorAll('.build-table tbody tr:first-child .item-chip').length, 5);
    assert.match(p.document.querySelector('.build-table').textContent, /전체 승률.*다른 상대 승률/);
    p.click('#stats-close');
    assert.equal(p.document.querySelector('#stats-dialog').open, false);
    assert.deepEqual(p.state.errors, []);
  } finally { p.dom.window.close(); }
});

test('published changes replace visitor data and close an outdated detail dialog', async () => {
  const p = page();
  try {
    p.chooseMatchup();
    p.click('[data-zone="both"] [data-id="Ashe"]');
    await flush();
    p.state.published.revision = 'new-revision';
    p.state.published.board.matchups.bottom.Tristana = { both: [], pressure: [], solo: ['Ashe'] };
    p.click('[data-action="refresh-data"]');
    await flush();
    assert.ok(p.document.querySelector('[data-zone="solo"] [data-id="Ashe"]'));
    assert.equal(p.document.querySelector('[data-zone="both"] [data-id="Ashe"]'), null);
    assert.equal(p.document.querySelector('#stats-dialog').open, false);
    assert.deepEqual(p.state.errors, []);
  } finally { p.dom.window.close(); }
});

test('publisher can click to add and remove counters, warnings and tiers, then save', async () => {
  const p = page(true);
  try {
    p.chooseMatchup();
    p.click('[data-action="edit"]');
    p.click('#select-counter-both');
    p.click('#champ-pool-Ashe');
    assert.equal(p.document.querySelector('[data-zone="both"] [data-counter="Ashe"]'), null);
    p.click('#champ-pool-Ashe');
    assert.ok(p.document.querySelector('[data-zone="both"] [data-counter="Ashe"]'));
    p.click('#early-Ashe');
    assert.ok(p.document.querySelector('[data-zone="both"] .champ-portrait .early-warning'));
    p.click('[data-action="tier-edit"]');
    p.click('#select-tier-1');
    p.click('#champ-tier-pool-Ashe');
    assert.ok(p.document.querySelector('[data-tier-zone="1"] #champ-tier-board-Ashe'));
    p.click('#champ-tier-pool-Ashe');
    assert.equal(p.document.querySelector('#champ-tier-board-Ashe'), null);
    p.click('#champ-tier-pool-Ashe');
    p.click('[data-action="tier-close"]');
    p.click('[data-action="save-publisher"]');
    await flush();
    assert.equal(p.state.published.board.tiers.bottom['1'][0], 'Ashe');
    assert.deepEqual(p.state.published.board.earlyDisadvantage.bottom.Tristana, ['Ashe']);
    assert.match(p.document.querySelector('#toast').textContent, /배포 파일을 생성/);
    assert.deepEqual(p.state.errors, []);
  } finally { p.dom.window.close(); }
});

test('detail network failure and an uncollected matchup show clear empty/error states', async () => {
  const p = page();
  try {
    p.chooseMatchup();
    p.state.rejectDetails = true;
    p.click('[data-zone="both"] [data-id="Ashe"]');
    await flush();
    assert.match(p.document.querySelector('#stats-content').textContent, /테스트 연결 실패/);
    p.click('#stats-close');
    p.document.querySelector('#detail-champion').value = 'Garen';
    p.click('[data-action="show-matchup"]');
    await flush();
    assert.match(p.document.querySelector('#stats-content').textContent, /경기 표본이 아직 없습니다/);
    assert.equal(p.document.querySelectorAll('[data-recommend-feature]').length, 5);
    p.click('[data-recommend-feature="skills"]');
    p.click('[data-skill-stage="skills9"]');
    assert.match(p.document.querySelector('.comparison-empty').textContent, /수집 대기/);
    assert.equal(p.document.querySelector('.build-table'), null);
    assert.deepEqual(p.state.errors, []);
  } finally { p.dom.window.close(); }
});

test('runes, spells and skill orders display names, stages and corrected evidence', async () => {
  const p = page();
  try {
    p.chooseMatchup();
    p.click('[data-zone="both"] [data-id="Ashe"]');
    await flush();
    p.click('[data-recommend-feature="runes"]');
    assert.match(p.document.querySelector('.rune-build').textContent, /주 룬.*정밀.*보조 룬.*마법/);
    assert.ok(p.document.querySelector('tr.significant .fdr-badge'));
    p.click('[data-recommend-feature="spells"]');
    assert.match(p.document.querySelector('.build-table tbody tr').textContent, /점멸.*회복/);
    p.click('[data-recommend-feature="skills"]');
    assert.equal(p.document.querySelectorAll('[data-skill-stage]').length, 3);
    assert.equal(p.document.querySelectorAll('.skill-sequence')[0].children.length, 3);
    p.click('[data-skill-stage="skills9"]');
    assert.equal(p.document.querySelectorAll('.skill-sequence')[0].children.length, 9);
    assert.equal(p.document.activeElement.dataset.skillStage, 'skills9');
    assert.doesNotMatch(p.document.querySelector('#stats-content').textContent, /NaN|undefined|Infinity/);
    assert.deepEqual(p.state.errors, []);
  } finally { p.dom.window.close(); }
});

test('missing feature data does not hide other categories or fabricate evidence', async () => {
  const p = page();
  try {
    const originalFetch = p.dom.window.fetch;
    p.dom.window.fetch = async (url, options) => {
      const response = await originalFetch(url, options);
      const data = await response.json();
      if (url.endsWith('bottom-Tristana.json')) {
        data.Ashe.recommendations.features.runes = { observedGames: 0, excludedGames: 80, baselineGames: 0, candidateCount: 0, status: 'unavailable', rows: [] };
        for (const row of data.Ashe.recommendations.features.spells.rows) Object.assign(row, { status: 'insufficient_sample', p: null, q: null, ratio: null, ratioCi: null, significant: false });
      }
      return { ok: true, json: async () => data };
    };
    p.chooseMatchup();
    p.click('[data-zone="both"] [data-id="Ashe"]');
    await flush();
    p.click('[data-recommend-feature="runes"]');
    assert.match(p.document.querySelector('.comparison-empty').textContent, /확인 가능한 표본 없음/);
    p.click('[data-recommend-feature="spells"]');
    assert.match(p.document.querySelector('.comparison-status').textContent, /비교 표본 부족/);
    assert.equal(p.document.querySelector('.significant'), null);
    p.click('[data-recommend-feature="build"]');
    assert.ok(p.document.querySelector('tr.significant'));
    assert.deepEqual(p.state.errors, []);
  } finally { p.dom.window.close(); }
});
