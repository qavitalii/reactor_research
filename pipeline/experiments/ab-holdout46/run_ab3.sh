#!/usr/bin/env bash
# v2 hints (current hints.py). 46-question holdout A/B (2026-10-30 night): arm B = instructions-v3 + timeline hints + retry-on-abstain,
# arm A = current reactor_instructions.txt, no hints, no retry. B first: it is the candidate for the test run.
set -u
cd /home/alex/code/personal/memory-challenge
. "$HOME/.config/memchal/reactor.env"
export REACTOR_RUN_OWNER="$(python3 -I -c "import json;print(json.load(open('artifacts/reactor-leases/agt_284de70db1909e11.json')).get('owner',''))" 2>/dev/null)"
run_arm() {  # $1 = out dir, rest = runner args; resume up to 6 times on transient stops
  out=$1; shift
  for i in 1 2 3 4 5 6; do
    .venv/bin/python run_reactor_hints.py dev "$1" "$out" "${@:2}" --timeout 240 --max-chars 17500 && return 0
    echo "[$(date +%H:%M:%S)] arm $out stopped (try $i), resuming in 30 s"; sleep 30
  done
  return 1
}
echo "[$(date +%H:%M:%S)] arm B start"
run_arm artifacts/ab-20261030/armB2 artifacts/ab-20261030/holdout46-hints-v2.jsonl \
    --instructions artifacts/ab-20261030/instructions-v3.txt --retry-abstain
echo "[$(date +%H:%M:%S)] arm A start"
run_arm artifacts/ab-20261030/armA artifacts/ab-20261030/holdout46.jsonl
echo "[$(date +%H:%M:%S)] ab2 finished"
