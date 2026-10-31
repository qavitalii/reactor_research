# Memory Retrieval Challenge: the pipeline

Team "Dealer Handshake" entry for the Reactive AI Memory Retrieval Challenge (START Warsaw x Poland Tech Week, 2026-10-30/31).
The presentation is in [`../idea/slides.pptx`](../idea/slides.pptx). The demo app is in [`../app/`](../app/README.md).

**Idea in one line: Reactor is the witness, code is the judge.** Reactor (the organisers' fast instruct agent, the only
model allowed to write the final answer) reads a few verbatim, dated excerpts and answers. Everything else is code and
small local models: finding the excerpts in a 200-conversation history, turning calendar arithmetic into day numbers,
deciding when an answer is not supported, and checking every answer against the official format.

## How it works

```
questions.jsonl + histories.jsonl
   │
   ▼  1. prepare      hybrid retrieval per history: stemmed BM25 over turn windows and sessions, BGE-small session
   │                  embeddings, a local cross-encoder reranker, reciprocal-rank fusion; two-part questions
   │                  ("days between X and Y") are searched per part; packs <= 14,500 chars of dated excerpts
   ▼  2. hints        code-computed passages: a day-number timeline for temporal/update questions; ownership cues when
   │                  an excerpt attributes the asked thing to someone else (the test set's decoys)
   ▼  3. runner       official client protocol: a fresh Reactor history per question (every request carries its full
   │                  evidence; this avoids the busy wait after each answer), [E#] labels = session ids, exact-message
   │                  preflight, citation repair, one format repair (alternatives / missing unit), resume-safe checkpoints
   ▼  4. finalize     code-side abstention rules (a zero count on "how many" = no such event in the history)
   ▼  5. validate     official format, ids and citation ownership
predictions.jsonl
```

## Run it

```bash
cd pipeline
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt       # CPU only; models download on first use
export REACTOR_BASE_URL=... REACTOR_AGENT_ID=... REACTOR_ACCESS_KEY=...   # from the participant kit; key only via env
.venv/bin/python -m memchal.run ../test runs/test                          # -> runs/test/predictions.jsonl
```

`memchal.run` is resumable: rerun the same command after an interruption and it continues from the last checkpoint.
`--dry-run` prepares the requests and preflights the exact Reactor messages without network or credentials.
Each stage is also its own CLI (`python -m memchal.prepare|hints|runner|finalize|validate|evaluate_retrieval --help`).

The submitted run used `--reranker cross-encoder/ettin-reranker-68m-v1 --chunk-dense --decompose` (needs
`requirements-ettin.txt`; see `MODELS.md`). Other switches: `--count-window` (date-window coverage for counting
questions, opt-in), `--retry-abstain`, `--count-hints` (both measured as not helping; off by default).
Instructions given to Reactor live in [`instructions/`](instructions/); `reactor_instructions.txt` is the one in use.

Self-scoring on the public dev split (gold is never read at runtime):

```bash
.venv/bin/python -m memchal.run ../dev runs/dev --partition holdout --limit 46
.venv/bin/python score.py ../dev/gold.jsonl runs/dev/predictions.jsonl
```

## Layout

| Path | What |
| --- | --- |
| `memchal/` | the pipeline package (retrieval, hints, decompose, runner, finalize, validate, audit, lease, run) |
| `reactor/` | the official participant kit: `client.py`, `predictions.py`, docs |
| `instructions/` | Reactor policies: v1 strict, v3 soft abstention, v4 required facts (in use) |
| `../app/` | the demo: `../app/web/` (three-step web UI served by `memchal.api`, FastAPI) and `../app/app.py` (the same flow in Streamlit); `../app/mock_reactor.py` lets anyone try it without credentials; see [`../app/README.md`](../app/README.md) and [`../app/API.md`](../app/API.md) |
| `experiments/` | what we measured: A/B runs, stress tests, retrieval ablations, reports |
| `tests/` | Automated tests, including an end-to-end run against a local fake Reactor (`pytest -q tests`) |
| `score.py`, `convert_longmemeval.py`, `format.md` | organisers' tools, unchanged |
| `MODELS.md` | the local models, where they come from, how they are cached |

## Submitted run

146 test questions: 131 answers and 15 abstentions, produced 2026-10-31 05:58-08:52 CET (median 61 s per Reactor call, a fresh
Reactor history per question), followed by a wider-retrieval rerun of 15 questions a human audit of the raw histories had marked
wrong or doubtful (24 sources, 26k-char packets; 11 answers changed). Details, raw Reactor replies and the merge rules:
[`experiments/final-run/RESULT.md`](experiments/final-run/RESULT.md). The file is `predictions.jsonl` at the repository root.

## Rules we follow

Final answers come from Reactor, produced by this code; no prediction is edited by hand. No external model API is used
anywhere: only Reactor plus small local models (embeddings, reranker) that run on the CPU. Gold labels are read only by
`score.py` and `memchal.evaluate_retrieval`, never by anything that builds a request or a prediction.
