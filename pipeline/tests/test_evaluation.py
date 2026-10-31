from memchal.evaluate_retrieval import evaluate


def test_distractor_answer_does_not_count_as_retained_gold_evidence():
    gold = [{"question_id": "q", "question_type": "single-session-user", "abstain": False,
             "evidence": ["correct"], "answer": "Pepper"}]
    requests = [{"question_id": "q", "passages": [{"id": "wrong", "text": "Pepper"}],
                 "retrieval": {"ranked_sessions": ["wrong", "correct"], "chars": 100}}]
    summary, _ = evaluate(requests, gold, {"q": True})
    assert summary["all"]["session_recall"] == 0
    assert summary["all"]["extractable_answer_coverage"] == 0


def test_abstention_only_sample_does_not_claim_retrieval_accuracy():
    gold = [{"question_id": "q", "question_type": "single-session-user", "abstain": True,
             "evidence": [], "answer": "unknown"}]
    summary, _ = evaluate([{"question_id": "q"}], gold)
    assert summary["all"] == {"n": 0}
