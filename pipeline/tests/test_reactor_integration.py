import asyncio
from contextlib import contextmanager
import json
import re
import sys
import threading

from aiohttp import web
import pytest

from reactor import client
from memchal.runner import execute, format_request, load_completed, main


POLICY = "Use only these excerpts. Cite supporting evidence and abstain when it is absent."
KEY = "unit-test-only-not-a-real-credential"


def request(qid, hid, question="What is my cat's name?"):
    date = "2026/10/01 (Thu) 09:00"
    text = f"Session date: {date}\nuser (t_example): My cat is Pepper."
    return {"question_id": qid, "history_id": hid, "question": question, "question_date": date,
            "passages": [{"id": "s_" + hid, "text": text, "score": 0.1}],
            "retrieval": {"chars": len(question) + len(date) + len(text) + 80}}


@contextmanager
def local_reactor(mode="normal"):
    """Actual localhost HTTP+WebSocket service; no external endpoint or real credential."""
    state = {"histories": [], "calls": [], "mode": mode, "cycle": 0}
    ready, stop = threading.Event(), threading.Event()

    async def reset(req):
        if req.headers.get("Authorization") != "Bearer " + KEY:
            raise web.HTTPForbidden()
        hid = f"history-{len(state['histories']) + 1}"
        state["histories"].append(hid)
        return web.json_response({"history_id": hid, "running": True})

    async def chat(req):
        if req.headers.get("Authorization") != "Bearer " + KEY:
            raise web.HTTPForbidden()
        assert req.query["history"] == state["histories"][-1]
        ws = web.WebSocketResponse()
        await ws.prepare(req)
        frame = await ws.receive_json()
        text = frame["text"]
        ref = re.search(r"\[ref:([0-9a-f]{8})\] Question:", text).group(1)
        state["calls"].append({"history": req.query["history"], "text": text, "ref": ref})
        state["cycle"] += 2
        cycle = state["cycle"]
        if state["mode"] == "busy_once" and len(state["calls"]) == 1:
            await ws.send_json({"type": "error", "code": "busy", "forwarded": False})
            await ws.close()
            return ws
        await ws.send_json({"type": "ack", "text": text, "cycle": cycle})
        await ws.send_json({"type": "reply", "text": f"Thinking about ref:{ref}.", "cycle": cycle + 1})
        stale_ref = "00000000" if ref != "00000000" else "ffffffff"
        await ws.send_json({"type": "reply", "text": f"# FINAL ANSWER [ref:{stale_ref}]: stale wrong answer [E99]",
                            "cycle": cycle + 1})
        if state["mode"] == "timeout":
            await asyncio.sleep(0.25)
        else:
            answer = "INSUFFICIENT_EVIDENCE" if "hamster" in text else "Pepper [E1]"
            if state["mode"] == "uncited_once" and len(state["calls"]) == 1:
                answer = "Pepper"
            if state["mode"] == "abstain_once" and len(state["calls"]) == 1:
                answer = "INSUFFICIENT_EVIDENCE"
            if state["mode"] == "alternative_once":
                answer = "Pepper or Salt [E1]" if len(state["calls"]) == 1 else "Pepper [E1]"
            if state["mode"] == "alternative_always":
                answer = "Pepper or Salt [E1]"
            if state["mode"] == "bare_number":
                answer = "12 [E1]" if len(state["calls"]) == 1 else "12 days [E1]"
            if state["mode"] == "alternative_then_abstain":
                answer = "Pepper or Salt [E1]" if len(state["calls"]) == 1 else "INSUFFICIENT_EVIDENCE"
            if state["mode"] == "unknown_always":
                answer = "Pepper [E999]"
            await ws.send_json({"type": "reply", "text": f"# FINAL ANSWER [ref:{ref}]: {answer}", "cycle": cycle + 1})
        await ws.close()
        return ws

    async def serve():
        app = web.Application()
        app.router.add_post("/agents/{agent}/history", reset)
        app.router.add_get("/agents/{agent}/ws/chat", chat)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        state["base_url"] = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        ready.set()
        while not stop.is_set():
            await asyncio.sleep(0.01)
        await runner.cleanup()

    thread = threading.Thread(target=lambda: asyncio.run(serve()), daemon=True)
    thread.start()
    assert ready.wait(5), "Local test server did not start"
    try:
        yield state
    finally:
        stop.set()
        thread.join(5)
        assert not thread.is_alive(), "Local test server did not stop"


def run(records, tmp_path, server, **kwargs):
    return execute(records, tmp_path, base_url=server["base_url"], agent_id="agt_test",
                   access_key=KEY, instructions=POLICY, timeout=kwargs.pop("timeout", 2), **kwargs)


def test_http_websocket_history_isolation_citations_and_abstention(tmp_path):
    records = [request("q1", "h1"), request("q2", "h1"), request("q3", "h2", "What is my hamster's name?")]
    with local_reactor() as server:
        receipt = run(records, tmp_path, server)
        assert receipt["complete"]
        assert len(server["histories"]) == 2
        assert [c["history"] for c in server["calls"]] == ["history-1", "history-1", "history-2"]
        assert all(KEY not in c["text"] and len(c["text"]) <= 16000 for c in server["calls"])
    predictions = [json.loads(l) for l in (tmp_path / "predictions.jsonl").read_text().splitlines()]
    assert predictions[0] == {"question_id": "q1", "abstain": False, "answer": "Pepper", "citations": ["s_h1"]}
    assert predictions[2] == {"question_id": "q3", "abstain": True, "answer": "", "citations": []}
    results = list(load_completed(tmp_path / "results.jsonl", records).values())
    assert all(r["late_replies"] and r["other_replies"] for r in results)
    assert KEY not in (tmp_path / "results.jsonl").read_text()
    assert KEY not in (tmp_path / "attempts.jsonl").read_text()


