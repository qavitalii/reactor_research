"""Merge two Reactor runs by a code-defined rule: counting questions with a named calendar window take their answer
from the count-window pass (which reserved every matching session in the window), every other question from the main
run. Both answers are Reactor's, converted by the official converter; nothing is chosen by outcome.
Usage: python runs/test-final/merge.py MAIN_RUN MAIN_REQUESTS CW_RUN CW_REQUESTS OUT.jsonl
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memchal.audit import read  # noqa: E402
from memchal.runner import checked_prediction  # noqa: E402

main_run, main_req, cw_run, cw_req, out_path = (Path(a) for a in sys.argv[1:6])
main_records = list(read(main_req))
cw_records = {r["question_id"]: r for r in read(cw_req)}
main_results = {r["question_id"]: r for r in read(main_run / "results.jsonl")}
cw_results = {r["question_id"]: r for r in read(cw_run / "results.jsonl")} if (cw_run / "results.jsonl").exists() else {}
rows, taken, missing = [], 0, 0
for record in main_records:
    qid = record["question_id"]
    if qid in cw_records and qid in cw_results:
        rows.append(checked_prediction(cw_results[qid], cw_records[qid]))
        taken += 1
    elif qid in main_results:
        rows.append(checked_prediction(main_results[qid], record))
    else:
        rows.append({"question_id": qid, "abstain": True, "answer": "", "citations": []})
        missing += 1
out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print(f"{len(rows)} predictions: {taken} from the count-window pass, {missing} unanswered filled as abstentions", file=sys.stderr)
