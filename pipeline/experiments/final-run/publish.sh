#!/usr/bin/env bash
# Merge whatever the audited rerun has answered so far into the main-pass predictions, finalize, validate, publish.
set -eu
cd /home/alex/code/personal/memory-challenge/pipeline
RR=runs/test-rerun; MAIN=runs/test-final
../.venv/bin/python $MAIN/merge_rerun.py $MAIN/reactor/predictions.jsonl $RR/reactor24 $RR/requests24-hints.jsonl $RR/merged-raw.jsonl
../.venv/bin/python -m memchal.finalize ../test/questions.jsonl $RR/merged-raw.jsonl $RR/predictions.jsonl
../.venv/bin/python -m memchal.validate ../test $RR/predictions.jsonl
cd /home/alex/code/personal/reactor-research && git pull -q --rebase origin main && cp /home/alex/code/personal/memory-challenge/pipeline/$RR/predictions.jsonl predictions.jsonl
if ! git diff --quiet -- predictions.jsonl; then git add predictions.jsonl && git commit -q -m "feat: update test predictions with the audited wide-retrieval rerun" && git push -q origin HEAD:main && echo "pushed $(git log --oneline -1)"; else echo "no change"; fi
