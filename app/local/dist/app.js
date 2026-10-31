import { sourceText, parseImport, parsePdfImport, eligibleSources } from './memory.js?v=search-2';

const paths = {
  spark: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
  chat: '<path d="M20 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2v-10A8.5 8.5 0 1 1 20 11.5Z"/><path d="M7 9h8M7 13h5"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>', down: '<path d="m7 10 5 5 5-5"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>', up: '<path d="M12 19V5m-6 6 6-6 6 6"/>',
  arrowUp: '<path d="M6 18 18 6M7 6h11v11"/>', back: '<path d="M19 12H5m6-6-6 6 6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>',
  shield: '<path d="m12 3 8 3v5c0 5-4 8-8 10-4-2-8-5-8-10V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.7 9a2.3 2.3 0 0 1 4.6 0c0 1.7-2.3 1.9-2.3 3.5M12 16h.01"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 7a7.5 7.5 0 0 1 12-2L20 8M4 16l2.5 3a7.5 7.5 0 0 0 12-2"/>',
  calendar: '<rect x="4" y="5" width="16" height="16" rx="3"/><path d="M8 3v4M16 3v4M4 10h16m-11 5h2m3 0h2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  upload: '<path d="M12 15V3m-4 4 4-4 4 4M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  check: '<path d="m5 12 4 4L19 6"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>', sliders: '<path d="M4 7h4m4 0h8M4 17h9m4 0h3"/><circle cx="10" cy="7" r="2"/><circle cx="15" cy="17" r="2"/>',
};
const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.spark}</svg>`;
const mark = () => '<span class="brand-mark"><svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><rect x="9" y="5" width="18" height="29" rx="9" transform="rotate(-25 18 19.5)" stroke="currentColor" stroke-width="2.6"/><rect x="21" y="14" width="18" height="29" rx="9" transform="rotate(25 30 28.5)" stroke="currentColor" stroke-width="2.6"/></svg></span>';
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const $ = selector => document.querySelector(selector);
const day = value => value ? new Intl.DateTimeFormat('en-GB', { day:'numeric', month:'short', timeZone:'UTC' }).format(new Date(`${value.slice(0,10)}T12:00:00Z`)).replace('.', '') : 'Undated';
const STORAGE = 'recall-demo-v1';
let saved = {};
try { saved = JSON.parse(localStorage.getItem(STORAGE) || '{}'); } catch { /* A clean session is always usable. */ }
const localCollections = (Array.isArray(saved.collections) ? saved.collections : []).filter(c => c.mode !== 'demo');
if (!localCollections.length) localCollections.push({ collection_id: 'local-default', name: 'My notes', mode: 'documents' });
const initialCollection = localCollections.find(c => c.collection_id === saved.collectionId) || localCollections[0];
const state = {
  collections: localCollections,
  sources: (Array.isArray(saved.sources) ? saved.sources : []).filter(s => !s.synthetic),
  collectionId: initialCollection.collection_id, page: ['sources', 'memory'].includes(location.hash.slice(1)) ? 'sources' : 'ask',
  history: Array.isArray(saved.history) ? saved.history.slice(0, 8) : [],
  selectedIds: null, asOf: '', draft: '', result: null, question: '', running: false,
  sourceFilter: '', sourceKind: 'all', pendingFile: null,
  sourceMatches: null, sourceSearching: false, sourceError: '',
  conversation: [],
};
let runId = 0, toastTimer, requestController;
let sourceSearchId = 0, sourceSearchTimer, sourceSearchInFlight = false;
const currentCollection = () => state.collections.find(c => c.collection_id === state.collectionId) || state.collections[0];
const currentSources = () => state.sources.filter(s => s.collection_id === state.collectionId);
const getSource = id => state.sources.find(s => s.source_id === id);
const persist = () => {
  try {
    localStorage.setItem(STORAGE, JSON.stringify({ collections: state.collections, collectionId: state.collectionId, sources: state.sources, history: state.history, feedback: saved.feedback || {} }));
    return true;
  } catch { return false; }
};
function toast(text) { clearTimeout(toastTimer); $('#toast').textContent = text; $('#toast').classList.add('visible'); toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3700); }
function announce(text) { $('#announcer').textContent = text; }
function clearRun() { requestController?.abort(); runId++; state.running = false; }
function setMenu(open) {
  const sidebar = $('#sidebar'), toggle = $('.mobile-menu');
  const restoreFocus = !open && sidebar.contains(document.activeElement);
  sidebar.classList.toggle('open', open);
  $('.app-shell').classList.toggle('menu-open', open);
  toggle?.setAttribute('aria-expanded', String(open));
  toggle?.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  if (toggle) toggle.innerHTML = icon(open ? 'close' : 'menu');
  for (const selector of ['#main', '.app-footer', '.breadcrumbs', '.topbar-actions']) $(selector).inert = open;
  if (open) sidebar.querySelector('.nav-btn.active')?.focus();
  else if (restoreFocus) toggle?.focus();
}
function navigate(page, reset = false) {
  page = page === 'memory' ? 'sources' : page;
  clearSourceSearch();
  clearRun(); state.page = page; if (reset) { state.conversation = []; state.result = null; state.question = ''; state.draft = ''; }
  history.replaceState(null, '', `#${page}`); setMenu(false); render(); window.scrollTo({ top:0, behavior:'instant' });
}
function sidebar() {
  const collection = currentCollection();
  const historyRows = state.history.filter(h => h.collectionId === state.collectionId).slice(0, 4);
  $('#sidebar').innerHTML = `<button class="brand" data-action="home" aria-label="Recall — home">${mark()}<span>recall<span class="brand-period" aria-hidden="true">.</span></span></button>
    <button class="workspace-button" data-action="collections" aria-label="Choose a collection"><span class="workspace-icon">${esc(collection.name.slice(0,2).toUpperCase())}</span><span class="workspace-name">${esc(collection.name)}<small>Local collection</small></span>${icon('down','icon-sm')}</button>
    <div class="sidebar-label">Workspace</div><nav class="nav" aria-label="Sections"><button class="nav-btn ${state.page === 'ask' ? 'active' : ''}" data-action="home" ${state.page === 'ask' ? 'aria-current="page"' : ''}>${icon('chat')}<span>Ask Recall</span><kbd>⌘ K</kbd></button>
    <button class="nav-btn ${state.page === 'sources' ? 'active' : ''}" data-page="sources" ${state.page === 'sources' ? 'aria-current="page"' : ''}>${icon('layers')}<span>Sources</span><span class="count">${currentSources().length}</span></button>
    </nav>
    <div class="history-section"><div class="sidebar-label">Recent questions</div>${historyRows.length ? historyRows.map(h => `<button class="history-item" data-history="${esc(h.id)}" title="${esc(h.question)}">${icon('clock','icon-sm')}<span>${esc(h.question)}</span></button>`).join('') : '<p class="history-empty">Your questions will appear here.</p>'}</div>
    <div class="sidebar-bottom"><button class="sidebar-add" data-action="import">${icon('plus','icon-sm')} Add a source</button><div class="sidebar-note">${icon('lock','icon-sm')}<span>Your files stay on this Mac.</span></div></div>`;
}
function topbar() {
  $('#topbar').innerHTML = `<button class="icon-button mobile-menu" data-action="menu" aria-label="Open navigation" aria-expanded="false" aria-controls="sidebar">${icon('menu')}</button><span class="mobile-wordmark" aria-hidden="true">recall<span>.</span></span><div class="breadcrumbs"><span>Collection</span><strong>${esc(currentCollection().name)}</strong></div><div class="topbar-actions">${state.page !== 'sources' ? `<button class="text-button topbar-add" data-action="import">${icon('plus','icon-sm')} Add source</button>` : ''}<button class="icon-button" data-action="help" aria-label="How it works">${icon('help','icon-sm')}</button></div>`;
}
function composer(followup = false) {
  const count = eligibleSources(state.sources, { collectionId: state.collectionId, selectedIds: state.selectedIds, asOf: state.asOf }).length;
  if (!count) return `<div class="notice">${icon('info','icon-sm')}<span>No sources selected. Choose at least one to ask a question.</span><button class="text-button" data-action="context">Choose sources</button></div>`;
  return `<form id="question-form" class="composer glass ${followup ? 'followup' : ''}"><label for="question" class="sr-only">Your question</label><textarea id="question" name="question" maxlength="1000" rows="${followup ? 1 : 2}" placeholder="${followup ? 'Ask a follow-up question…' : 'Ask about a decision, a detail, or an event…'}" required>${esc(state.draft)}</textarea><div class="composer-bottom"><button class="context-chip" type="button" data-action="context">${icon('layers','icon-sm')}<span>${state.selectedIds || state.asOf ? 'Selected' : 'All sources'} · ${count}${state.asOf ? ` · through ${day(state.asOf)}` : ''}</span>${icon('down','icon-sm')}</button><div class="send-wrap"><span class="keyboard-hint">Enter ↵</span><button class="send-button" type="submit" aria-label="Ask a question"><span>Ask</span>${icon('up')}</button></div></div></form>`;
}
function recentItem(s) { return `<button class="recent-item" data-source="${esc(s.source_id)}" aria-label="Open source: ${esc(s.title)}"><span class="source-icon">${icon(s.kind === 'conversation' ? 'chat' : 'file','icon-sm')}</span><span><strong>${esc(s.title)}</strong><small>${day(s.date_raw)} · Local file</small></span>${icon('arrowUp')}</button>`; }
function askHome() {
  const sources = currentSources();
  if (!sources.length) return `<div class="welcome"><div class="eyebrow">${icon('spark','icon-sm')} Your conversation workspace</div><h1>Start with a source.</h1><p>Add a document to ${esc(currentCollection().name)}, then ask questions and check the original quotes.</p></div><div class="empty-state"><span class="source-icon">${icon('file')}</span><h2>Add your first file</h2><p>PDF, TXT, Markdown or a conversation export.</p><button class="primary-button" data-action="import">${icon('plus','icon-sm')} Add a source</button></div>`;
  return `<div class="welcome"><div class="eyebrow">${icon('spark','icon-sm')} Your conversation workspace</div><h1>A little clarity.<br>From every conversation.</h1><p>Search ${esc(currentCollection().name)}. Get clear answers, with the original words to back them up.</p></div>${composer()}<div class="composer-note">${icon('shield','icon-sm')}Search by meaning, in your language. Answers include source quotes.</div>
  <section class="recent-section"><div class="section-heading"><h2>Latest sources</h2><button class="text-button" data-page="sources">View all ${icon('arrow','icon-sm')}</button></div><div class="recent-list">${sources.slice(-2).reverse().map(recentItem).join('')}</div></section>`;
}
function sourcesPage() {
  const kinds = new Set(currentSources().map(s => s.kind));
  if (kinds.size < 2) state.sourceKind = 'all';
  return `<div class="page-heading"><div><h1>Sources</h1><p>Browse your conversations and notes, or add a file.</p></div><button class="primary-button" data-action="import">${icon('plus','icon-sm')} Add a source</button></div>${kinds.size ? `<div class="toolbar"><label class="search-field">${icon('search','icon-sm')}<input id="source-search" type="search" maxlength="1000" placeholder="Describe what you’re looking for…" aria-label="Search sources" value="${esc(state.sourceFilter)}"></label>${kinds.size > 1 ? `<div class="segmented" aria-label="Source type">${[['all','All'],['conversation','Conversations'],['text','Files']].map(([v,l]) => `<button data-kind="${v}" class="${state.sourceKind === v ? 'active' : ''}" aria-pressed="${state.sourceKind === v}">${l}</button>`).join('')}</div>` : ''}</div>` : ''}${kinds.size ? '<p class="search-hint">Search by meaning or exact words. Results stay within this collection.</p>' : ''}<div id="source-results"></div><div class="notice">${icon('lock','icon-sm')}Files are stored in this browser and processed on this Mac. Supports PDF, TXT, Markdown and conversation JSONL.</div>`;
}
function renderSourceRows() {
  const results = $('#source-results');
  if (!results) return;
  if (state.sourceSearching) { results.innerHTML = '<p class="search-status" role="status"><span class="spinner"></span> Searching your sources…</p>'; return; }
  if (state.sourceError) { results.innerHTML = `<div class="notice" role="alert"><span>${esc(state.sourceError)}</span><button class="text-button" data-action="retry-search">Try again</button></div>`; return; }
  const query = state.sourceFilter.trim();
  const pool = currentSources().filter(s => state.sourceKind === 'all' || s.kind === state.sourceKind);
  const sources = query ? (state.sourceMatches || []).map(match => pool.find(s => s.source_id === match.source_id)).filter(Boolean) : pool;
  $('#source-results').innerHTML = sources.length ? `<div class="source-list glass">${sources.map(s => `<button class="source-row" data-source="${esc(s.source_id)}"><span class="source-icon">${icon(s.kind === 'conversation' ? 'chat' : 'file','icon-sm')}</span><span class="source-row-text"><strong>${esc(s.title)}</strong><small>${s.history_id ? esc(s.history_id) : 'Your file'} · ${s.kind === 'conversation' ? `${s.turns.length} messages` : s.format === 'pdf' ? `PDF · page ${s.page_number} of ${s.total_pages}${s.extraction_warning ? ' · Some pages need OCR' : ''}` : 'Text document'}</small>${query ? `<span class="source-match">${esc((state.sourceMatches.find(m => m.source_id === s.source_id)?.quote || "").slice(0, 240))}</span>` : ""}</span><time class="date">${day(s.date_raw)}</time>${query ? "" : `<span class="pill">${icon('check','icon-sm')} Added</span>`}${icon('chevron','icon-sm')}</button>`).join('')}</div><p class="source-count">${query ? "Closest sources" : "Showing"}: ${sources.length} of ${currentSources().length}</p>` : `<div class="empty-state glass">${icon('search')}<h3>${currentSources().length ? 'Nothing found' : 'No sources yet'}</h3><p>${currentSources().length ? 'Try describing the topic in a different way, or check your source filters.' : 'Add a PDF, a text file or a conversation export to begin.'}</p>${!currentSources().length ? '<button class="primary-button" data-action="import">Add a source</button>' : ''}</div>`;
}
function progressView() {
  return `<button class="back-button" data-action="home">${icon('back','icon-sm')} Back to questions</button><h1 class="question-title">${esc(state.question)}</h1><section class="progress-card" aria-label="Answer progress"><div class="progress-title"><span class="spinner"></span>Finding the answer</div><div class="progress-footer"><p class="progress-note">Looking through your selected sources. This may take a moment.</p><button class="text-button" data-action="cancel">Cancel</button></div></section>`;
}
function clearSourceSearch() {
  clearTimeout(sourceSearchTimer); sourceSearchId++;
  state.sourceMatches = null; state.sourceSearching = false; state.sourceError = '';
}
function scheduleSourceSearch() {
  clearSourceSearch();
  state.sourceSearching = Boolean(state.sourceFilter.trim());
  renderSourceRows();
  if (state.sourceSearching) sourceSearchTimer = setTimeout(searchSources, 450);
}
async function searchSources() {
  // Serialize requests while typing: cancellation in the browser cannot stop local inference.
  if (sourceSearchInFlight || state.page !== 'sources' || !state.sourceFilter.trim()) return;
  const id = sourceSearchId;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 300000);
  sourceSearchInFlight = true;
  try {
    const sources = currentSources().filter(s => state.sourceKind === 'all' || s.kind === state.sourceKind);
    let matches = [];
    if (sources.length) {
      const response = await fetch('/api/search', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: state.sourceFilter.trim().slice(0, 1000), sources }), signal: controller.signal });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not search your sources.');
      matches = result.results;
    }
    if (id !== sourceSearchId) return;
    state.sourceMatches = matches;
    announce(`Found ${matches.length} related ${matches.length === 1 ? 'source' : 'sources'}.`);
  } catch (error) {
    if (id === sourceSearchId) state.sourceError = error.name === 'AbortError' ? 'Search took too long. Try again to continue indexing.' : error.message;
  } finally {
    clearTimeout(timeout); sourceSearchInFlight = false;
    if (id === sourceSearchId) { state.sourceSearching = false; renderSourceRows(); }
    else if (state.page === 'sources' && state.sourceFilter.trim()) {
      clearTimeout(sourceSearchTimer); sourceSearchTimer = setTimeout(searchSources, 450);
    }
  }
}
function answerView() {
  const r = state.result;
  return `<button class="back-button" data-action="home">${icon('back','icon-sm')} New question</button><h1 class="question-title">${esc(state.question)}</h1><section class="result-card glass"><div class="answer-meta"><span class="answer-brand">${mark()} Recall</span><span class="answer-origin">${icon('info','icon-sm')} ${r.answer_status === 'unverified' ? 'Original passages' : r.type === 'model' ? 'Local AI answer' : 'Source search'}</span></div><h2 class="answer-headline">${esc(r.answer)}</h2><p class="answer-detail">${esc(r.detail)}${r.type !== 'search' ? `<span class="citation-numbers">${r.citations.map((c,i) => `<button class="citation-number" data-citation="${i}" aria-label="Open source ${i+1}">${i+1}</button>`).join('')}</span>` : ''}</p>${r.abstain ? `<div class="notice">${icon('shield','icon-sm')}The selected sources do not provide enough information.</div>` : ''}${r.type === 'search' && r.sources.length && !r.citations.length ? `<div class="search-results">${r.sources.map(s => `<div><button class="source-row" data-source="${esc(s.source_id)}"><span class="source-icon">${icon('file','icon-sm')}</span><span class="source-row-text"><strong>${esc(s.title)}</strong><small>${day(s.date_raw)} · open original text</small></span>${icon('chevron','icon-sm')}</button><p class="search-excerpt">${esc(sourceText(s).slice(0,240))}${sourceText(s).length > 240 ? '…' : ''}</p></div>`).join('')}</div>` : ''}<div class="result-actions"><button class="text-button" data-action="copy">${icon('copy','icon-sm')} Copy</button></div></section>
  ${r.citations.length ? `<section class="evidence-section"><div class="section-heading"><h2>${r.answer_status === 'unverified' ? 'Related source passages' : 'Sources for this answer'}</h2><span class="muted" style="font-size:12px">${r.citations.length} ${r.answer_status === 'unverified' ? (r.citations.length === 1 ? 'passage' : 'passages') : (r.citations.length === 1 ? 'source' : 'sources')}</span></div><div class="evidence-grid">${r.citations.map((c,i) => { const s = getSource(c.source_id); return `<button class="evidence-card" data-citation="${i}"><span class="evidence-top"><span class="source-label">${i+1}</span>Your file<time>${day(s.date_raw)}</time></span><blockquote>«${esc(c.quote)}»</blockquote><strong>${esc(s.title)} ${icon('arrowUp','icon-sm')}</strong></button>`; }).join('')}</div></section>` : ''}${composer(true)}`;
}
function renderMain() {
  $('#main').innerHTML = `<div class="main-inner">${state.page === 'sources' ? sourcesPage() : state.running ? progressView() : state.result ? answerView() : askHome()}</div>`;
  if (state.page === 'sources') scheduleSourceSearch();
}
function render() { sidebar(); topbar(); renderMain(); $('.app-footer').innerHTML = `<span><i class="status-dot"></i> Local files · local AI</span><span>Recall · Dealer Handshake</span>`; }

