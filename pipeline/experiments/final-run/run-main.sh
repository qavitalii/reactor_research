#!/usr/bin/env bash
# FINAL TEST RUN. Waits for every other Reactor process, then: hints -> runner (resume-safe) -> finalize -> validate.
# INSTRUCTIONS selects the Reactor policy file (set before launching).
set -u
cd /home/alex/code/personal/memory-challenge/pipeline
. "$HOME/.config/memchal/reactor.env"
INSTRUCTIONS=${INSTRUCTIONS:-instructions/reactor_instructions.txt}
OUT=runs/test-final
REQ=runs/test-combo/requests.jsonl
PAT_A="$(printf 'run_reactor_%s' 'hints.py')"; PAT_B="$(printf 'memchal.%s' 'runner')"; PAT_C="$(printf 'count-hint/%s' 'run.sh')"
while pgrep -f -- "$PAT_A|$PAT_B|$PAT_C" >/dev/null; do sleep 15; done
until [ -s "$REQ" ]; do sleep 20; done   # prepare writes requests.jsonl only when all 146 are done
echo "[$(date +%H:%M:%S)] final test run start; instructions=$INSTRUCTIONS"
${PY:-../.venv/bin/python} -m memchal.hints $REQ $OUT/requests-hints.jsonl --no-counts || exit 1
cp "$INSTRUCTIONS" $OUT/instructions-used.txt
for i in $(seq 1 12); do
  ${PY:-../.venv/bin/python} -m memchal.runner ../test $OUT/requests-hints.jsonl $OUT/reactor \
      --instructions "$INSTRUCTIONS" --history-per-question --timeout 300 --max-chars 19500 && break
  echo "[$(date +%H:%M:%S)] runner stopped (try $i), resuming in 45 s"; sleep 45
done
if [ -s $OUT/reactor/predictions.jsonl ]; then
  ${PY:-../.venv/bin/python} -m memchal.finalize ../test/questions.jsonl $OUT/reactor/predictions.jsonl $OUT/predictions.jsonl \
    && ${PY:-../.venv/bin/python} -m memchal.validate ../test $OUT/predictions.jsonl \
    && echo "[$(date +%H:%M:%S)] FINAL predictions written: $OUT/predictions.jsonl"
else
  echo "[$(date +%H:%M:%S)] runner incomplete; rerun this script to resume"
fi
