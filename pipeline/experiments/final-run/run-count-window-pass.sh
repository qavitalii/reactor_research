#!/usr/bin/env bash
# Second pass for counting questions with a named calendar window: same configuration as the main run plus
# --count-window packets. Then merge with the main run, finalize, validate.
set -u
cd /home/alex/code/personal/memory-challenge/pipeline 2>/dev/null
. "$HOME/.config/memchal/reactor.env"
PY=${PY:-../.venv/bin/python}
CW=runs/test-cw; MAIN=runs/test-final
until [ -s $CW/count-all.jsonl ]; do sleep 10; done
$PY - <<'PYEOF'
import json
rows = [json.loads(l) for l in open("runs/test-cw/count-all.jsonl") if l.strip()]
keep = [r for r in rows if r["retrieval"].get("required_evidence")]
with open("runs/test-cw/requests.jsonl", "w") as f:
    for r in keep:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"{len(keep)} windowed counting questions of {len(rows)} counting questions")
PYEOF
$PY -m memchal.hints $CW/requests.jsonl $CW/requests-hints.jsonl --no-counts || exit 1
until [ -s $MAIN/reactor/predictions.jsonl ]; do sleep 15; done   # wait for the main run to finish
echo "[$(date +%H:%M:%S)] count-window pass start"
for i in $(seq 1 6); do
  $PY -m memchal.runner ../test $CW/requests-hints.jsonl $CW/reactor \
      --instructions $MAIN/instructions-used.txt --history-per-question --timeout 300 --max-chars 19500 && break
  echo "[$(date +%H:%M:%S)] runner stopped (try $i), resuming in 30 s"; sleep 30
done
$PY $MAIN/merge.py $MAIN/reactor $MAIN/requests-hints.jsonl $CW/reactor $CW/requests-hints.jsonl $CW/merged-raw.jsonl \
  && $PY -m memchal.finalize ../test/questions.jsonl $CW/merged-raw.jsonl $CW/predictions.jsonl \
  && $PY -m memchal.validate ../test $CW/predictions.jsonl \
  && echo "[$(date +%H:%M:%S)] MERGED predictions written: $CW/predictions.jsonl"
