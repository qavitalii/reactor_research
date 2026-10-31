#!/usr/bin/env bash
# Wider retrieval (2x candidates and sources, ~1.8x budget) for the audited questions.
cd /home/alex/code/personal/memory-challenge/pipeline
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
exec ../.venv-ettin/bin/python -m memchal.prepare ../test runs/test-rerun/requests24.jsonl --ids runs/test-rerun/audit-rerun.jsonl \
  --reranker cross-encoder/ettin-reranker-68m-v1 --chunk-dense --decompose --count-window \
  --candidates 144 --sessions 24 --budget 26000 --per-session 6500 > runs/test-rerun/prepare.log 2>&1
