from memchal.finalize import finalize


def p(answer, abstain=False):
    return {"question_id": "q", "abstain": abstain, "answer": answer, "citations": ["s_1"]}


def test_zero_count_becomes_abstention():
    assert finalize(p("0 [E3]"), "How many museums did I visit in December?")["abstain"] is True
    assert finalize(p("Zero museums"), "How many museums did I visit?")["abstain"] is True
    assert finalize(p("None"), "How much did I spend on wine?")["abstain"] is True


def test_nonzero_and_non_count_answers_are_kept():
    assert finalize(p("0.5 hours"), "How many hours of jogging did I do?")["abstain"] is False
    assert finalize(p("0,5 hours"), "How many hours of jogging did I do?")["abstain"] is False
    assert finalize(p("3"), "How many museums did I visit?")["abstain"] is False
    assert finalize(p("No"), "Did I visit the museum?")["abstain"] is False
    assert finalize(p("10 days"), "How many days passed?")["abstain"] is False