function ask(question) {
  if (!question.trim()) return;
  clearSourceSearch();
  clearRun(); state.question = question.trim().slice(0,1000); state.draft = ''; state.result = null; state.page = 'ask'; state.running = true;
  history.replaceState(null,'','#ask'); setMenu(false); render(); window.scrollTo({top:0,behavior:'instant'});
  askLocal(runId);
}
async function askLocal(id) {
  const controller = new AbortController(); requestController = controller;
  const timeout = setTimeout(() => controller.abort(), 540000);
  announce('Searching your selected sources.');
  try {
    const sources = eligibleSources(state.sources, { collectionId: state.collectionId, selectedIds: state.selectedIds, asOf: state.asOf });
    if (!sources.length) throw new Error('Add a file or select a source before asking.');
    const response = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: state.question, sources, previous_questions: state.conversation }), signal: controller.signal });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not generate an answer.');
    if (id !== runId) return;
    state.result = result;
    if (result.answer_status !== 'unverified') state.conversation = [...state.conversation, state.question].slice(-3);
    state.history = [{ id: `query-${Date.now()}`, question: state.question, collectionId: state.collectionId, selectedIds: state.selectedIds, asOf: state.asOf }, ...state.history].slice(0, 8);
    persist(); state.running = false; render(); announce(result.answer_status === 'unverified' ? 'Original passages ready. A complete answer could not be verified.' : 'Answer ready. Open its sources to verify it.');
  } catch (error) {
    if (id !== runId) return;
    state.running = false; state.result = null; state.draft = state.question; render();
    toast(error.name === 'AbortError' ? 'The model took too long. Please try again.' : error.message);
  } finally { clearTimeout(timeout); if (requestController === controller) requestController = null; }
}
function sourceDialog(id, quote = '') {
  const s = getSource(id); if (!s) return;
  const dialog = $('#source-dialog');
  dialog.innerHTML = `<div class="source-content"><div class="dialog-head"><div><div class="eyebrow">Original source</div><h2 id="source-title">${esc(s.title)}</h2></div><button class="icon-button" data-close="source-dialog" aria-label="Close source" autofocus>${icon('close')}</button></div><div class="source-header-info"><span>${icon('calendar','icon-sm')} ${day(s.date_raw)}${s.date_raw ? ' ' + esc(s.date_raw.slice(0,4)) : ''}</span><span>·</span><span>${esc(s.history_id || 'Local document')}</span>${quote ? '<span class="pill">Quote highlighted</span>' : ''}</div><p class="source-demo-note">${s.format === 'pdf' ? `Extracted PDF text · page ${s.page_number} of ${s.total_pages}. Layout and images are not retained. ${esc(s.extraction_warning || '')}` : 'Original text from your file. Stored only in this browser.'}</p>${s.turns.map(t => {
    const at = quote ? t.content.indexOf(quote) : -1;
    const content = at >= 0 ? `${esc(t.content.slice(0,at))}<mark>${esc(quote)}</mark>${esc(t.content.slice(at+quote.length))}` : esc(t.content);
    return `<article class="turn ${t.role === 'assistant' ? 'assistant' : ''}"><div class="turn-heading"><span class="turn-avatar">${t.role === 'user' ? 'YOU' : 'AI'}</span>${esc(t.speaker)}</div><p>${content}</p></article>`;
  }).join('')}<div class="source-provenance">${esc(s.source_id)} · ${esc(s.revision)}<br>${s.format === 'pdf' ? 'Extracted text; verify complex tables and formatting in your original PDF.' : 'Original wording and message order preserved.'}</div></div>`;
  if (!dialog.open) dialog.showModal();
}
function showModal(html) { const dialog = $('#modal'); dialog.innerHTML = `<div class="modal-content">${html}</div>`; if (!dialog.open) dialog.showModal(); }
function dialogHead(title, sub = '') { return `<div class="dialog-head"><div><h2 id="modal-title">${title}</h2>${sub ? `<p>${sub}</p>` : ''}</div><button class="icon-button" data-close="modal" aria-label="Close dialog">${icon('close')}</button></div>`; }
function helpDialog() {
  showModal(`${dialogHead('About Recall', 'Answers grounded in your own files.')}<div class="help-step"><span class="step-circle">1</span><div><strong>Ask a question</strong><p>Ask in your own words, even in another language. Recall searches by meaning and keeps exact words and amounts searchable.</p></div></div><div class="help-step"><span class="step-circle">2</span><div><strong>See where the answer comes from</strong><p>Each number beside an answer opens the original quote.</p></div></div><div class="help-step"><span class="step-circle">3</span><div><strong>Add a note of your own</strong><p>Import PDF, TXT, Markdown or JSONL, then ask a question in your language.</p></div></div><div class="notice">${icon('info','icon-sm')}Files stay in this browser and are processed on this Mac. Answers may contain mistakes; check the quoted sources.</div><div class="form-actions"><button class="primary-button" data-close="modal">Got it ${icon('arrow','icon-sm')}</button></div>`);
}
function contextDialog() {
  const sources = currentSources();
  const hasDates = sources.some(s => s.date_raw);
  showModal(`${dialogHead('Where should we look?', hasDates ? 'Choose sources and an optional date.' : 'Choose which sources to search.')}<form id="context-form"><label class="check-row"><input type="checkbox" id="select-all" ${!state.selectedIds || state.selectedIds.length === sources.length ? 'checked' : ''}>All sources</label><div class="check-list">${sources.map(s => `<label class="check-row"><input type="checkbox" name="source" value="${esc(s.source_id)}" ${!state.selectedIds || state.selectedIds.includes(s.source_id) ? 'checked' : ''}><span>${esc(s.title)}<br><small>${day(s.date_raw)}</small></span></label>`).join('')}</div>${hasDates ? `<label class="form-field context-date"><span>Include conversations through this date</span><input type="date" name="asOf" value="${esc(state.asOf)}"></label><p class="import-note">Leave empty to use all conversations. Undated sources are excluded when a date is selected.</p>` : ''}<div class="form-actions"><button type="button" class="secondary-button" data-action="context-reset">Reset</button><button class="primary-button" type="submit">Apply</button></div></form>`);
}
function collectionsDialog() {
  showModal(`${dialogHead('Collections', 'Choose a workspace or create a collection.')}<div>${state.collections.map(c => `<button class="collection-option ${c.collection_id === state.collectionId ? 'selected' : ''}" data-collection="${esc(c.collection_id)}"><span class="workspace-icon">${esc(c.name.slice(0,2).toUpperCase())}</span><span class="name">${esc(c.name)}<small>Local sources · ${state.sources.filter(s => s.collection_id === c.collection_id).length} ${state.sources.filter(s => s.collection_id === c.collection_id).length === 1 ? 'source' : 'sources'}</small></span>${c.collection_id === state.collectionId ? icon('check','icon-sm') : ''}</button>`).join('')}</div><div class="form-actions"><button class="primary-button" data-action="new-collection">${icon('plus','icon-sm')} Create a collection</button></div>`);
}
function newCollectionDialog() { showModal(`${dialogHead('Create a collection', 'Keep related conversations and notes together.')}<form id="collection-form"><label class="form-field"><span>Collection name</span><input name="name" placeholder="My notes" maxlength="50" required autofocus></label><div class="form-actions"><button class="secondary-button" type="button" data-action="collections">Back</button><button class="primary-button" type="submit">Create</button></div></form>`); }
function importDialog() {
  state.pendingFile = null;
  showModal(`${dialogHead('Add a source', 'Import a PDF, a text file or a conversation export.')}<form id="import-form"><label class="form-field"><span>Collection</span><select name="collection"><option value="__new">New · My notes</option>${state.collections.map(c => `<option value="${esc(c.collection_id)}" ${c.collection_id === state.collectionId ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></label><label class="dropzone" id="dropzone">${icon('upload')}<strong id="file-label">Drop a file here, or choose one</strong><small>PDF up to 10 MB / 200 pages · TXT, Markdown, JSONL up to 1 MB</small><input id="file-input" type="file" accept=".pdf,.txt,.md,.jsonl" aria-label="Choose a file"></label><p class="import-note">Your file is stored in this browser and processed by the local model on this Mac. Ask questions and open the quoted sources. PDFs need selectable text; images and scans require OCR first. PDF layout and images are not retained. JSONL structure: history_id → sessions → turns.</p><div id="import-error" class="error-message" role="alert"></div><div class="form-actions"><button class="secondary-button" type="button" data-close="modal">Cancel</button><button class="primary-button" id="import-submit" type="submit">${icon('plus','icon-sm')} Add</button></div></form>`);
  const zone = $('#dropzone');
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('dragover'); state.pendingFile = e.dataTransfer.files[0]; $('#file-label').textContent = state.pendingFile?.name || 'Choose a file'; });
}
async function importFile(form) {
  const file = state.pendingFile || $('#file-input').files[0], error = $('#import-error');
  if (!file) { error.textContent = 'Choose a file first.'; return; }
  const isPdf = file.name.toLowerCase().endsWith('.pdf');
  if (file.size > (isPdf ? 10_000_000 : 1_000_000)) { error.textContent = isPdf ? 'Choose a PDF up to 10 MB.' : 'Choose a text file up to 1 MB.'; return; }
  const submit = $('#import-submit'); submit.disabled = true; submit.textContent = 'Reading your file…';
  try {
    const stamp = `${Date.now()}-${Math.random().toString(36).slice(2,7)}`;
    const selected = new FormData(form).get('collection');
    const cid = selected === '__new' ? `local-${stamp}` : selected;
    let sources, warning = '';
    if (isPdf) {
      submit.textContent = 'Reading PDF pages…';
      const response = await fetch('/api/import/pdf', { method: 'POST', headers: { 'Content-Type': 'application/pdf' }, body: file,
        signal: AbortSignal.timeout(60000) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not read this PDF.');
      sources = parsePdfImport(result, file.name, cid, stamp);
      warning = result.warning || '';
    } else sources = parseImport(await file.text(), file.name, cid, stamp);
    if (!form.isConnected || !$('#modal').open) return;
    const oldSources = state.sources, oldCollections = state.collections;
    if (selected === '__new') state.collections = [...state.collections, { collection_id:cid, name:'My notes', mode:'documents' }];
    state.sources = [...state.sources, ...sources];
    if (!persist()) { state.sources = oldSources; state.collections = oldCollections; throw new Error('Browser storage is full or unavailable. Please try a smaller file.'); }
    state.collectionId = cid; state.selectedIds = null; state.asOf = ''; state.sourceFilter = ''; state.sourceKind = 'all';
    $('#modal').close(); navigate('sources', true); persist(); toast(warning || `Sources added: ${sources.length}. Saved in this browser.`);
  } catch(e) { error.textContent = e.message || 'Could not read the file.'; submit.disabled = false; submit.innerHTML = `${icon('plus','icon-sm')} Add`; }
}
async function copyAnswer() {
  const r = state.result;
  const text = `[Recall · ${r.type === 'model' ? 'local AI answer' : 'source passages'}]\n\n${state.question}\n\n${r.answer}\n${r.detail}\n\n${r.citations.map((c,i) => `[${i+1}] ${getSource(c.source_id).title}: «${c.quote}»`).join('\n')}`;
  try { await navigator.clipboard.writeText(text); toast('Answer and source references copied.'); } catch { showModal(`${dialogHead('Copy answer')}<label class="form-field"><span>Select and copy the text</span><textarea id="copy-text" readonly rows="12" style="width:100%;font-size:14px;padding:12px;border-radius:0;border:1px solid #b5b5ad">${esc(text)}</textarea></label>`); $('#copy-text').select(); }
}
document.addEventListener('click', e => {
  const button = e.target.closest('button'); if (!button) return;
  if (button.dataset.close) { $(`#${button.dataset.close}`).close(); return; }
  if (button.dataset.page) { navigate(button.dataset.page); return; }
  if (button.dataset.source) { sourceDialog(button.dataset.source, state.page === 'sources' ? state.sourceMatches?.find(m => m.source_id === button.dataset.source)?.quote || '' : ''); return; }
  if (button.dataset.citation != null) { const c = state.result?.citations[Number(button.dataset.citation)]; if (c) sourceDialog(c.source_id, c.quote); return; }
  if (button.dataset.kind) { state.sourceKind = button.dataset.kind; renderMain(); return; }
  if (button.dataset.history) { const h = state.history.find(h => h.id === button.dataset.history); if (h) { state.conversation = []; state.selectedIds = h.selectedIds; state.asOf = h.asOf; ask(h.question); } return; }
  if (button.dataset.collection) { state.collectionId = button.dataset.collection; state.selectedIds = null; state.asOf = ''; state.sourceFilter = ''; state.sourceKind = 'all'; persist(); $('#modal').close(); navigate('ask', true); return; }
  const actions = { home: () => navigate('ask',true), menu: () => setMenu(!$('#sidebar').classList.contains('open')), 'close-menu': () => setMenu(false), help: helpDialog, context: contextDialog, collections: collectionsDialog, 'new-collection': newCollectionDialog, import: importDialog, copy: copyAnswer, 'retry-search': scheduleSourceSearch,
    cancel: () => { clearRun(); state.draft = state.question; state.result = null; render(); toast('Request cancelled.'); announce('Request cancelled.'); },
    'context-reset': () => { state.conversation = []; state.selectedIds = null; state.asOf = ''; $('#modal').close(); renderMain(); } };
  actions[button.dataset.action]?.();
});
document.addEventListener('input', e => {
  if (e.target.id === 'question') state.draft = e.target.value;
  if (e.target.id === 'source-search') { state.sourceFilter = e.target.value; scheduleSourceSearch(); }
});
document.addEventListener('change', e => {
  if (e.target.id === 'select-all') document.querySelectorAll('#context-form input[name="source"]').forEach(i => i.checked = e.target.checked);
  if (e.target.name === 'source') { const all = [...document.querySelectorAll('#context-form input[name="source"]')]; $('#select-all').checked = all.every(i => i.checked); }
  if (e.target.id === 'file-input') { state.pendingFile = e.target.files[0]; $('#file-label').textContent = state.pendingFile?.name || 'Choose a file'; }
});
document.addEventListener('submit', e => {
  if (e.target.id === 'question-form') { e.preventDefault(); ask(new FormData(e.target).get('question')); }
  if (e.target.id === 'context-form') { e.preventDefault(); state.conversation = []; const data = new FormData(e.target); const ids = data.getAll('source'); state.selectedIds = ids.length === currentSources().length ? null : ids; state.asOf = data.get('asOf') || ''; $('#modal').close(); renderMain(); }
  if (e.target.id === 'collection-form') {
    e.preventDefault(); const name = String(new FormData(e.target).get('name')).trim(); if (!name) return;
    const c = { collection_id:`local-collection-${Date.now()}`, name, mode:'documents' };
    state.collections.push(c);
    if (!persist()) { state.collections.pop(); toast('Could not save the collection. Browser storage is unavailable.'); return; }
    state.collectionId = c.collection_id; state.selectedIds = null; state.asOf = ''; persist(); $('#modal').close(); navigate('ask',true); toast('Collection created. Add your first file to begin.');
  }
  if (e.target.id === 'import-form') { e.preventDefault(); importFile(e.target); }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Tab' && $('#sidebar').classList.contains('open') && !$('#modal').open && !$('#source-dialog').open) {
    const stops = [...$('#sidebar').querySelectorAll('button:not(:disabled), summary'), $('.mobile-menu')].filter(el => el.getClientRects().length);
    const first = stops[0], last = stops.at(-1);
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.target.id === 'question') { e.preventDefault(); e.target.form.requestSubmit(); }
  if ((e.metaKey || e.ctrlKey) && e.key === 'k' && !$('#modal').open && !$('#source-dialog').open) { e.preventDefault(); if (state.page !== 'ask') navigate('ask',true); $('#question')?.focus(); }
  if (e.key === 'Escape') setMenu(false);
});
for (const dialog of [$('#modal'), $('#source-dialog')]) dialog.addEventListener('click', e => { if (e.target === dialog) { const r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close(); } });
window.addEventListener('hashchange', () => { const page = location.hash.slice(1); if (['ask','sources','memory'].includes(page)) navigate(page); });
if (location.hash === '#memory') history.replaceState(null, '', '#sources');
window.matchMedia('(min-width: 801px)').addEventListener('change', e => { if (e.matches) setMenu(false); });
render();
