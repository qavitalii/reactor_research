#!/usr/bin/env bash
# Third pilot arm: same 7 questions, baseline evidence, softer-abstention instructions (instructions-v2.txt).
set -u
cd /home/alex/code/personal/memory-challenge
. "$HOME/.config/memchal/reactor.env"
export REACTOR_RUN_OWNER="$(python3 -I -c "import json;print(json.load(open('artifacts/reactor-leases/agt_284de70db1909e11.json')).get('owner',''))" 2>/dev/null)"
until grep -q "pilot finished\|giving up" artifacts/ab-20261030/pilot.log 2>/dev/null; do sleep 15; done
while pgrep -f "[e]xperiment_reactor.py run|[r]un_reactor.py " >/dev/null; do sleep 20; done
echo "[$(date +%H:%M:%S)] starting instr2 arm"
for i in 1 2 3 4 5 6; do
  .venv/bin/python run_reactor_hints.py dev artifacts/ab-20261030/pilot6.jsonl artifacts/ab-20261030/pilot-instr2 \
      --instructions artifacts/ab-20261030/instructions-v2.txt --timeout 240 --max-chars 17500 && break
  echo "[$(date +%H:%M:%S)] instr2 stopped (try $i), resuming in 30 s"; sleep 30
done
echo "[$(date +%H:%M:%S)] instr2 finished"
