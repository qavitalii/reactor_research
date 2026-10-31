"""Code-side abstention rules applied to validated predictions (the answer text stays Reactor's).

A count question ("how many / how much") answered with zero means the history has no such event: on dev,
no answerable count question has a zero gold answer, while unanswerable ones do get "0" from Reactor.
"""
from __future__ import annotations

import json
import re
import sys

COUNT = re.compile(r"\bhow (many|much)\b", re.I)
ZERO = re.compile(r"^\W*(0|zero|none|no)(?![.,]?\d)\b", re.I)


def finalize(prediction: dict, question: str) -> dict:
    if not prediction["abstain"] and COUNT.search(question) and ZERO.match(prediction["answer"]):
        return {**prediction, "abstain": True}
    return prediction


def main(questions_path, predictions_path, output_path):
    questions = {json.loads(l)["question_id"]: json.loads(l)["question"] for l in open(questions_path) if l.strip()}
    changed = 0
    with open(predictions_path) as f, open(output_path, "w") as out:
        for line in f:
            p = json.loads(line)
            q = finalize(p, questions[p["question_id"]])
            changed += q != p
            out.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"{changed} predictions turned into abstentions", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
