#!/usr/bin/env bash
# A/B on 46 holdout questions: baseline evidence vs evidence + timeline hint. Same runner for both arms.
set -u
cd /home/alex/code/personal/memory-challenge
. "$HOME/.config/memchal/reactor.env"
LOCK=/tmp/reactor-t04.lock
while pgrep -f "run_reactor.py dev artifacts/reactor-smoke" >/dev/null; do sleep 15; done   # other thread's smoke run
echo "$$ memory-challenge A/B (Claude thread) started $(date -Is)" > "$LOCK"
run_arm() {  # $1 = requests, $2 = out dir; resume up to 6 times on transient stops
  for i in 1 2 3 4 5 6; do
    .venv/bin/python run_reactor_hints.py dev "$1" "$2" --timeout 240 --max-chars 17500 && break
    echo "[$(date +%H:%M:%S)] arm $2 stopped (try $i), resuming in 20 s"; sleep 20
  done
}
run_arm artifacts/ab-20261030/holdout46.jsonl artifacts/ab-20261030/baseline
run_arm artifacts/ab-20261030/holdout46-hints.jsonl artifacts/ab-20261030/hints
rm -f "$LOCK"
echo "A/B finished $(date -Is)"
