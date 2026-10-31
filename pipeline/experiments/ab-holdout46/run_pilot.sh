#!/usr/bin/env bash
# Pilot: 6 questions, both arms, sequential. Waits until no other Reactor run holds the agent (never kills anything).
set -u
cd /home/alex/code/personal/memory-challenge
. "$HOME/.config/memchal/reactor.env"
export REACTOR_RUN_OWNER="$(python3 -I -c "import json;print(json.load(open('artifacts/reactor-leases/agt_284de70db1909e11.json')).get('owner',''))" 2>/dev/null)"
waited=0
while pgrep -f "[e]xperiment_reactor.py run|[r]un_reactor.py " >/dev/null; do
  sleep 20; waited=$((waited+20))
  if [ $waited -ge 3600 ]; then echo "[$(date +%H:%M:%S)] still blocked after 60 min; giving up"; exit 3; fi
done
echo "[$(date +%H:%M:%S)] agent free after ${waited}s wait; starting pilot"
run_arm() {  # $1 requests, $2 out dir; resume a few times on transient stops or a held lease
  for i in 1 2 3 4 5 6 7 8; do
    .venv/bin/python run_reactor_hints.py dev "$1" "$2" --timeout 240 --max-chars 17500 && return 0
    echo "[$(date +%H:%M:%S)] arm $2 stopped (try $i), resuming in 30 s"; sleep 30
  done
  return 1
}
run_arm artifacts/ab-20261030/pilot6.jsonl artifacts/ab-20261030/pilot-baseline
run_arm artifacts/ab-20261030/pilot6-hints.jsonl artifacts/ab-20261030/pilot-hints
echo "[$(date +%H:%M:%S)] pilot finished"
