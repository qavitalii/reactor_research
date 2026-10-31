from memchal.validate import validate

QUESTIONS = [{"question_id": "q1", "history_id": "h1"}, {"question_id": "q2", "history_id": "h2"}]
HISTORIES = [{"history_id": "h1", "sessions": [{"session_id": "s1"}]},
             {"history_id": "h2", "sessions": [{"session_id": "s2"}]}]
PREDICTIONS = [{"question_id": "q1", "answer": "Pepper", "abstain": False, "citations": ["s1"]},
               {"question_id": "q2", "answer": "", "abstain": True, "citations": []}]


def test_valid_complete_submission():
    assert validate(PREDICTIONS, QUESTIONS, HISTORIES) == []


def test_wrong_user_citation_is_rejected():
    wrong = [{**PREDICTIONS[0], "citations": ["s2"]}, PREDICTIONS[1]]
    assert any("outside this history" in e for e in validate(wrong, QUESTIONS, HISTORIES))


def test_missing_and_duplicate_questions_are_rejected():
    errors = validate([PREDICTIONS[0], PREDICTIONS[0]], QUESTIONS, HISTORIES)
    assert any("duplicate question" in e for e in errors)
    assert any("missing question q2" in e for e in errors)


def test_malformed_ids_and_citations_fail_cleanly():
    wrong = [{"question_id": []}, {**PREDICTIONS[1], "citations": [{}]}]
    errors = validate(wrong, QUESTIONS, HISTORIES)
    assert any("question_id must be a string" in e for e in errors)
    assert any("citations must be" in e for e in errors)


def test_empty_factual_answer_cannot_pass():
    wrong = [{**PREDICTIONS[0], "answer": "", "citations": []}, PREDICTIONS[1]]
    errors = validate(wrong, QUESTIONS, HISTORIES)
    assert any("needs an answer" in e for e in errors)
    assert any("needs supporting citations" in e for e in errors)
