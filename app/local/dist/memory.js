// Synthetic demonstration data. No challenge questions, gold or Reactor results.
export const demoCollection = { collection_id: 'demo-nord', name: 'Nord Motors', mode: 'demo', history_id: 'demo-anna', description: 'Customer commitments', active_index_generation: 'demo-v1' };

const source = (id, date, title, topic, turns) => ({
  source_id: id, collection_id: 'demo-nord', history_id: 'demo-anna', session_id: id,
  revision: 'demo-rev-1', kind: 'conversation', status: 'ready', date_raw: date,
  title, topic, synthetic: true,
  turns: turns.map(([speaker, content], i) => ({ turn_id: `${id}-t${i + 1}`, role: speaker === 'Anna' ? 'user' : 'assistant', speaker, content })),
});

export const demoSources = [
  source('demo-s1', '2026-10-08', 'The first shortlist', 'Choosing a car', [
    ['Anna', 'I need a car for the city and family trips. For now, I prefer the Volvo XC60 with a light interior. My budget is up to €55,000.'],
    ['Mark · sales advisor', 'I have noted your preferences. I will prepare XC60 options and an alternative to compare.'],
  ]),
  source('demo-s2', '2026-10-12', 'The first test drive', 'Visits and test drives', [
    ['Mark · sales advisor', 'What did you think of the XC60 test drive today?'],
    ['Anna', 'Today, 12 October, I test-drove the XC60. It was comfortable, but I would like to compare it with the electric EX40.'],
  ]),
  source('demo-s3', '2026-10-16', 'A change of plans', 'Visits and test drives', [
    ['Anna', 'Please cancel the test drive on 17 October. I cannot make it. Let us arrange a time next week.'],
    ['Mark · sales advisor', 'The appointment on 17 October is cancelled. We will arrange a new time separately.'],
  ]),
  source('demo-s4', '2026-10-21', 'Meeting the EX40', 'Visits and test drives', [
    ['Anna', 'Today, 21 October, I drove the EX40. This was my second test drive with you. I liked how quiet the cabin was.'],
    ['Mark · sales advisor', 'Great. We can discuss the trim when you have made your choice.'],
  ]),
  source('demo-s5', '2026-10-24', 'A new direction', 'Choosing a car', [
    ['Anna', 'I have changed my mind about the XC60. I am choosing the Volvo EX40 Ultra in Sage Green with a light interior. My budget is still up to €55,000.'],
    ['Mark · sales advisor', 'Updating your choice to the EX40 Ultra in Sage Green with a light interior. I will check availability.'],
  ]),
  source('demo-s6', '2026-10-27', 'The next step', 'Purchase and paperwork', [
    ['Mark · sales advisor', 'I can prepare an offer for the EX40 Ultra you selected.'],
    ['Anna', 'Yes, please send the offer. Both test drives were helpful. I have not decided on a payment method yet. We can discuss it later.'],
  ]),
];

