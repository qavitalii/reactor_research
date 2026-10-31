#!/usr/bin/env bash
# After the v4 runs: count-hint test (v3 + timeline + count hints + retry) on the holdout46 counting questions.
set -u
cd /home/alex/code/personal/memory-challenge/pipeline
. "$HOME/.config/memchal/reactor.env"
while pgrep -f "[r]un_v4.sh|[r]un_reactor_hints.py" >/dev/null; do sleep 15; done
echo "[$(date +%H:%M:%S)] count-hint start"
for i in 1 2 3 4; do
  ../.venv/bin/python -m memchal.runner ../dev runs/count-hint/requests.jsonl runs/count-hint/armC \
      --instructions instructions/v3-soft-abstention.txt --retry-abstain --timeout 240 --max-chars 19500 && break
  echo "[$(date +%H:%M:%S)] count-hint stopped (try $i), resuming in 30 s"; sleep 30
done
echo "[$(date +%H:%M:%S)] count-hint finished"
