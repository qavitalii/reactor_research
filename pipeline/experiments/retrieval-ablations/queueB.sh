#!/usr/bin/env bash
set -u
cd /home/alex/code/personal/memory-challenge
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
R=artifacts/retr-ab-20261031
ev() { .venv/bin/python evaluate_retrieval.py dev-large/gold.jsonl $R/$1.jsonl --histories dev-large/histories.jsonl --report $R/$1-report.json > $R/$1-eval.txt 2>&1; }
run() { name=$1; shift
  echo "[$(date +%H:%M:%S)] $name start"
  .venv/bin/python prepare.py dev-large $R/$name.jsonl --partition holdout --only-count "$@" > $R/$name.log 2>&1 && ev $name && echo "[$(date +%H:%M:%S)] $name done" || echo "[$(date +%H:%M:%S)] $name FAILED"; }
run count-control
run count-scan --candidates 200 --sessions 20
echo "[$(date +%H:%M:%S)] queueB finished"