export const scenarios = [
  { id: 'choice', icon: 'refresh', label: 'Follow the changes', question: 'Which car did Anna finally choose?', hint: 'The latest choice, with its history', sourceIds: ['demo-s1', 'demo-s5'],
    answer: 'Volvo EX40 Ultra', detail: 'Sage Green, light interior. On 24 October, Anna changed her original choice from the Volvo XC60.',
    quotes: ['I need a car for the city and family trips. For now, I prefer the Volvo XC60 with a light interior. My budget is up to €55,000.', 'I have changed my mind about the XC60. I am choosing the Volvo EX40 Ultra in Sage Green with a light interior. My budget is still up to €55,000.'],
    aliases: ['What car did Anna choose?', 'Which car did Anna choose?'] },
  { id: 'visits', icon: 'calendar', label: 'Connect the dots', question: 'How many test drives did Anna take?', hint: 'Count events, not repeated mentions', sourceIds: ['demo-s2', 'demo-s3', 'demo-s4', 'demo-s6'],
    answer: '2 test drives', detail: 'XC60 on 12 October, EX40 on 21 October. The cancelled appointment and a repeated mention are excluded from the total.',
    quotes: ['Today, 12 October, I test-drove the XC60. It was comfortable, but I would like to compare it with the electric EX40.', 'Please cancel the test drive on 17 October. I cannot make it. Let us arrange a time next week.', 'Today, 21 October, I drove the EX40. This was my second test drive with you. I liked how quiet the cabin was.', 'Yes, please send the offer. Both test drives were helpful. I have not decided on a payment method yet. We can discuss it later.'],
    aliases: ['How many test drives were there?', 'How many test drives has Anna taken?'] },
  { id: 'unknown', icon: 'shield', label: 'Know the limits', question: 'How did Anna decide to pay?', hint: 'A clear answer when evidence is missing', sourceIds: ['demo-s6'],
    answer: 'Not decided yet', detail: 'In the latest conversation, Anna explicitly said she had not decided how to pay. There is no evidence to choose between financing, leasing or paying in full.',
    quotes: ['Yes, please send the offer. Both test drives were helpful. I have not decided on a payment method yet. We can discuss it later.'], abstain: true,
    aliases: ['How will Anna pay?', 'What payment method did Anna choose?'] },
];

export const demoFacts = [
  { id: 'fact-car', label: 'Car', value: 'Volvo EX40 Ultra', topic: 'Choosing a car', sourceId: 'demo-s5', status: 'Current choice', old: 'Volvo XC60', quote: scenarios[0].quotes[1] },
  { id: 'fact-color', label: 'Colour & interior', value: 'Sage Green · light interior', topic: 'Choosing a car', sourceId: 'demo-s5', status: 'Customer preference', quote: scenarios[0].quotes[1] },
  { id: 'fact-budget', label: 'Budget', value: 'Up to €55,000', topic: 'Purchase and paperwork', sourceId: 'demo-s5', status: 'Unchanged', quote: scenarios[0].quotes[1] },
  { id: 'fact-payment', label: 'Payment method', value: 'Not specified', topic: 'Purchase and paperwork', sourceId: 'demo-s6', status: 'Needs a follow-up', quote: scenarios[2].quotes[0] },
];

