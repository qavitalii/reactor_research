# A/B: baseline evidence vs evidence + code-computed timeline hint (prepared 2026-10-30, Claude thread)

Question set: `holdout46.jsonl` = 46 requests from `artifacts/holdout-final.jsonl` (independent holdout; questions
sharing gold evidence with the 80 tuning requests removed), 8 answerable per type + all 6 unanswerable, 44 histories.
Selection is deterministic: SHA256("ab-20261030:" + question_id). `gold46.jsonl` is the matching gold subset.

Arms (same runner `run_reactor_hints.py`, same `reactor_instructions.txt`, `--max-chars 17500`):
- `holdout46.jsonl`        -> `baseline/`  (identical evidence to the existing pipeline)
- `holdout46-hints.jsonl`  -> `hints/`     (22 of 46 requests get one extra passage from `hints.py`: session dates of
  the excerpts as day numbers from the earliest excerpt, question date as a day number, and which [E#] is the most
  recent; no source id, so a citation of it is dropped by the official converter; max message 16,207 chars)

Why: on dev, 14 of 21 numeric temporal gold answers equal a gap between gold session dates (or to the question
date); knowledge-update needs "which excerpt is latest". Reactor is a fast instruct model, so calendar arithmetic
is moved into code while Reactor still chooses the two events.

Run (needs the agent lease and the env file with REACTOR_* variables):
    bash artifacts/ab-20261030/run_ab.sh
Compare (partial results fine):
    .venv/bin/python artifacts/ab-20261030/ab_report.py baseline hints
