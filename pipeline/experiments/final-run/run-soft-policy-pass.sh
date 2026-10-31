#!/usr/bin/env bash
# Third pass: the soft policy (v3) as a second opinion on every question the strict policy (v4) abstained on.
# Same packets as the main run. Then merge (two-policy abstention), finalize, validate.
set -u
cd /home/alex/code/personal/memory-challenge/pipeline 2>/dev/null
. "$HOME/.config/memchal/reactor.env"
PY=${PY:-../.venv/bin/python}
V3=runs/test-v3; MAIN=runs/test-final; CW=runs/test-cw
until [ -s $CW/merged-raw.jsonl ]; do sleep 15; done   # main run and count-window pass finished and merged
$PY - <<'PYEOF'
import json
abstained = {json.loads(l)["question_id"] for l in open("runs/test-cw/merged-raw.jsonl") if l.strip() and json.loads(l)["abstain"]}
with open("runs/test-final/requests-hints.jsonl") as f, open("runs/test-v3/requests-hints.jsonl", "w") as out:
    n = 0
    for line in f:
        if json.loads(line)["question_id"] in abstained:
            out.write(line); n += 1
print(f"{n} strict-policy abstentions go to the soft policy")
PYEOF
echo "[$(date +%H:%M:%S)] soft-policy pass start"
for i in $(seq 1 6); do
  $PY -m memchal.runner ../test $V3/requests-hints.jsonl $V3/reactor \
      --instructions instructions/v3-soft-abstention.txt --history-per-question --timeout 300 --max-chars 19500 && break
  echo "[$(date +%H:%M:%S)] runner stopped (try $i), resuming in 30 s"; sleep 30
done
$PY $MAIN/merge_abstained.py $CW/merged-raw.jsonl $V3/reactor $V3/requests-hints.jsonl $V3/merged-raw.jsonl \
  && $PY -m memchal.finalize ../test/questions.jsonl $V3/merged-raw.jsonl $V3/predictions.jsonl \
  && $PY -m memchal.validate ../test $V3/predictions.jsonl \
  && echo "[$(date +%H:%M:%S)] TWO-POLICY predictions written: $V3/predictions.jsonl"
