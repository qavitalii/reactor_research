"""Validate test submissions against public questions and histories, without gold."""
import argparse
import json
from pathlib import Path


def rows(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def validate(predictions, questions, histories):
    questions = {q["question_id"]: q for q in questions}
    sessions = {h["history_id"]: {s["session_id"] for s in h["sessions"]} for h in histories}
    errors, seen = [], set()
    for n, p in enumerate(predictions, 1):
        if not isinstance(p, dict):
            errors.append(f"line {n}: expected an object")
            continue
        qid = p.get("question_id")
        if not isinstance(qid, str):
            errors.append(f"line {n}: question_id must be a string")
            continue
        if qid in seen:
            errors.append(f"line {n}: duplicate question {qid}")
        seen.add(qid)
        if qid not in questions:
            errors.append(f"line {n}: unknown question {qid}")
            continue
        if type(p.get("abstain")) is not bool:
            errors.append(f"{qid}: abstain must be a boolean")
        if not isinstance(p.get("answer"), str):
            errors.append(f"{qid}: answer must be a string")
        elif p.get("abstain") is False and not p["answer"].strip():
            errors.append(f"{qid}: a non-abstention needs an answer")
        citations = p.get("citations")
        if not isinstance(citations, list) or not all(isinstance(c, str) for c in citations):
            errors.append(f"{qid}: citations must be a list of session IDs")
            continue
        if len(citations) != len(set(citations)):
            errors.append(f"{qid}: duplicate citations")
        allowed = sessions[questions[qid]["history_id"]]
        if set(citations) - allowed:
            errors.append(f"{qid}: citations outside this history: {sorted(set(citations) - allowed)}")
        if p.get("abstain") is False and not citations:
            errors.append(f"{qid}: a factual answer needs supporting citations")
    for qid in sorted(set(questions) - seen):
        errors.append(f"missing question {qid}")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("split", type=Path)
    ap.add_argument("predictions", type=Path)
    args = ap.parse_args()
    errors = validate(rows(args.predictions), rows(args.split / "questions.jsonl"), rows(args.split / "histories.jsonl"))
    if errors:
        raise SystemExit("\n".join(errors))
    print("Submission is complete; types, IDs and citation ownership are valid. Answer correctness is not checked.")


if __name__ == "__main__":
    main()
