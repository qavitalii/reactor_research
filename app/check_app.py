"""End-to-end check against the mock Reactor: python app/check_app.py (run from the repo root)."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1] / "pipeline"
APP = Path(__file__).resolve().parent
PORT = 8791
tmp = tempfile.mkdtemp(prefix="memchal-check-")
os.environ.update(REACTOR_LEASE_DIR=tmp, REACTOR_BASE_URL=f"http://127.0.0.1:{PORT}", REACTOR_AGENT_ID="agt_mock",
                  REACTOR_ACCESS_KEY="mock-key-not-a-real-credential")
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest

from memchal import service


def check(condition, message):
    print(("ok   " if condition else "FAIL ") + message, flush=True)
    if not condition:
        raise SystemExit(1)


def button(at, label):
    return next(b for b in at.button if b.label == label)


def parsing():
    text = service.parse_chat_text("chat-2024-03-05.txt", "user: My cat is Pepper.\nassistant: Nice!\nmore\nuser: Thanks")
    check([t["role"] for t in text["turns"]] == ["user", "assistant", "user"] and text["date"].startswith("2024/03/05 (Tue)"),
          "text export: roles and date from file name")
    plain = service.parse_chat_text("notes.md", "Just some words\nabout a trip")
    check(len(plain["turns"]) == 1 and plain["turns"][0]["role"] == "user", "plain text: one user turn")
    histories = service.parse_uploads([("b.txt", b"user: hi"), ("2020-01-02 a.txt", b"user: hello")])
    check(len(histories) == 1 and histories[0]["sessions"][0]["date"].startswith("2020/01/02"), "text files form one history, oldest first")
    try:
        service.parse_uploads([("x.jsonl", b"{not json")])
        check(False, "bad jsonl rejected")
    except ValueError as exc:
        check("line 1" in str(exc), "bad jsonl rejected with a friendly message")


def ui():
    at = AppTest.from_file(str(APP / "app.py"), default_timeout=300).run()
    check(not at.exception, "page renders")
    button(at, "Try the demo conversations").click().run()
    check(any("50 conversations" in s.value for s in at.success), "demo summary: " + at.success[0].value)
    button(at, "Prepare my conversations").click().run()
    check(not at.exception and at.session_state.indexes, "prepare builds the index")
    at.text_input[0].set_value("Where did I redeem a $5 coupon on coffee creamer?").run()
    button(at, "Get the answer").click().run()
    single = at.session_state.single
    check(not at.exception and single and not single["prediction"]["abstain"] and single["prediction"]["citations"],
          "single question answered with citations: " + single["prediction"]["answer"])
    check(any("Based on these conversations" in m.value for m in at.markdown), "answer card lists its sources")
    at.radio[0].set_value("Answer a list of questions").run()
    button(at, "Answer all questions").click().run()
    batch = at.session_state.batch
    check(not at.exception and len(batch) == 1, "batch of the demo questions answered")
    data = service.predictions_jsonl([r["prediction"] for r in batch])
    row = json.loads(data)
    check(set(row) == {"question_id", "abstain", "answer", "citations"} and row["question_id"] == "q_bdcc36b14f9a",
          "predictions.jsonl row: " + data.strip())
    return batch


def abstention():
    index = service.prepare(service.parse_uploads([("2024-01-01 pets.txt", b"user: My cat is Pepper.")]))["h_uploaded"]
    record = service.retrieve(index, "What is my hamster called?", "2024/02/01 (Thu) 09:00", "q_h")
    result = service.ask(record, service.reactor_settings())
    check(result["prediction"]["abstain"] and not result["prediction"]["citations"], "abstention is passed through")


if __name__ == "__main__":
    server = subprocess.Popen([sys.executable, str(APP / "mock_reactor.py"), str(PORT)], stdout=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", PORT), 0.2).close()
                break
            except OSError:
                time.sleep(0.2)
        parsing()
        ui()
        abstention()
        key = os.environ["REACTOR_ACCESS_KEY"]
        check(key not in "".join(p.read_text() for p in Path(tmp).glob("*.json")), "key is not written to the lease dir")
        print("all checks passed")
    finally:
        server.terminate()
