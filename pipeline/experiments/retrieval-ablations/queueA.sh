#!/usr/bin/env bash
set -u
cd /home/alex/code/personal/memory-challenge
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
R=artifacts/retr-ab-20261031
ev() { .venv/bin/python evaluate_retrieval.py dev-large/gold.jsonl $R/$1.jsonl --histories dev-large/histories.jsonl --report $R/$1-report.json > $R/$1-eval.txt 2>&1; }
while pgrep -f "[p]repare.py dev-large $R/chunkdense.jsonl" >/dev/null; do sleep 10; done
ev chunkdense && echo "[$(date +%H:%M:%S)] chunkdense done"
run() { name=$1; py=$2; shift 2
  echo "[$(date +%H:%M:%S)] $name start"
  $py prepare.py dev-large $R/$name.jsonl "$@" > $R/$name.log 2>&1 && ev $name && echo "[$(date +%H:%M:%S)] $name done" || echo "[$(date +%H:%M:%S)] $name FAILED"; }
run twopart-control .venv/bin/python --only-two-part
run twopart-decompose .venv/bin/python --only-two-part --decompose
run combo .venv-ettin/bin/python --partition holdout --limit 40 --reranker cross-encoder/ettin-reranker-68m-v1 --chunk-dense --decompose
echo "[$(date +%H:%M:%S)] queueA finished"
