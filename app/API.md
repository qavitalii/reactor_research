# HTTP API and web UI

`pipeline/memchal/api.py` (FastAPI) wraps `pipeline/memchal/service.py` for the one-page web UI in `app/web/` (served at `/`).
State is kept in memory; restarting the server forgets all collections and jobs. Reactor credentials come only from the
environment and are never logged or returned.

## Run

From the repository root, with the app venv ([`app/README.md`](README.md); `app/requirements.txt` includes fastapi, uvicorn, python-multipart):

    export REACTOR_BASE_URL=... REACTOR_AGENT_ID=... REACTOR_ACCESS_KEY=...     # real Reactor
    .venv-app/bin/python -m uvicorn memchal.api:app --app-dir pipeline --port 8787  # open http://127.0.0.1:8787

Mock Reactor: `.venv-app/bin/python app/mock_reactor.py 8766`, run the three printed `export` lines, then start uvicorn.
Without the variables everything works except asking (503 with a plain message). Self-check: `app/check_api.sh`.

Errors are `{"detail": "<plain-language message>"}` with status 404 (unknown id), 409 (not prepared yet),
422 (unreadable file or date), 502 (Reactor failed), 503 (Reactor not configured). Interactive docs: `/api/docs`.

## Endpoints

`GET /health` -> `{"ok": true, "reactor_configured": bool}`

    curl localhost:8787/health

`POST /collections` (multipart `files`: `histories.jsonl` and/or `.txt`/`.md` exports; or `?demo=1`)
-> `{collection_id, conversations, messages, date_from, date_to}` (dates `YYYY-MM-DD`)

    curl -F files=@histories.jsonl localhost:8787/collections
    curl -X POST 'localhost:8787/collections?demo=1'

`POST /collections/{id}/prepare` -> `{state}`; starts indexing in a background thread (first run downloads about 150 MB of models).

    curl -X POST localhost:8787/collections/$ID/prepare

`GET /collections/{id}/status` -> `{state: pending|preparing|ready|error, progress: 0..1, message}`

    curl localhost:8787/collections/$ID/status

`POST /collections/{id}/ask` JSON `{question, question_date?, history_id?}` (`question_date` is `YYYY-MM-DD`, meaning the
end of that day, or the challenge format; default is the newest conversation) ->
`{question_id, question, answer, abstain, citations: [{session_id, date, excerpt}], latency_s}`.
Blocks until Reactor answers (30-120 s). One Reactor conversation at a time (`memchal.lease.agent_lease`).

    curl -X POST localhost:8787/collections/$ID/ask -H 'Content-Type: application/json' \
         -d '{"question": "Where did I redeem a $5 coupon on coffee creamer?", "question_date": "2023-05-30"}'

`POST /collections/{id}/batch` (multipart `file`: `questions.jsonl` with `question_id, history_id, question, question_date`)
-> `{job_id}`. With a single history, unknown `history_id` values are applied to it.

    curl -F file=@app/demo/questions.jsonl localhost:8787/collections/$ID/batch

`GET /jobs/{job_id}` -> `{done, total, answered, state: running|done|error, message, results: [ask-style answers so far]}`.
On `error` (e.g. Reactor failed) the answers so far are kept and downloadable.

    curl localhost:8787/jobs/$JOB

`GET /jobs/{job_id}/predictions.jsonl` -> the file, one `{"question_id","abstain","answer","citations"}` per line.

    curl -o predictions.jsonl localhost:8787/jobs/$JOB/predictions.jsonl
