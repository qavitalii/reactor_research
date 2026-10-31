"""Stand-in for Reactor so the demo runs without credentials: python app/mock_reactor.py [port].

It speaks the same HTTP + WebSocket protocol, cites the first excerpt and always answers with a fixed sentence
(or abstains when the message has no evidence, or asks about a hamster). Its answers are NOT real.
"""
import asyncio
import re
import sys

from aiohttp import web

KEY = "mock-key-not-a-real-credential"
AGENT = "agt_mock"
DELAY = 2.0
histories = []


async def new_history(request):
    if request.headers.get("Authorization") != "Bearer " + KEY:
        raise web.HTTPForbidden()
    histories.append(f"history-{len(histories) + 1}")
    return web.json_response({"history_id": histories[-1], "running": True})


async def chat(request):
    if request.headers.get("Authorization") != "Bearer " + KEY:
        raise web.HTTPForbidden()
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    text = (await ws.receive_json())["text"]
    ref = re.search(r"\[ref:([0-9a-f]{8})\] Question:", text).group(1)
    await ws.send_json({"type": "ack", "text": text, "cycle": 1})
    await asyncio.sleep(DELAY)
    abstain = "Evidence:" not in text or "hamster" in re.search(r"Question: (.*)", text).group(1).lower()
    answer = "INSUFFICIENT_EVIDENCE" if abstain else "This is a mock answer, taken from the first excerpt [E1]"
    await ws.send_json({"type": "reply", "text": f"# FINAL ANSWER [ref:{ref}]: {answer}", "cycle": 2})
    await ws.close()
    return ws


def main(port):
    app = web.Application()
    app.router.add_post("/agents/{agent}/history", new_history)
    app.router.add_get("/agents/{agent}/ws/chat", chat)
    print("Mock Reactor on http://127.0.0.1:%d. In another terminal, before starting the app, run:" % port)
    print(f"  export REACTOR_BASE_URL=http://127.0.0.1:{port}")
    print(f"  export REACTOR_AGENT_ID={AGENT}")
    print(f"  export REACTOR_ACCESS_KEY={KEY}", flush=True)
    web.run_app(app, host="127.0.0.1", port=port, print=None)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
