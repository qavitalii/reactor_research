#!/usr/bin/env bash
# After the A/B (run_ab4.sh) exits: swap-owner stress set with the arm B configuration (v3 + hints + retry).
set -u
cd /home/alex/code/personal/memory-challenge
. "$HOME/.config/memchal/reactor.env"
export REACTOR_RUN_OWNER="$(python3 -I -c "import json;print(json.load(open('artifacts/reactor-leases/agt_284de70db1909e11.json')).get('owner',''))" 2>/dev/null)"
S=artifacts/stress-20261031
while pgrep -f "[r]un_ab4.sh" >/dev/null || pgrep -f "[r]un_reactor_hints.py" >/dev/null; do sleep 15; done
echo "[$(date +%H:%M:%S)] stress B start"
for i in 1 2 3 4; do
  .venv/bin/python run_reactor_hints.py $S/split $S/swap-owner-hints.jsonl $S/armB \
      --instructions artifacts/ab-20261030/instructions-v3.txt --retry-abstain --timeout 240 --max-chars 17500 && break
  echo "[$(date +%H:%M:%S)] stress stopped (try $i), resuming in 30 s"; sleep 30
done
echo "[$(date +%H:%M:%S)] stress finished"
