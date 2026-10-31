from copy import deepcopy
import json

import pytest

from memchal.audit import audit


@pytest.fixture
def prepared(tmp_path):
    date = "2026/10/01 (Thu) 09:00"
    q = {"question_id": "q", "history_id": "h1", "question": "What is my cat's name?", "question_date": date}
    histories = [{"history_id": "h1", "sessions": [{"session_id": "s1", "date": date}]},
                 {"history_id": "h2", "sessions": [{"session_id": "s2", "date": date}]}]
    (tmp_path / "questions.jsonl").write_text(json.dumps(q) + "\n")
    (tmp_path / "histories.jsonl").write_text("\n".join(map(json.dumps, histories)) + "\n")
    text = f"Session date: {date}\nuser (t1): My cat is Pepper."
    request = {**q, "passages": [{"id": "s1", "text": text, "score": 0.1}],
               "retrieval": {"chars": len(q["question"]) + len(date) + len(text) + 80}}
    return tmp_path, [request]


def test_complete_requests_pass_independent_audit(prepared):
    root, requests = prepared
    result = audit(root, requests)
    assert result["questions"] == 1
    assert result["source_ownership_and_dates"]
    assert not result["answer_correctness_checked"]


def test_audit_rejects_another_users_source(prepared):
    root, requests = prepared
    wrong = deepcopy(requests)
    wrong[0]["passages"][0]["id"] = "s2"
    with pytest.raises(ValueError, match="outside its history"):
        audit(root, wrong)


def test_audit_rejects_missing_question_and_falsified_budget(prepared):
    root, requests = prepared
    with pytest.raises(ValueError, match="every question exactly once"):
        audit(root, [])
    wrong = deepcopy(requests)
    wrong[0]["retrieval"]["chars"] = 1
    with pytest.raises(ValueError, match="invalid context budget"):
        audit(root, wrong)
