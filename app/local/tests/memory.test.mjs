import test from 'node:test';
import assert from 'node:assert/strict';
import { demoSources, scenarios, resolveQuery, parseImport, eligibleSources, searchSources } from '../dist/memory.js';

const options = { collectionId: 'demo-nord' };
test('every scenario citation resolves to its exact original turn and revision', () => {
  for (const scenario of scenarios) {
    const result = resolveQuery(scenario.question, demoSources, options);
    assert.equal(result.type, 'scenario');
    assert.equal(result.answer_origin, 'mock');
    for (const c of result.citations) {
      const source = demoSources.find(s => s.source_id === c.source_id);
      assert.equal(c.source_revision, source.revision);
      assert.ok(source.turns.some(t => c.locator.turn_ids.includes(t.turn_id) && t.content.includes(c.quote)));
    }
  }
});
test('historical cutoff and source selections never disclose a future answer', () => {
  assert.equal(resolveQuery(scenarios[0].question, demoSources, { ...options, asOf:'2026-10-12' }).type, 'search');
  assert.equal(resolveQuery(scenarios[0].question, demoSources, { ...options, selectedIds:['demo-s1'] }).type, 'search');
  assert.equal(eligibleSources(demoSources, { ...options, selectedIds:[] }).length, 0);
});
test('collections are isolated and a question with a negation is never loosely matched to a canned answer', () => {
  assert.equal(resolveQuery(scenarios[0].question, demoSources, { collectionId:'someone-else' }).sources.length, 0);
  assert.equal(resolveQuery('Which car did Anna NOT choose?', demoSources, options).type, 'search');
});
test('missing attribute and unimplemented arbitrary answer are separate states', () => {
  const refusal = resolveQuery(scenarios[2].question, demoSources, options);
  assert.equal(refusal.abstain, true);
  assert.equal(refusal.coverage, 'insufficient');
  const search = resolveQuery('What is the budget?', demoSources, options);
  assert.equal(search.type, 'search');
  assert.equal(search.coverage, 'unknown');
  assert.equal(search.answer_origin, 'mock');
});
test('test-drive total uses the two completed events, not the cancelled appointment or duplicate mention', () => {
  const result = resolveQuery(scenarios[1].question, demoSources, options);
  assert.deepEqual(result.computations[0].supporting_citation_ids, ['demo-c1','demo-c3']);
  assert.equal(result.computations[0].result, '2');
  assert.equal(result.citations.length, 4);
});
const fixture = () => ({ history_id:'h_example', sessions:[{ session_id:'s_example', date:'2024/02/29 (Thu) 12:30', turns:[{ turn_id:'t_1', role:'user', content:'Synthetic source: glacier meeting.' }] }] });
test('JSONL import preserves roles, dates, occurrence IDs and exact text', () => {
  const row = fixture();
  const imported = parseImport(JSON.stringify(row), 'history.jsonl', 'own', 'test');
  assert.equal(imported[0].date_raw, '2024-02-29');
  assert.equal(imported[0].original_date, row.sessions[0].date);
  assert.equal(imported[0].history_id, row.history_id);
  assert.equal(imported[0].turns[0].content, row.sessions[0].turns[0].content);
  assert.equal(searchSources(imported,'glacier')[0].source_id, 'local-test-0');
});
test('malformed imports, impossible dates, duplicate IDs and gold-shaped records fail without partial state', () => {
  assert.throws(() => parseImport('{', 'bad.jsonl','own'));
  assert.throws(() => parseImport('text', 'bad.pdf','own'));
  assert.throws(() => parseImport('  ', 'empty.txt','own'));
  assert.throws(() => parseImport(JSON.stringify({ question_id:'q', answer:'gold' }), 'gold.jsonl','own'));
  const row = fixture(); row.sessions[0].date = '2023-02-29';
  assert.throws(() => parseImport(JSON.stringify(row),'date.jsonl','own'));
  const duplicate = fixture(); duplicate.sessions.push(duplicate.sessions[0]);
  assert.throws(() => parseImport(JSON.stringify(duplicate),'duplicate.jsonl','own'));
});
test('HTML-like content remains literal data; undated notes are excluded under a historical cutoff', () => {
  const text = '<script>alert(1)</script>\nMeeting tomorrow.';
  const [note] = parseImport(text,'note.md','own','x');
  assert.equal(note.turns[0].content,text);
  assert.equal(eligibleSources([note], { collectionId:'own', asOf:'2026-10-31' }).length,0);
});

test('currency aliases and grouped amounts match sources without changing original quotes', async () => {
  const { readFile } = await import('node:fs/promises');
  const { normalizeSearch, matchesSource } = await import('../dist/memory.js');
  const cases = JSON.parse(await readFile(new URL('./fixtures/search-equivalences.json', import.meta.url), 'utf8'));
  for (const [query, canonical] of cases) {
    assert.equal(normalizeSearch(query), normalizeSearch(canonical), query);
    const original = `The approved budget is ${canonical}.`;
    const [note] = parseImport(original, 'budget.txt', 'own', 'currency');
    assert.ok(matchesSource(note, query), query);
    assert.ok(searchSources([note], query).length, query);
    assert.equal(note.turns[0].content, original);
  }
});
test('source filters distinguish amounts and currencies', async () => {
  const { matchesSource } = await import('../dist/memory.js');
  for (const text of ['17300 PLN', '7300 USD', '8300 PLN']) {
    const [note] = parseImport(text, 'other.txt', 'own', 'other');
    assert.equal(matchesSource(note, '7300 зл'), false, text);
  }
});
