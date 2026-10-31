"""Two-policy abstention: a question is an abstention only when both the strict policy (v4, main pass) and the soft
policy (v3, second opinion on the strict pass's abstentions) refuse. Where v3 answered, its answer and citations are
used. Both answers are Reactor's, converted by the official converter; nothing is chosen by outcome or gold.
Usage: python runs/test-final/merge_abstained.py BASE_RAW.jsonl V3_RUN V3_REQUESTS OUT.jsonl
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memchal.audit import read  # noqa: E402
from memchal.runner import checked_prediction  # noqa: E402

base_path, v3_run, v3_req, out_path = (Path(a) for a in sys.argv[1:5])
base = [json.loads(l) for l in base_path.read_text().splitlines() if l.strip()]
records = {r["question_id"]: r for r in read(v3_req)}
results = {r["question_id"]: r for r in read(v3_run / "results.jsonl")} if (v3_run / "results.jsonl").exists() else {}
replaced = 0
rows = []
for row in base:
    qid = row["question_id"]
    if row["abstain"] and qid in results and not results[qid]["abstained"]:
        rows.append(checked_prediction(results[qid], records[qid]))
        replaced += 1
    else:
        rows.append(row)
out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print(f"{len(rows)} predictions: {replaced} strict-policy abstentions answered by the soft policy", file=sys.stderr)