export function normalize(text) { return text.toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]+/gu, ' ').trim(); }
// Normalize the search index, never the original text used for citations.
const currencyGroups = {
  pln: ['pln', 'zł', 'zl', 'зл', 'злотий', 'злоті', 'злотих', 'злотого', 'злотими', 'zloty', 'zlotych', 'zlotego', 'złoty', 'złote', 'złotych', 'złotego'],
  uah: ['uah', '₴', 'грн', 'гривня', 'гривні', 'гривень', 'гривнях', 'гривнями'],
  eur: ['eur', '€', 'євро', 'евро', 'euro', 'euros'],
  usd: ['usd', 'us$'],
  gbp: ['gbp', '£'],
};
const currencyAliases = new Map(Object.entries(currencyGroups).flatMap(([code, aliases]) => aliases.map(alias => [alias, code])));
export function normalizeSearch(text) {
  text = text.normalize('NFKC').toLocaleLowerCase('en')
    .replace(/(?<=\d)[ \t](?=\d{3}(?:\D|$))/g, '')
    .replace(/us\$/g, ' usd ')
    .replace(/[€₴£]/g, symbol => ` ${currencyAliases.get(symbol)} `)
    .replace(/(\d)(\p{L})/gu, '$1 $2');
  return normalize(text).split(' ').map(word => currencyAliases.get(word) || word).join(' ');
}
// Phrase matching is shared by the source list; token boundaries keep 7300 distinct from 17300.
export function matchesSource(source, query) {
  const phrase = normalizeSearch(query);
  return !phrase || ` ${normalizeSearch(`${source.title} ${sourceText(source)}`)} `.includes(` ${phrase} `);
}
export function sourceText(s) { return s.turns.map(t => t.content).join('\n'); }
export function eligibleSources(sources, { collectionId, selectedIds = null, asOf = '' }) {
  return sources.filter(s => s.collection_id === collectionId && (!selectedIds || selectedIds.includes(s.source_id)) && (!asOf || (s.date_raw && s.date_raw.slice(0, 10) <= asOf)));
}
export function searchSources(sources, query) {
  const words = [...new Set(normalizeSearch(query).split(' ').filter(w => w.length > 2 || /^\d+$/.test(w)))];
  return sources.map(s => ({ source: s, score: words.reduce((n, word) => n + (( /^\d+$/.test(word) ? normalizeSearch(`${s.title} ${sourceText(s)}`).split(' ').includes(word) : normalizeSearch(`${s.title} ${sourceText(s)}`).includes(word)) ? 1 : 0), 0) }))
    .filter(x => x.score > 0).sort((a,b) => b.score-a.score).slice(0, 5).map(x => x.source);
}
export function resolveQuery(question, sources, options) {
  const eligible = eligibleSources(sources, options);
  const scenario = options.collectionId === 'demo-nord' ? scenarios.find(s => [s.question, ...s.aliases].some(q => normalize(q) === normalize(question))) : null;
  const base = { answer_origin: 'mock', pipeline_version: 'demo-v1', index_generation: 'demo-v1', limitations: ['Fictional data. Reactor is not connected.'], question };
  if (scenario && scenario.sourceIds.every(id => eligible.some(s => s.source_id === id))) {
    const citations = scenario.sourceIds.map((id, i) => {
      const s = eligible.find(x => x.source_id === id);
      const turn = s.turns.find(t => t.content.includes(scenario.quotes[i]));
      if (!turn) throw new Error('The demo quote could not be found in its source.');
      return { citation_id: `demo-c${i+1}`, source_id: id, source_revision: s.revision, label: String(i+1), quote: scenario.quotes[i], locator: { kind: 'conversation', history_id: s.history_id, session_id: s.session_id, turn_ids: [turn.turn_id], date_raw: s.date_raw } };
    });
    return { ...base, type: 'scenario', scenarioId: scenario.id, answer: scenario.answer, detail: scenario.detail, abstain: Boolean(scenario.abstain), coverage: scenario.abstain ? 'insufficient' : 'sufficient', citations,
      computations: scenario.id === 'visits' ? [{ name: 'Completed test drives', formula: '1 + 1 = 2', result: '2', unit: 'test drives', supporting_citation_ids: ['demo-c1', 'demo-c3'] }] : [] };
  }
  const found = searchSources(eligible, question);
  return { ...base, type: 'search', answer: found.length ? 'Here is what the sources say' : 'No matches found', abstain: false, coverage: 'unknown', citations: [], computations: [], sources: found,
    detail: scenario ? 'This demo answer needs all related conversations. Adjust the sources or date to see the complete example.' : 'These are keyword matches in your sources. The three example questions have prepared demo answers. Other questions need a connected answer service.' };
}

