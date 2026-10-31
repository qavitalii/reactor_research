import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import * as memory from '../dist/memory.js';

function setup() {
  const nodes = new Map();
  const element = () => ({ innerHTML: '', textContent: '', classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    addEventListener() {}, setAttribute() {}, contains: () => false, querySelector: () => ({ focus() {} }) });
  const requests = [];
  const saved = { collections: [{ collection_id: 'local', name: 'Notes', mode: 'documents' }],
    sources: [{ source_id: 'one', collection_id: 'local', title: 'First note', kind: 'text', turns: [{ content: 'First text' }] },
      { source_id: 'two', collection_id: 'local', title: 'Second note', kind: 'text', turns: [{ content: 'Second text' }] }] };
  const context = vm.createContext({ ...memory, AbortController, Intl,
    localStorage: { getItem: () => JSON.stringify(saved), setItem() {} },
    location: { hash: '#sources' }, history: { replaceState() {} },
    document: { addEventListener() {}, querySelector(selector) {
      if (!nodes.has(selector)) nodes.set(selector, element());
      return nodes.get(selector);
    } },
    window: { scrollTo() {}, addEventListener() {}, matchMedia: () => ({ addEventListener() {} }) },
    setTimeout: () => 1, clearTimeout() {},
    fetch: (_, options) => new Promise(resolve => requests.push({ body: JSON.parse(options.body), resolve })),
  });
  const code = readFileSync(new URL('../dist/app.js', import.meta.url), 'utf8').replace(/^import .*\n/, '');
  vm.runInContext(code, context);
  return { ...vm.runInContext('({state, searchSources, scheduleSourceSearch, navigate, askLocal})', context), nodes, requests };
}

const reply = id => ({ ok: true, json: async () => ({ results: [{ source_id: id, quote: 'An original passage.' }] }) });

test('rapidly changed searches run serially and stale results never replace the latest query', async () => {
  const ui = setup();
  ui.state.sourceFilter = 'first meaning'; ui.scheduleSourceSearch();
  const first = ui.searchSources();
  ui.state.sourceFilter = 'second meaning'; ui.scheduleSourceSearch();
  await ui.searchSources();
  assert.equal(ui.requests.length, 1);
  ui.requests[0].resolve(reply('one')); await first;
  assert.equal(ui.state.sourceMatches, null);
  const second = ui.searchSources();
  assert.equal(ui.requests[1].body.question, 'second meaning');
  ui.requests[1].resolve(reply('two')); await second;
  assert.equal(ui.state.sourceMatches[0].source_id, 'two');
  assert.match(ui.nodes.get('#source-results').innerHTML, /Second note/);
  assert.doesNotMatch(ui.nodes.get('#source-results').innerHTML, /First note/);
});

test('clearing a query restores all sources and an old response cannot overwrite them', async () => {
  const ui = setup();
  ui.state.sourceFilter = 'first meaning'; ui.scheduleSourceSearch();
  const first = ui.searchSources();
  ui.state.sourceFilter = ''; ui.scheduleSourceSearch();
  ui.requests[0].resolve(reply('one')); await first;
  assert.equal(ui.state.sourceSearching, false);
  assert.match(ui.nodes.get('#source-results').innerHTML, /First note/);
  assert.match(ui.nodes.get('#source-results').innerHTML, /Second note/);
});

test('search errors provide a retry and do not display unrelated old results', async () => {
  const ui = setup();
  ui.state.sourceFilter = 'meaning'; ui.scheduleSourceSearch();
  const search = ui.searchSources();
  ui.requests[0].resolve({ ok: false, json: async () => ({ error: 'Search unavailable' }) }); await search;
  assert.equal(ui.state.sourceSearching, false);
  assert.match(ui.nodes.get('#source-results').innerHTML, /Search unavailable/);
  assert.match(ui.nodes.get('#source-results').innerHTML, /Try again/);
});


test('unverified generations show original passages without entering answer context', async () => {
  const ui = setup();
  ui.state.page = 'ask'; ui.state.question = 'What is this about?';
  const request = ui.askLocal(0);
  ui.requests[0].resolve({ ok: true, json: async () => ({ type: 'search', answer_status: 'unverified',
    answer: 'Review the original passages', detail: 'A complete answer could not be verified.',
    abstain: false, sources: [], citations: [{source_id:'one', quote:'First text'}] }) });
  await request;
  const html = ui.nodes.get('#main').innerHTML;
  assert.match(html, /Related source passages/);
  assert.match(html, /First text/);
  assert.doesNotMatch(html, /Sources for this answer|Local AI answer/);
  assert.equal(ui.state.conversation.length, 0);
});
