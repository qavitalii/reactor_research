"""Measure retrieval only; these numbers are NOT answer accuracy or citation F1."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from .retrieval import read_jsonl
from score import answer_matched


def extractable_answers(questions, gold, histories):
    """Only literal answers present in gold source text can measure excerpt retention."""
    by_id = {g["question_id"]: g for g in gold}
    grouped = defaultdict(list)
    for q in questions:
        grouped[q["history_id"]].append(q)
    found = {}
    for history in histories:
        if history["history_id"] not in grouped:
            continue
        sessions = {s["session_id"]: s for s in history["sessions"]}
        for q in grouped[history["history_id"]]:
            g = by_id[q["question_id"]]
            text = "\n".join(t["content"] for sid in g["evidence"] for t in sessions[sid]["turns"])
            found[q["question_id"]] = not g["abstain"] and answer_matched(text, g)
    return found


def evaluate(requests, gold, extractable=None):
    by_id = {g["question_id"]: g for g in gold}
    results = []
    for r in requests:
        g = by_id[r["question_id"]]
        if g["abstain"]:
            continue
        expected = set(g["evidence"])
        found = {p["id"] for p in r["passages"]}
        candidate = set(r["retrieval"]["ranked_sessions"])
        results.append({"question_id": r["question_id"], "type": g["question_type"],
                        "session_recall": len(expected & found) / len(expected),
                        "all_evidence": expected <= found,
                        "candidate_recall": len(expected & candidate) / len(expected),
                        "answer_phrase_present": answer_matched("\n".join(p["text"] for p in r["passages"]), g),
                        "answer_phrase_in_gold_excerpts": answer_matched("\n".join(p["text"] for p in r["passages"] if p["id"] in expected), g),
                        "extractable": extractable.get(r["question_id"]) if extractable else None,
                        "missing": sorted(expected - found), "chars": r["retrieval"]["chars"]})
    groups = defaultdict(list)
    for r in results:
        groups[r["type"]].append(r)
    groups["all"] = results
    summary = {}
    for name, rows in groups.items():
        if not rows:
            summary[name] = {"n": 0}
            continue
        summary[name] = {"n": len(rows), **{key: round(sum(r[key] for r in rows) / len(rows), 4)
                         for key in ["session_recall", "all_evidence", "candidate_recall", "answer_phrase_present", "chars"]}}
        if extractable is not None:
            eligible = [r for r in rows if r["extractable"]]
            summary[name]["extractable_n"] = len(eligible)
            summary[name]["extractable_answer_coverage"] = (round(sum(r["answer_phrase_in_gold_excerpts"] for r in eligible) / len(eligible), 4)
                                                          if eligible else None)
    return summary, results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gold", type=Path)
    ap.add_argument("requests", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--histories", type=Path, help="measure retained literal answers when gold text actually contains them")
    ap.add_argument("--exclude-evidence-from", type=Path, help="exclude questions sharing gold source sessions with these tuning requests")
    args = ap.parse_args()
    requests, gold = list(read_jsonl(args.requests)), list(read_jsonl(args.gold))
    excluded = []
    if args.exclude_evidence_from:
        by_id = {g["question_id"]: g for g in gold}
        used = {s for q in read_jsonl(args.exclude_evidence_from) for s in by_id[q["question_id"]]["evidence"]}
        excluded = [q["question_id"] for q in requests if used.intersection(by_id[q["question_id"]]["evidence"])]
        requests = [q for q in requests if q["question_id"] not in set(excluded)]
    extractable = extractable_answers(requests, gold, read_jsonl(args.histories)) if args.histories else None
    summary, details = evaluate(requests, gold, extractable)
    print(json.dumps(summary, indent=2))
    if excluded:
        print(f"Excluded {len(excluded)} questions with evidence shared with tuning")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"summary": summary, "details": details,
                                          "excluded_shared_evidence": excluded,
                                          "requests_evaluated": len(requests)}, indent=2) + "\n")


if __name__ == "__main__":
    main()