// Text imports are parsed in the browser; selected sources can be sent to the local model.
export function parseImport(text, filename, collectionId, stamp = String(Date.now())) {
  if (!text.trim()) throw new Error('This file is empty. Choose a file containing text.');
  if (text.length > 1_000_000) throw new Error('Please choose a file under 1 MB for this demo.');
  const extension = filename.split('.').pop().toLowerCase();
  if (!['txt', 'md', 'jsonl'].includes(extension)) throw new Error('Supported formats: TXT, Markdown and JSONL.');
  if (extension !== 'jsonl') return [{ source_id: `local-${stamp}-0`, collection_id: collectionId, revision: `local-${stamp}`, title: filename, kind: 'text', status: 'ready', date_raw: '', topic: 'Imported files', synthetic: false, turns: [{ turn_id: `local-${stamp}-t0`, role: 'user', speaker: 'Document', content: text }] }];
  const rows = text.replace(/^\uFEFF/, '').split(/\r?\n/).filter(l => l.trim());
  const sources = [], histories = new Set();
  for (const [rowIndex, line] of rows.entries()) {
    let row;
    try { row = JSON.parse(line); } catch { throw new Error(`Line ${rowIndex+1}: invalid JSON.`); }
    if (!row || typeof row.history_id !== 'string' || !Array.isArray(row.sessions) || !row.sessions.length || 'answer' in row || 'evidence' in row) throw new Error(`Line ${rowIndex+1}: a history_id and a non-empty sessions array are required.`);
    if (histories.has(row.history_id)) throw new Error('The file contains a duplicate history_id.');
    histories.add(row.history_id);
    const sessionIds = new Set();
    for (const s of row.sessions) {
      if (!s || typeof s.session_id !== 'string' || sessionIds.has(s.session_id) || typeof s.date !== 'string' || !Array.isArray(s.turns) || !s.turns.length) throw new Error('Each conversation needs a unique session_id, a date and a non-empty turns array.');
      sessionIds.add(s.session_id);
      const date = s.date.slice(0,10).replaceAll('/', '-');
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date)) || new Date(date).toISOString().slice(0,10) !== date) throw new Error('Conversation dates must start with a valid YYYY-MM-DD or YYYY/MM/DD date.');
      const turnIds = new Set();
      for (const t of s.turns) {
        if (!t || typeof t.turn_id !== 'string' || turnIds.has(t.turn_id) || !['user','assistant'].includes(t.role) || typeof t.content !== 'string') throw new Error('Each message needs a unique turn_id, a role (user/assistant) and text content.');
        turnIds.add(t.turn_id);
      }
      sources.push({ source_id: `local-${stamp}-${sources.length}`, collection_id: collectionId, history_id: row.history_id, session_id: s.session_id, revision: `local-${stamp}`, title: `${filename} · ${s.session_id}`, kind: 'conversation', status: 'ready', date_raw: date, original_date: s.date, topic: 'Imported conversations', synthetic: false, turns: s.turns.map(t => ({ ...t, speaker: t.role === 'user' ? 'User' : 'Assistant' })) });
      if (sources.length > 100) throw new Error('The demo supports up to 100 conversations per import.');
    }
  }
  return sources;
}

// One source per readable page preserves page numbers in filtering and citations.
export function parsePdfImport(result, filename, collectionId, stamp = String(Date.now())) {
  if (!result || !Array.isArray(result.pages) || !result.pages.length || result.pages.length > 200 ||
      !Number.isInteger(result.total_pages) || result.total_pages < 1 || result.total_pages > 200 ||
      (result.warning != null && typeof result.warning !== 'string')) throw new Error('Invalid PDF extraction response.');
  const seen = new Set();
  let total = 0;
  return result.pages.map(p => {
    if (!p || !Number.isInteger(p.page) || p.page < 1 || p.page > result.total_pages || seen.has(p.page) ||
        typeof p.text !== 'string' || !p.text.trim()) throw new Error('Invalid PDF page.');
    seen.add(p.page); total += p.text.length;
    if (total > 1_000_000) throw new Error('This PDF contains too much text. Split it into smaller files.');
    return { source_id: `local-${stamp}-p${p.page}`, collection_id: collectionId, revision: `local-${stamp}`,
      title: `${filename} · Page ${p.page}`, filename, page_number: p.page, total_pages: result.total_pages,
      extraction_warning: result.warning || '', format: 'pdf', kind: 'text', status: 'ready', date_raw: '',
      topic: 'Imported PDFs', synthetic: false,
      turns: [{ turn_id: `local-${stamp}-p${p.page}-t0`, role: 'user', speaker: `Page ${p.page}`, content: p.text }] };
  });
}
