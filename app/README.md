# Reactor application

For the current local Ollama interface, see [Local Recall](local/README.md). Run it from the repository root with `npm run dev`. The instructions below apply to the Reactor-backed application.

A one-page web app: add chat histories, prepare a search index, ask questions, get answers with sources.
Answers come only from Reactor, using the few excerpts our pipeline retrieves (BM25 + local embeddings + local reranker).

## Run

From the repository root (the app uses `pipeline/reactor/` and `pipeline/memchal/`):

    python3 -m venv .venv-app
    .venv-app/bin/pip install -q -r app/requirements.txt

Real Reactor (credentials only from the environment; the key is never shown or logged):

    export REACTOR_BASE_URL=... REACTOR_AGENT_ID=... REACTOR_ACCESS_KEY=...
    .venv-app/bin/python -m streamlit run app/app.py --server.headless true

Mock Reactor (no credentials; its answers are fake but follow the real protocol):

    .venv-app/bin/python app/mock_reactor.py        # prints three export lines; run them in the app's shell
    .venv-app/bin/python -m streamlit run app/app.py --server.headless true

Without the variables, steps 1 and 2 work and step 3 shows a notice.

Self-check (starts the mock, drives the page with Streamlit's AppTest): `.venv-app/bin/python app/check_app.py`

## The three steps

1. **Add your conversations**: `histories.jsonl` (challenge format, see [`pipeline/format.md`](../pipeline/format.md)), or `.txt`/`.md` chat exports
   (one conversation per file; `user:`/`assistant:` lines become messages, otherwise the whole file is one user message;
   dated from a date in the file name or first lines, else today), or "Try the demo conversations".
2. **Prepare**: reads the conversations and embeds each one (progress bar). Models are cached in `pipeline/.cache`
   and download on first use (about 150 MB); set `MEMCHAL_CACHE_DIR` to use another folder.
3. **Ask**: one question with an "as of" date (default: newest conversation), or a `questions.jsonl`
   (`question_id`, `history_id`, `question`, `question_date`) answered in a batch, then **Download predictions.jsonl**
   (`question_id`, `abstain`, `answer`, `citations`). Abstentions show "The conversations don't say that."
   If only one collection is loaded, questions with an unknown `history_id` are applied to it.

## Demo data

`app/demo/` holds history `h_fcb5ac4f8c08` from dev (50 conversations, 529 messages) and its one question,
`q_bdcc36b14f9a` ("Where did I redeem a $5 coupon on coffee creamer?"). No gold answers are included.

## Limitations

- One Reactor conversation at a time (process lease plus an in-app lock); a second browser tab waits or is told Reactor is busy.
- About 30-120 s per answer; a batch of N questions takes about N minutes. Stopping a batch keeps the answers so far.
- Each question opens a fresh Reactor history and carries its own excerpts.
- Glue code is `memchal/service.py`; the app does not modify other modules.
