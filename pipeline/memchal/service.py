"""Glue for the demo app: parse uploads, build the search index, retrieve excerpts and ask Reactor.

Everything here is plain Python (no Streamlit), so it can be driven from tests and scripts.
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import threading
import time

import numpy as np

from .finalize import finalize
from .hints import with_hints
from .lease import agent_lease
from .retrieval import DATE_FORMAT, HistoryIndex, Reranker, SemanticSearch, needs_coverage
from .runner import ROOT, checked_prediction, execute

BUDGET = 14500
MAX_CHARS = 17500  # the budget plus room for the timeline hint
CACHE_DIR = os.environ.get("MEMCHAL_CACHE_DIR", str(ROOT / ".cache"))
INSTRUCTIONS = ROOT / "instructions" / "reactor_instructions.txt"
ROLES = {"user": "user", "you": "user", "me": "user", "human": "user",
         "assistant": "assistant", "ai": "assistant", "bot": "assistant", "chatgpt": "assistant", "claude": "assistant"}
ROLE_LINE = re.compile(r"^\s*(%s)\s*:\s*(.*)$" % "|".join(ROLES), re.I)
FILE_DATE = re.compile(r"(?<!\d)(\d{4})[-_/.]?(\d{2})[-_/.]?(\d{2})(?!\d)")

_models = {}
_models_lock = threading.Lock()
work_lock = threading.Lock()  # retrieval models and the Reactor agent serve one request at a time


def format_date(when: datetime) -> str:
    return when.strftime(DATE_FORMAT)


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, DATE_FORMAT)


def _clean_history(raw: dict, line: int) -> dict:
    where = f"line {line}"
    try:
        sessions = []
        for s in raw["sessions"]:
            turns = [{"turn_id": str(t["turn_id"]), "role": t["role"], "content": t["content"]} for t in s["turns"]
                     if isinstance(t["content"], str) and t["content"].strip()]
            if any(t["role"] not in ("user", "assistant") for t in turns):
                raise ValueError("a message has a role other than user or assistant")
            if turns:
                sessions.append({"session_id": str(s["session_id"]), "date": s["date"], "turns": turns})
        history = {"history_id": str(raw["history_id"]), "sessions": sessions}
        for s in sessions:
            parse_date(s["date"])
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"{where}: missing or malformed field {exc}") from None
    except ValueError as exc:
        raise ValueError(f"{where}: {exc}") from None
    if not sessions:
        raise ValueError(f"{where}: no conversations with text")
    history["sessions"].sort(key=lambda s: parse_date(s["date"]))
    return history


def parse_histories_jsonl(data: bytes) -> list[dict]:
    histories = []
    for n, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                raw = json.loads(line)
            except ValueError:
                raise ValueError(f"line {n} is not valid JSON") from None
            histories.append(_clean_history(raw, n))
    if not histories:
        raise ValueError("the file is empty")
    return histories


def date_from_text(name: str, text: str) -> datetime:
    """A date in the file name or its first lines, else today (noon)."""
    head = name + "\n" + "\n".join(text.splitlines()[:5])
    for m in FILE_DATE.finditer(head):
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3]), 12, 0)
        except ValueError:
            continue
    today = date.today()
    return datetime(today.year, today.month, today.day, 12, 0)


def parse_chat_text(name: str, text: str) -> dict:
    """One plain-text chat export -> one session; 'user:'/'assistant:' lines become turns."""
    lines = text.splitlines()
    turns = []
    if any(ROLE_LINE.match(l) for l in lines):
        for line in lines:
            m = ROLE_LINE.match(line)
            if m:
                turns.append({"role": ROLES[m[1].lower()], "content": m[2]})
            elif turns:
                turns[-1]["content"] += "\n" + line
        turns = [{**t, "content": t["content"].strip()} for t in turns if t["content"].strip()]
    elif text.strip():
        turns = [{"role": "user", "content": text.strip()}]
    if not turns:
        raise ValueError(f"{name} has no text")
    digest = hashlib.sha256(text.encode()).hexdigest()[:10]
    return {"session_id": f"s_{digest}", "date": format_date(date_from_text(name, text)),
            "turns": [{"turn_id": f"t_{digest}_{i}", **t} for i, t in enumerate(turns)]}


def parse_uploads(files: list[tuple[str, bytes]]) -> list[dict]:
    """Uploaded (name, bytes) pairs -> histories. A .jsonl is in the challenge format; text files form one history."""
    histories, sessions = [], []
    for name, data in files:
        if name.lower().endswith((".jsonl", ".json")):
            histories += parse_histories_jsonl(data)
        else:
            sessions.append(parse_chat_text(name, data.decode("utf-8", errors="replace")))
    if sessions:
        sessions.sort(key=lambda s: parse_date(s["date"]))
        histories.append({"history_id": "h_uploaded", "sessions": sessions})
    if not histories:
        raise ValueError("no files to read")
    return histories


def parse_questions(data: bytes) -> list[dict]:
    questions = []
    for n, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            q = json.loads(line)
            item = {k: str(q[k]) for k in ("question_id", "history_id", "question", "question_date")}
            parse_date(item["question_date"])
        except (ValueError, KeyError, TypeError):
            raise ValueError(f"line {n}: each question needs question_id, history_id, question and a "
                             "question_date like 2023/05/30 (Tue) 08:08") from None
        questions.append(item)
    if not questions:
        raise ValueError("the file is empty")
    if len({q["question_id"] for q in questions}) != len(questions):
        raise ValueError("question_id values must be unique")
    return questions


def summarize(histories: list[dict]) -> dict:
    sessions = [s for h in histories for s in h["sessions"]]
    dates = [parse_date(s["date"]) for s in sessions]
    return {"collections": len(histories), "conversations": len(sessions),
            "messages": sum(len(s["turns"]) for s in sessions), "first": min(dates), "last": max(dates)}


def get_models(progress=lambda fraction, message: None):
    """The reranker and embedding model, loaded once (they download on first use)."""
    with _models_lock:
        if not _models:
            Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
            progress(0.0, "Getting the search tools ready (the first time this downloads about 150 MB)…")
            _models["reranker"] = Reranker(CACHE_DIR)
            semantic = SemanticSearch(CACHE_DIR)
            # Streamlit reruns the script on different threads; the vector cache must be usable from all of them.
            semantic.db.close()
            semantic.db = sqlite3.connect(Path(CACHE_DIR) / "embeddings.sqlite", check_same_thread=False)
            _models["semantic"] = semantic
        return _models["reranker"], _models["semantic"]


def prepare(histories: list[dict], progress=lambda fraction, message: None) -> dict[str, HistoryIndex]:
    """Index every history; progress(fraction, plain-language status) is called along the way."""
    with work_lock:
        reranker, semantic = get_models(lambda f, m: progress(0.1 * f, m))
        total = sum(len(h["sessions"]) for h in histories)
        done, indexes = 0, {}
        for h in histories:
            progress(0.1 + 0.9 * done / total, "Reading conversations…")
            index = HistoryIndex(h)
            texts = [semantic.session_text(s) for s in index.sessions]
            vectors = []
            for start in range(0, len(texts), 8):
                progress(0.1 + 0.9 * (done + start) / total,
                         f"Learning what each conversation is about… ({done + start} of {total})")
                vectors.append(semantic.encode(texts[start:start + 8]))
            index.semantic_vectors = np.concatenate(vectors)
            indexes[h["history_id"]] = index
            done += len(texts)
        progress(1.0, "Ready.")
        return indexes


def retrieve(index: HistoryIndex, question: str, question_date: str, question_id: str) -> dict:
    """The request record Reactor will see: dated excerpts (plus a timeline hint for time questions)."""
    parse_date(question_date)
    with work_lock:
        reranker, semantic = get_models()
        ranked, scores = index.rank(question, question_date, reranker, 72, semantic)
        coverage = needs_coverage(question)
        passages = index.pack(question, question_date, ranked, scores, BUDGET, 12 if coverage else 6, 4500, coverage)
    chars = sum(len(p["text"]) + 80 for p in passages) + len(question) + len(question_date)
    if chars > BUDGET:
        raise ValueError(f"Excerpts are too long ({chars} characters)")
    return with_hints({"question_id": question_id, "history_id": index.history_id, "question": question,
                       "question_date": question_date, "passages": passages})


def reactor_settings() -> dict | None:
    """Credentials from the environment only; None when any is missing."""
    s = {"base_url": os.environ.get("REACTOR_BASE_URL", ""), "agent_id": os.environ.get("REACTOR_AGENT_ID", ""),
         "access_key": os.environ.get("REACTOR_ACCESS_KEY", "")}
    return s if all(s.values()) else None


def excerpts(record: dict) -> dict[str, dict]:
    """Cited-source details by session id: its date and the exact excerpt that was sent."""
    found = {}
    for p in record["passages"]:
        if not p.get("hint"):
            header, body = p["text"].split("\n", 1)
            found[p["id"]] = {"session_id": p["id"], "date": header.removeprefix("Session date: "), "text": body}
    return found


def ask(record: dict, settings: dict) -> dict:
    """Ask Reactor one question. Returns {prediction, record, seconds}; raises RuntimeError with a plain message."""
    instructions = INSTRUCTIONS.read_text(encoding="utf-8")
    out = Path(tempfile.mkdtemp(prefix="memchal-app-"))
    started = time.monotonic()
    try:
        with work_lock, agent_lease(settings["agent_id"]):
            execute([record], out, base_url=settings["base_url"], agent_id=settings["agent_id"],
                    access_key=settings["access_key"], instructions=instructions, max_chars=MAX_CHARS)
        result = json.loads((out / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
        prediction = finalize(checked_prediction(result, record), record["question"])
    except RuntimeError as exc:
        raise RuntimeError(str(exc).replace(settings["access_key"], "[redacted]")) from None
    except (OSError, ValueError, IndexError) as exc:
        raise RuntimeError(f"Reactor did not return a usable answer ({str(exc).replace(settings['access_key'], '[redacted]')})") from None
    finally:
        shutil.rmtree(out, ignore_errors=True)
    return {"prediction": prediction, "record": record, "seconds": time.monotonic() - started}


def predictions_jsonl(predictions: list[dict]) -> str:
    return "".join(json.dumps({k: p[k] for k in ("question_id", "abstain", "answer", "citations")},
                              ensure_ascii=False) + "\n" for p in predictions)
