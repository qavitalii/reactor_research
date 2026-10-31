#!/usr/bin/env bash
# After arm A + stress: instructions v4 (+hints, +retry) on the sensitive holdout subset, then on the swap-owner stress set.
set -u
cd /home/alex/code/personal/memory-challenge
. "$HOME/.config/memchal/reactor.env"
export REACTOR_RUN_OWNER="$(python3 -I -c "import json;print(json.load(open('artifacts/reactor-leases/agt_284de70db1909e11.json')).get('owner',''))" 2>/dev/null)"
D=artifacts/ab-20261030; S=artifacts/stress-20261031
while pgrep -f "[r]un_ab4.sh|[r]un_stress.sh|[r]un_reactor_hints.py" >/dev/null; do sleep 15; done
run() { out=$1; split=$2; req=$3
  echo "[$(date +%H:%M:%S)] $out start"
  for i in 1 2 3 4; do
    .venv/bin/python run_reactor_hints.py $split $req $out --instructions $D/instructions-v4.txt --retry-abstain --timeout 240 --max-chars 17500 && break
    echo "[$(date +%H:%M:%S)] $out stopped (try $i), resuming in 30 s"; sleep 30
  done
  echo "[$(date +%H:%M:%S)] $out done"; }
run $D/armV4 dev $D/sensitive-v4.jsonl
run $S/armV4 $S/split $S/swap-owner-hints.jsonl
echo "[$(date +%H:%M:%S)] v4 finished"
