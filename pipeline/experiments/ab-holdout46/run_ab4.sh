#!/usr/bin/env bash
# Finish arm B2 (resume if it stopped), then arm A only on the questions disputed in B2.
set -u
cd /home/alex/code/personal/memory-challenge
. "$HOME/.config/memchal/reactor.env"
export REACTOR_RUN_OWNER="$(python3 -I -c "import json;print(json.load(open('artifacts/reactor-leases/agt_284de70db1909e11.json')).get('owner',''))" 2>/dev/null)"
D=artifacts/ab-20261030
while pgrep -f "[r]un_reactor_hints.py dev $D/holdout46-hints-v2.jsonl" >/dev/null; do sleep 10; done
for i in 1 2 3 4 5 6; do
  python3 -I -c "import json,sys;sys.exit(0 if json.load(open('$D/armB2/receipt.json')).get('complete') else 1)" 2>/dev/null && break
  echo "[$(date +%H:%M:%S)] arm B2 incomplete, resuming (try $i)"
  .venv/bin/python run_reactor_hints.py dev $D/holdout46-hints-v2.jsonl $D/armB2 --instructions $D/instructions-v3.txt \
      --retry-abstain --timeout 240 --max-chars 17500 || sleep 30
done
echo "[$(date +%H:%M:%S)] arm B2 done"
.venv/bin/python $D/select_disputed.py || { echo "select failed"; exit 1; }
echo "[$(date +%H:%M:%S)] arm A start (disputed subset)"
for i in 1 2 3 4 5 6; do
  .venv/bin/python run_reactor_hints.py dev $D/armA-subset.jsonl $D/armA --timeout 240 --max-chars 17500 && break
  echo "[$(date +%H:%M:%S)] arm A stopped (try $i), resuming in 30 s"; sleep 30
done
echo "[$(date +%H:%M:%S)] ab4 finished"
