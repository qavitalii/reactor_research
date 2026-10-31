#!/usr/bin/env bash
# Offline retrieval ablations on dev-large (no Reactor), one at a time; each changes ONE factor vs control.
set -u
cd /home/alex/code/personal/memory-challenge
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
R=artifacts/retr-ab-20261031
while pgrep -f "[p]repare.py dev-large $R/control.jsonl" >/dev/null; do sleep 10; done
run() { name=$1; py=$2; shift 2
  echo "[$(date +%H:%M:%S)] $name start"
  $py prepare.py dev-large $R/$name.jsonl "$@" > $R/$name.log 2>&1 || { echo "[$(date +%H:%M:%S)] $name FAILED"; tail -5 $R/$name.log; return; }
  echo "[$(date +%H:%M:%S)] $name done"; }
run ettin68 .venv-ettin/bin/python --partition holdout --limit 40 --reranker cross-encoder/ettin-reranker-68m-v1
run chunkdense .venv/bin/python --partition holdout --limit 40 --chunk-dense
run twopart-control .venv/bin/python --only-two-part
run twopart-decompose .venv/bin/python --only-two-part --decompose
for n in control ettin68 chunkdense twopart-control twopart-decompose; do
  [ -f $R/$n.jsonl ] && .venv/bin/python evaluate_retrieval.py dev-large/gold.jsonl $R/$n.jsonl --histories dev-large/histories.jsonl --report $R/$n-report.json > $R/$n-eval.txt 2>&1
done
echo "[$(date +%H:%M:%S)] queue finished"
