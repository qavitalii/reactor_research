#!/usr/bin/env bash
# Counting questions: control vs exhaustive-ish scan (200 lexical candidates, 20 sources, same 14,500 budget).
set -u
cd /home/alex/code/personal/memory-challenge
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
R=artifacts/retr-ab-20261031
while pgrep -f "[q]ueue.sh" >/dev/null; do sleep 15; done
for spec in "count-control|" "count-scan|--candidates 200 --sessions 20"; do
  name=${spec%%|*}; extra=${spec#*|}
  echo "[$(date +%H:%M:%S)] $name start"
  .venv/bin/python prepare.py dev-large $R/$name.jsonl --partition holdout --only-count $extra > $R/$name.log 2>&1 \
    && .venv/bin/python evaluate_retrieval.py dev-large/gold.jsonl $R/$name.jsonl --histories dev-large/histories.jsonl --report $R/$name-report.json > $R/$name-eval.txt 2>&1 \
    && echo "[$(date +%H:%M:%S)] $name done" || echo "[$(date +%H:%M:%S)] $name FAILED"
done
echo "[$(date +%H:%M:%S)] queue2 finished"