def test_uncited_answer_is_repaired_in_same_history(tmp_path):
    with local_reactor("uncited_once") as server:
        run([request("q1", "h1")], tmp_path, server)
        assert len(server["histories"]) == 1
        assert len(server["calls"]) == 2
        assert server["calls"][0]["ref"] != server["calls"][1]["ref"]
    assert len((tmp_path / "results.jsonl").read_text().splitlines()) == 1


def test_unknown_citations_cannot_become_predictions(tmp_path):
    with local_reactor("unknown_always") as server:
        with pytest.raises(RuntimeError, match="invalid answer after citation repair"):
            run([request("q1", "h1")], tmp_path, server)
        assert len(server["calls"]) == 2
    assert not (tmp_path / "predictions.jsonl").exists()
    assert not (tmp_path / "results.jsonl").exists()


def test_timeout_is_not_an_abstention_and_resume_succeeds(tmp_path):
    records = [request("q1", "h1")]
    with local_reactor("timeout") as server:
        with pytest.raises(RuntimeError, match="timeout"):
            run(records, tmp_path, server, timeout=0.05)
        assert not (tmp_path / "predictions.jsonl").exists()
        assert not (tmp_path / "results.jsonl").exists()
        server["mode"] = "normal"
        assert run(records, tmp_path, server)["complete"]
        assert len(server["histories"]) == 2
    result = json.loads((tmp_path / "predictions.jsonl").read_text())
    assert not result["abstain"]


def test_resume_skips_completed_questions_without_duplicates(tmp_path):
    records = [request("q1", "h1"), request("q2", "h1"), request("q3", "h2")]
    with local_reactor() as server:
        first = run(records, tmp_path, server, max_questions=1)
        assert not first["complete"]
        assert not (tmp_path / "predictions.jsonl").exists()
        second = run(records, tmp_path, server)
        assert second["new_answers"] == 2
        assert len(server["calls"]) == 3
        assert len(server["histories"]) == 3  # first run h1, resumed h1, then h2
        assert run(records, tmp_path, server)["new_answers"] == 0
        assert len(server["histories"]) == 3


def test_official_client_retries_only_unforwarded_busy(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "_RETRY_FIRST", 0.01)
    with local_reactor("busy_once") as server:
        run([request("q1", "h1")], tmp_path, server)
        assert len(server["calls"]) == 2
    result = json.loads((tmp_path / "results.jsonl").read_text())
    assert result["retries"] == 1


def test_actual_message_format_preserves_date_and_enforces_limit():
    r = request("q1", "h1")
    message, passages, date = format_request(r, POLICY, "1234abcd")
    assert date == "2026-10-01 09:00"
    assert passages[0]["date"] == r["question_date"]
    assert "[E1] (source: s_h1, date: 2026/10/01 (Thu) 09:00)" in message
    assert "# FINAL ANSWER [ref:1234abcd]:" in message
    with pytest.raises(ValueError, match="serialized message"):
        format_request(r, POLICY, "1234abcd", max_chars=100)


def test_checkpoint_rejects_tampered_citation_metadata(tmp_path):
    records = [request("q1", "h1")]
    with local_reactor() as server:
        run(records, tmp_path, server)
    path = tmp_path / "results.jsonl"
    result = json.loads(path.read_text())
    result["citations"][0]["id"] = "s_other_user"
    path.write_text(json.dumps(result) + "\n")
    with pytest.raises(ValueError, match="metadata does not match"):
        load_completed(path, records)


@pytest.fixture
def driver_files(tmp_path):
    split = tmp_path / "split"
    split.mkdir()
    records = [request("q1", "h1"), request("q2", "h1")]
    (split / "questions.jsonl").write_text("".join(json.dumps({k: r[k] for k in
        ["question_id", "history_id", "question", "question_date"]}) + "\n" for r in records))
    (split / "histories.jsonl").write_text(json.dumps({"history_id": "h1", "sessions": [
        {"session_id": "s_h1", "date": records[0]["question_date"]}]}) + "\n")
    requests = tmp_path / "requests.jsonl"
    requests.write_text("".join(json.dumps(r) + "\n" for r in records))
    policy = tmp_path / "policy.txt"
    policy.write_text(POLICY)
    out = tmp_path / "out"
    argv = ["run_reactor.py", str(split), str(requests), str(out), "--instructions", str(policy)]
    return argv, policy, out


def test_dry_run_needs_no_credentials_or_network(driver_files, monkeypatch):
    argv, _, out = driver_files
    monkeypatch.delenv("REACTOR_ACCESS_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", argv + ["--dry-run"])
    assert main() == 0
    report = json.loads((out / "preflight.json").read_text())
    assert report["exact_reactor_serialization_checked"]
    assert report["reactor_histories_required"] == 1
    assert not (out / "results.jsonl").exists()


def test_changed_instructions_cannot_mix_with_saved_results(driver_files, monkeypatch):
    argv, policy, out = driver_files
    monkeypatch.setenv("REACTOR_ACCESS_KEY", KEY)
    with local_reactor() as server:
        monkeypatch.setattr(sys, "argv", argv + ["--base-url", server["base_url"], "--agent-id", "agt_test",
                                              "--max-questions", "1"])
        assert main() == 0
        assert len(server["calls"]) == 1
        policy.write_text(POLICY + "\nDifferent instructions.")
        assert main() == 1
        assert len(server["calls"]) == 1
        assert len(server["histories"]) == 1
    assert KEY not in (out / "manifest.json").read_text()
