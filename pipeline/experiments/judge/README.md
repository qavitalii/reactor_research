# Hand-judged test answers (no gold for the test split)

- `rerun.jsonl`: questions judged wrong or doubtful in the final run, with the expected answer found by reading the raw
  history and the session ids that carry it. Re-run these at the end (e.g. with wider retrieval / query expansion);
  the answer must still come from Reactor.
- `judged.tsv`: every checked answer with the verdict. Updated as the run progresses.
- `grep_hist.py HISTORY_ID PATTERN [PATTERN...]`: prints dated sentences of a test history matching all patterns.
