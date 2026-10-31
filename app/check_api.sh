#!/usr/bin/env bash
# End-to-end check of the HTTP API against the mock Reactor (never the real one). Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv-app/bin/python
BASE=http://127.0.0.1:8787
MOCK_PORT=${MOCK_PORT:-8766}  # 8765 may be taken by another service on this machine
WORK=$(mktemp -d)
PIDS=()
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$WORK"; }
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $*"; }
json() { $PY -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

export REACTOR_LEASE_DIR="$WORK/leases"
$PY app/mock_reactor.py "$MOCK_PORT" >"$WORK/mock.log" 2>&1 & PIDS+=($!)
sleep 2
kill -0 "${PIDS[0]}" 2>/dev/null || fail "mock Reactor did not start: $(tail -n 2 "$WORK/mock.log")"
export REACTOR_BASE_URL=http://127.0.0.1:$MOCK_PORT REACTOR_AGENT_ID=agt_mock REACTOR_ACCESS_KEY=mock-key-not-a-real-credential
$PY -m uvicorn memchal.api:app --app-dir pipeline --port 8787 >"$WORK/api.log" 2>&1 & PIDS+=($!)
for _ in $(seq 60); do curl -sf "$BASE/health" >/dev/null && break; sleep 1; done
curl -sf "$BASE/health" | grep -q '"reactor_configured":true' || fail "health"
ok "health $(curl -s $BASE/health)"

page=$(curl -s -o "$WORK/index.html" -w '%{http_code}' "$BASE/")
[ "$page" = 200 ] || fail "web UI returned $page"
for h in "Add your conversations" "Prepare" "Ask" "Or answer many questions at once"; do
  grep -q ">$h\|>$h<\|$h</h" "$WORK/index.html" || fail "web UI lacks heading: $h"
done
for f in app.js styles.css; do [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/$f")" = 200 ] || fail "$f"; done
ok "web UI served with the three step headings"

bad=$(curl -s -o /dev/null -w '%{http_code}' -F "files=@$WORK/index.html;filename=x.jsonl" "$BASE/collections")
[ "$bad" = 422 ] || fail "bad upload should be 422, got $bad"
ok "bad upload rejected (422)"

created=$(curl -sf -X POST "$BASE/collections?demo=1")
echo "$created"
CID=$(echo "$created" | json "d['collection_id']")
[ "$(echo "$created" | json "d['conversations']")" -gt 0 ] || fail "no conversations"
ok "collection $CID created"

early=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/collections/$CID/ask" -H 'Content-Type: application/json' -d '{"question":"hi"}')
[ "$early" = 409 ] || fail "ask before prepare should be 409, got $early"
ok "ask before prepare refused (409)"

curl -sf -X POST "$BASE/collections/$CID/prepare" >/dev/null
for _ in $(seq 600); do
  st=$(curl -sf "$BASE/collections/$CID/status")
  state=$(echo "$st" | json "d['state']")
  [ "$state" = ready ] && break
  [ "$state" = error ] && fail "prepare: $st"
  sleep 1
done
[ "$state" = ready ] || fail "prepare timed out"
ok "prepared: $st"

answer=$(curl -sf -X POST "$BASE/collections/$CID/ask" -H 'Content-Type: application/json' \
  -d '{"question":"Where did I redeem a $5 coupon on coffee creamer?","question_date":"2023-05-30"}')
echo "$answer" | cut -c1-300
echo "$answer" | json "len(d['citations'])" | grep -qv '^0$' || fail "no citations"
echo "$answer" | json "d['citations'][0]['excerpt']" | grep -q . || fail "empty excerpt"
echo "$answer" | json "d['abstain']" | grep -q False || fail "unexpected abstain"
echo "$answer" | json "d['latency_s']" >/dev/null || fail "latency"
ok "single question answered with citations"

abst=$(curl -sf -X POST "$BASE/collections/$CID/ask" -H 'Content-Type: application/json' -d '{"question":"What is my hamster called?"}')
echo "$abst" | json "d['abstain']" | grep -q True || fail "hamster question should abstain"
ok "abstention works (default as-of date)"

job=$(curl -sf -X POST -F "file=@app/demo/questions.jsonl" "$BASE/collections/$CID/batch")
JID=$(echo "$job" | json "d['job_id']")
for _ in $(seq 300); do
  js=$(curl -sf "$BASE/jobs/$JID")
  [ "$(echo "$js" | json "d['done']")" = True ] && break
  [ "$(echo "$js" | json "d['state']")" = error ] && fail "batch: $js"
  sleep 1
done
echo "$js" | json "d['done']" | grep -q True || fail "batch timed out"
ok "batch job $JID: $(echo "$js" | json "str(d['answered'])+' of '+str(d['total'])+' answered'")"

curl -sf "$BASE/jobs/$JID/predictions.jsonl" -o "$WORK/predictions.jsonl"
cat "$WORK/predictions.jsonl" | cut -c1-300
$PY - "$WORK/predictions.jsonl" <<'PYEOF' || fail "predictions.jsonl format"
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
assert rows and all(list(r) == ["question_id", "abstain", "answer", "citations"] for r in rows), rows
assert all(isinstance(r["abstain"], bool) and isinstance(r["citations"], list) for r in rows)
PYEOF
ok "predictions.jsonl has the official keys"

grep -q "$REACTOR_ACCESS_KEY" "$WORK/api.log" && fail "access key found in the API log"
curl -s "$BASE/jobs/$JID" | grep -q "$REACTOR_ACCESS_KEY" && fail "access key in a response"
ok "access key absent from logs and responses"
echo "ALL CHECKS PASSED"
