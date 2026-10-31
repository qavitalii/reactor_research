import json

import memchal.runner as run_reactor_hints
from test_reactor_integration import KEY, POLICY, local_reactor, request


def run(records, tmp_path, server):
    return run_reactor_hints.execute(records, tmp_path, base_url=server["base_url"], agent_id="agt_test",
                                     access_key=KEY, instructions=POLICY, timeout=2, retry_abstain=True)


def predictions(tmp_path):
    return [json.loads(l) for l in (tmp_path / "predictions.jsonl").read_text().splitlines()]


def test_answer_is_not_rechecked(tmp_path):
    with local_reactor() as server:
        run([request("q1", "h1")], tmp_path, server)
        assert len(server["calls"]) == 1
    assert predictions(tmp_path)[0]["answer"] == "Pepper"


def test_abstention_is_asked_again_and_flip_is_kept(tmp_path):
    with local_reactor("abstain_once") as server:
        run([request("q1", "h1")], tmp_path, server)
        assert len(server["calls"]) == 2
        assert server["calls"][0]["history"] == server["calls"][1]["history"]
        assert run_reactor_hints.RECHECK in server["calls"][1]["text"]
        assert run_reactor_hints.RECHECK not in server["calls"][0]["text"]
    assert predictions(tmp_path)[0] == {"question_id": "q1", "abstain": False, "answer": "Pepper", "citations": ["s_h1"]}


def test_two_refusals_make_an_abstention(tmp_path):
    with local_reactor() as server:
        run([request("q1", "h1", "What is my hamster's name?")], tmp_path, server)
        assert len(server["calls"]) == 2
    assert predictions(tmp_path)[0]["abstain"] is True
    attempts = (tmp_path / "attempts.jsonl").read_text().splitlines()
    assert [json.loads(l).get("rechecked") for l in attempts if '"answered"' in l] == [False, True]


def test_history_per_question_opens_one_history_per_question(tmp_path):
    records = [request("q1", "h1"), request("q2", "h1"), request("q3", "h2")]
    with local_reactor() as server:
        receipt = run_reactor_hints.execute(records, tmp_path, base_url=server["base_url"], agent_id="agt_test",
                                            access_key=KEY, instructions=POLICY, timeout=2, history_per_question=True)
        assert receipt["complete"]
        assert len(server["histories"]) == 3
        assert [c["history"] for c in server["calls"]] == ["history-1", "history-2", "history-3"]
    attempts = [json.loads(l) for l in (tmp_path / "attempts.jsonl").read_text().splitlines()]
    assert [a["dataset_history_id"] for a in attempts if a["status"] == "history"] == ["h1", "h1", "h2"]
