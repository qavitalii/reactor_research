"""Check prepared evidence against public data, without importing retrieval or gold."""
import argparse
from collections import Counter
from datetime import datetime
import json
import os
import math
from pathlib import Path


def read(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def audit(split, requests, allow_subset=False):
    questions = {q["question_id"]: q for q in read(split / "questions.jsonl")}
    histories = {h["history_id"]: {s["session_id"]: s["date"] for s in h["sessions"]}
                 for h in read(split / "histories.jsonl")}
    ids = [r["question_id"] for r in requests]
    if (len(set(ids)) != len(ids) or not set(ids) <= set(questions)
            or not allow_subset and set(ids) != set(questions)):
        raise ValueError("Requests must cover every question exactly once")
    counts, sizes = [], []
    for r in requests:
        q = questions[r["question_id"]]
        for field in ("question", "question_date", "history_id"):
            if r[field] != q[field]:
                raise ValueError(f"{r['question_id']}: changed {field}")
        source_ids = [p["id"] for p in r["passages"]]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError(f"{r['question_id']}: repeated sources")
        question_date = datetime.strptime(q["question_date"], "%Y/%m/%d (%a) %H:%M")
        for p in r["passages"]:
            source = histories[q["history_id"]].get(p["id"])
            if source is None:
                raise ValueError(f"{r['question_id']}: source outside its history")
            if not p["text"].startswith("Session date: " + source + "\n"):
                raise ValueError(f"{r['question_id']}: incorrect source date")
            if datetime.strptime(source, "%Y/%m/%d (%a) %H:%M") > question_date:
                raise ValueError(f"{r['question_id']}: future source")
            if not math.isfinite(p["score"]):
                raise ValueError(f"{r['question_id']}: invalid retrieval score")
        chars = len(q["question"]) + len(q["question_date"]) + sum(len(p["text"]) + 80 for p in r["passages"])
        if chars != r["retrieval"]["chars"] or chars > int(os.environ.get("MEMCHAL_BUDGET", 14500)):
            raise ValueError(f"{r['question_id']}: invalid context budget")
        counts.append(len(source_ids))
        sizes.append(chars)
    return {"questions": len(requests), "histories": len({r["history_id"] for r in requests}),
            "complete_unique_questions": set(ids) == set(questions), "original_question_metadata": True,
            "source_ownership_and_dates": True, "unique_sources": True,
            "max_accounted_chars": max(sizes, default=0), "min_accounted_chars": min(sizes, default=0),
            "source_count_distribution": dict(sorted(Counter(counts).items())),
            "exact_reactor_serialization_checked": False, "answer_correctness_checked": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("split", type=Path)
    ap.add_argument("requests", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    result = audit(args.split, list(read(args.requests)))
    print(json.dumps(result, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
