import json

import pytest

import memchal.runner as runner
from test_reactor_integration import KEY, POLICY, local_reactor, request

DAYS = "How many days ago did I get my cat Pepper?"


def run(records, tmp_path, server, **kwargs):
    return runner.execute(records, tmp_path, base_url=server["base_url"], agent_id="agt_test",
                          access_key=KEY, instructions=POLICY, timeout=2, **kwargs)


def attempts(tmp_path):
    return [json.loads(l) for l in (tmp_path / "attempts.jsonl").read_text().splitlines() if '"answered"' in l]


def prediction(tmp_path):
    return json.loads((tmp_path / "predictions.jsonl").read_text())


@pytest.mark.parametrize("answer,question,expected", [
    ("Pepper or Salt [E1]", "What is my cat's name?", True),
    ("12 [E1]", DAYS, True),
    ("12 days [E1]", DAYS, False),
    ("12 [E1]", "How many cats do I have?", False),
    ("Pepper [E1]", "What is my cat's name?", False),
    ("INSUFFICIENT_EVIDENCE", DAYS, False),
    ("3 cats and 2 dogs, which is a long answer that goes well past a hundred and twenty characters in total [E1]",
     "How many pets do I have?", False),
])
def test_needs_format_repair(answer, question, expected):
    assert runner.needs_format_repair(answer, question) is expected


def test_alternative_is_asked_once_more_in_same_history_and_second_answer_kept(tmp_path):
    with local_reactor("alternative_once") as server:
        run([request("q1", "h1")], tmp_path, server)
        assert len(server["calls"]) == 2
        assert server["calls"][0]["history"] == server["calls"][1]["history"]
        assert server["calls"][0]["ref"] != server["calls"][1]["ref"]
        assert runner.FORMAT_REPAIR in server["calls"][1]["text"]
        assert runner.FORMAT_REPAIR not in server["calls"][0]["text"]
    assert prediction(tmp_path) == {"question_id": "q1", "abstain": False, "answer": "Pepper", "citations": ["s_h1"]}
    assert [a["format_repair"] for a in attempts(tmp_path)] == [False, True]
    assert len((tmp_path / "results.jsonl").read_text().splitlines()) == 1


def test_bare_number_for_unit_question_gets_the_unit(tmp_path):
    with local_reactor("bare_number") as server:
        run([request("q1", "h1", DAYS)], tmp_path, server)
        assert len(server["calls"]) == 2
    assert prediction(tmp_path)["answer"] == "12 days"


def test_at_most_one_format_repair_and_second_answer_kept_even_if_not_better(tmp_path):
    with local_reactor("alternative_always") as server:
        run([request("q1", "h1")], tmp_path, server)
        assert len(server["calls"]) == 2
    assert prediction(tmp_path)["answer"] == "Pepper or Salt"


def test_format_repair_never_becomes_an_abstention(tmp_path):
    with local_reactor("alternative_then_abstain") as server:
        run([request("q1", "h1")], tmp_path, server, retry_abstain=True)
        assert len(server["calls"]) == 2
    assert prediction(tmp_path)["abstain"] is False
    assert prediction(tmp_path)["answer"] == "Pepper or Salt"


def test_clean_answer_is_not_repaired(tmp_path):
    with local_reactor() as server:
        run([request("q1", "h1")], tmp_path, server)
        assert len(server["calls"]) == 1
    assert [a["format_repair"] for a in attempts(tmp_path)] == [False]


def test_hedged_two_candidate_answers_need_repair():
    from memchal.runner import needs_format_repair
    assert needs_format_repair("Nell (previously Juniper) [E1]", "What's my rescue greyhound's name?")
    assert needs_format_repair("Amici [E6] (earlier statement booked Osteria Numero [E4])", "What restaurant did I book?")
    assert needs_format_repair("Rifugio San Francesco (renamed from Rifugio Arca) [E1]", "Where do I volunteer?")
    assert not needs_format_repair("Juniper [E1][E2]", "What's my rescue greyhound's name?")
    assert not needs_format_repair("The Glass Menagerie [E2]", "What play did I attend before the trip?")
