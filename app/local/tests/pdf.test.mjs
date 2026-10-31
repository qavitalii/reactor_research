import test from 'node:test';
import assert from 'node:assert/strict';
import { parsePdfImport, eligibleSources } from '../dist/memory.js';

test('PDF sources preserve physical pages, quotes, collections and warnings', () => {
  const result = { pages: [{page: 1, text: 'First page'}, {page: 3, text: '<script>literal text</script>'}], total_pages: 3, warning: 'Page 2 needs OCR' };
  const sources = parsePdfImport(result, 'notes.pdf', 'mine', 'test');
  assert.equal(sources[1].title, 'notes.pdf · Page 3');
  assert.equal(sources[1].turns[0].content, result.pages[1].text);
  assert.equal(sources[1].extraction_warning, result.warning);
  assert.equal(eligibleSources(sources, { collectionId: 'other' }).length, 0);
  assert.equal(eligibleSources(sources, { collectionId: 'mine', selectedIds: [sources[1].source_id] }).length, 1);
  assert.equal(eligibleSources(sources, { collectionId: 'mine', asOf: '2026-10-31' }).length, 0);
});

test('invalid PDF extraction cannot partially import', () => {
  for (const pages of [[], [{page: 0, text: 'x'}], [{page: 1, text: 'a'}, {page: 1, text: 'b'}], [{page: 1, text: ''}], [{page: 1, text: 'x'.repeat(1_000_001)}]]) {
    assert.throws(() => parsePdfImport({pages, total_pages: 2}, 'x.pdf', 'mine'));
  }
});
