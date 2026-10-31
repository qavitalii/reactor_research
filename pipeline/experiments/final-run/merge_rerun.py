"""Replace the predictions of an audited question list with the answers of a wider-retrieval rerun.

A human audit of the raw test histories (artifacts/judge) listed questions whose first answer looked wrong or doubtful.
They were re-run with twice the retrieval width; whatever Reactor answered there (answer or abstention) replaces the
earlier prediction, converted by the official converter. No prediction text is written by hand.
Usage: python runs/test-final/merge_rerun.py BASE_RAW.jsonl RERUN_RUN RERUN_REQUESTS OUT.jsonl
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memchal.audit import read  # noqa: E402
from memchal.runner import checked_prediction  # noqa: E402

base_path, run_dir, req_path, out_path = (Path(a) for a in sys.argv[1:5])
base = [json.loads(l) for l in base_path.read_text().splitlines() if l.strip()]
records = {r["question_id"]: r for r in read(req_path)}
results = {r["question_id"]: r for r in read(run_dir / "results.jsonl")} if (run_dir / "results.jsonl").exists() else {}
replaced = 0
rows = []
for row in base:
    qid = row["question_id"]
    if qid in results:
        rows.append(checked_prediction(results[qid], records[qid]))
        replaced += 1
    else:
        rows.append(row)
out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print(f"{len(rows)} predictions: {replaced} replaced by the wider-retrieval rerun", file=sys.stderr)
