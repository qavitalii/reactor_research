#!/usr/bin/env bash
# Combined candidate configuration on the same 40 dev-large holdout questions: Ettin-68m + chunk-dense + decompose.
set -u
cd /home/alex/code/personal/memory-challenge
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
R=artifacts/retr-ab-20261031
while pgrep -f "[q]ueue2.sh|[q]ueue.sh" >/dev/null; do sleep 15; done
echo "[$(date +%H:%M:%S)] combo start"
.venv-ettin/bin/python prepare.py dev-large $R/combo.jsonl --partition holdout --limit 40 --reranker cross-encoder/ettin-reranker-68m-v1 --chunk-dense --decompose > $R/combo.log 2>&1 \
  && .venv/bin/python evaluate_retrieval.py dev-large/gold.jsonl $R/combo.jsonl --histories dev-large/histories.jsonl --report $R/combo-report.json > $R/combo-eval.txt 2>&1 \
  && echo "[$(date +%H:%M:%S)] combo done" || echo "[$(date +%H:%M:%S)] combo FAILED"
echo "[$(date +%H:%M:%S)] queue3 finished"
