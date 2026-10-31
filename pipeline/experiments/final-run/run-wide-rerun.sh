#!/usr/bin/env bash
# Fourth pass: audited questions with 2x retrieval width (artifacts/judge/rerun.jsonl). Then merge, finalize, validate.
set -u
cd /home/alex/code/personal/memory-challenge/pipeline 2>/dev/null
. "$HOME/.config/memchal/reactor.env"
PY=${PY:-../.venv/bin/python}
RR=runs/test-rerun; MAIN=runs/test-final; V3=runs/test-v3
until [ -s $RR/requests.jsonl ]; do sleep 10; done
$PY -m memchal.hints $RR/requests.jsonl $RR/requests-hints.jsonl --no-counts || exit 1
until [ -s $V3/merged-raw.jsonl ]; do sleep 15; done   # the three earlier passes are done
echo "[$(date +%H:%M:%S)] wide rerun start"
for i in $(seq 1 6); do
  $PY -m memchal.runner ../test $RR/requests-hints.jsonl $RR/reactor \
      --instructions $MAIN/instructions-used.txt --history-per-question --timeout 300 --max-chars 32000 && break
  echo "[$(date +%H:%M:%S)] runner stopped (try $i), resuming in 30 s"; sleep 30
done
$PY $MAIN/merge_rerun.py $V3/merged-raw.jsonl $RR/reactor $RR/requests-hints.jsonl $RR/merged-raw.jsonl \
  && $PY -m memchal.finalize ../test/questions.jsonl $RR/merged-raw.jsonl $RR/predictions.jsonl \
  && $PY -m memchal.validate ../test $RR/predictions.jsonl \
  && echo "[$(date +%H:%M:%S)] RERUN-MERGED predictions written: $RR/predictions.jsonl"
