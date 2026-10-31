# Recall with local AI

A local application for asking questions about imported conversations and documents. The interface contains **Ask Recall** and **Sources**, with collection selection, source filters, recent questions and original-source inspection.

## Setup

Requirements: Python 3, Node.js/npm, Ollama and a modern browser. Install and start Ollama before running the launcher on a fresh checkout. In a separate terminal, if Ollama is not already running:

```sh
OLLAMA_NO_CLOUD=1 ollama serve
```

From the repository root:

```sh
npm run dev
```

The launcher creates `.venv`, installs `requirements.txt`, ensures the required models are available and starts the Python server on loopback port 4173. Open the local address printed by the server. Model downloads require internet access and several gigabytes of disk space; inference runs locally.

Defaults:

| Setting | Default | Purpose |
| --- | --- | --- |
| `RECALL_MODEL` | `qwen3:4b-instruct` | Answer generation and query reformulation |
| `RECALL_EMBED_MODEL` | `qwen3-embedding:4b` | Semantic retrieval |

The server connects to Ollama on loopback port 11434. If a project-local Ollama binary exists at `../../.cache/ollama-runtime/ollama`, the launcher can also start it and use `../../.cache/ollama-models`. Those runtime files, models, caches and virtual environments are not committed. A fresh checkout relies on your installed, running Ollama.

To start the Python service manually after starting Ollama:

```sh
ollama pull qwen3:4b-instruct
ollama pull qwen3-embedding:4b
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

## Import and storage

Create a collection and add PDF, TXT, Markdown or conversation JSONL. PDFs may be up to 10 MB / 200 pages, with at most one million extracted characters. Text files may be up to 1 MB; JSONL imports may contain up to 100 conversations. See the [root README](../../README.md) for the JSONL format.

PDF extraction runs in a separate local worker with a 45-second timeout. Each readable page becomes a source with its original page number. Blank or image-only pages are reported as skipped. Scans need OCR beforehand; password-protected files must be exported unlocked. Tables, columns, images and formatting may not be preserved.

Only extracted text is saved in browser storage; the original PDF is not retained. Collections and recent questions are also browser-local. Selected content goes to the local Python server and Ollama. There is no account sync or cloud inference. Keep original files because clearing site data removes imports.

Source-type controls appear for mixed collections; date controls appear when dated sources exist. A date cutoff excludes undated sources. The UI does not expose placeholder facts, timelines or feedback actions.

## Retrieval

The server embeds source passages and combines semantic similarity with BM25 and exact phrase boosts for names, codes and amounts. For queries with non-ASCII letters, the local answer model also creates two English retrieval formulations. The original question is retained; reformulations are search aids, never factual evidence.

Passages more than 0.15 below the best semantic match are excluded unless they contain the exact query. Up to 24 passages / 18,000 characters are supplied to the answer model. Overlapping or adjacent chunks from the same original turn are merged without joining across omitted text or different turns.

Short keyword and amount questions can return matching original passages directly, without generating an answer. Matching recognizes common PLN, UAH, EUR, USD (`US$`) and GBP labels and spaces in grouped amounts. It does not convert currencies.

The Sources view uses the same retrieval, returning snippets from up to eight distinct sources. Amount-only searches require an exact amount match; other results use a minimum semantic similarity of 0.4. This cutoff is not a probability. Debounced requests are serialized and stale results are discarded. Collection and source-type filters apply before source search; selected-source and date filters apply before question retrieval.

### Follow-up questions

The last three completed questions from the active conversation provide context for omitted subjects and retrieval. Unverified fallback questions are excluded. Only source text can support citations. Starting a new question, changing the collection or source/date filters, opening a history item, or reloading resets the context.

### Index cache

Embeddings are cached in `../../.cache/recall-embeddings.sqlite3`, up to 20,000 vectors. The cache contains hashes and vectors, not original text. Changes to text, titles or model digests produce new entries. Retrieval only ranks sources supplied in the current request; the cache never adds source text. Query translations are cached in process memory.

First searches index uncached files. Indexing has a four-minute request budget and saves completed batches so a retry can continue. Stop Recall before deleting the SQLite file to clear the derived index.

## Answer and citation verification

Answers are brief, up to 600 characters. Every supplied citation must match an allowed source passage. Tabs, line breaks and other whitespace are collapsed in the model's reading view and during matching; accepted quotes are mapped back to exact slices of the original text for display and highlighting. Words, punctuation, case, amounts and currencies must still match.

If the first generation has invalid citations, the server retries once with a schema that selects existing passage IDs. It copies original text for those IDs, so the model cannot rewrite the quotations. If verification still fails, generated claims are discarded and the UI shows original retrieved passages under **Review the original passages**, with an unverified-answer explanation. This is distinct from finding no evidence.

Quote validation does not guarantee every generated claim is correct. Semantic retrieval can miss a passage, particularly in long or poorly extracted files. Check the original source when accuracy matters.

## Service and limits

The Python service serves the UI and `/api/health`, `/api/ask`, `/api/search` and `/api/import/pdf`. It binds to loopback and validates request Host and Origin. No cloud model or external embedding API is used.

Cancellation stops the UI waiting; in-flight local inference may continue. Another request can report that Recall is busy. Missing required models produce an explicit setup error. DOCX parsing, OCR, automatic fact extraction and timelines are not included.

## Validation

From the repository root, `npm test` runs the local application checks and `npm run test:live` runs the live-model regressions. The commands below can also be run from this directory.

Unit and integration checks that do not require model inference:

```sh
npm test
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --check dist/app.js
node --check dist/memory.js
sh -n run-local.sh
```

Live checks require Ollama with both configured models:

```sh
.venv/bin/python tests/eval_followups.py
.venv/bin/python tests/eval_semantic.py
.venv/bin/python tests/eval_citations.py
```

- Follow-ups: broad amount/date questions, paraphrases, ambiguity, context and missing evidence.
- Semantic retrieval: nine Ukrainian, English and Polish paraphrases against more sources than fit the answer context, an unrelated query and three grounded answers.
- Citations: a synthetic Polish contract with tabs and line breaks, covering a Ukrainian summary, remuneration and deadline.

All live fixtures are synthetic. Model behavior may vary; these are regression checks, not a general accuracy benchmark. The [documentation screenshots](../../docs/README.md) use a separate fictional English collection imported through the real UI.
