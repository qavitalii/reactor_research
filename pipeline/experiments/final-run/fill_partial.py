"""Deadline fallback: predictions for all 146 test questions from a partial Reactor run.

Completed questions get Reactor's validated answer (official converter); questions Reactor did not reach are
abstentions, which the format allows ("" answer, no citations). Then finalize and validate as usual.
Usage: python runs/test-final/fill_partial.py runs/test-final/reactor runs/test-final/requests-hints.jsonl OUT.jsonl
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memchal.audit import read  # noqa: E402
from memchal.runner import checked_prediction  # noqa: E402

run_dir, requests_path, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
records = list(read(requests_path))
results = {r["question_id"]: r for r in read(run_dir / "results.jsonl")} if (run_dir / "results.jsonl").exists() else {}
rows, missing = [], 0
for record in records:
    result = results.get(record["question_id"])
    if result:
        rows.append(checked_prediction(result, record))
    else:
        rows.append({"question_id": record["question_id"], "abstain": True, "answer": "", "citations": []})
        missing += 1
out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print(f"{len(rows)} predictions: {len(rows) - missing} from Reactor, {missing} filled as abstentions", file=sys.stderr)
