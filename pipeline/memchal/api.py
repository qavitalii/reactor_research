"""HTTP API over memchal.service for the web UI: python -m uvicorn memchal.api:app --port 8787 (from pipeline/).

State lives in memory. Reactor credentials come from the REACTOR_* environment only and are never returned.
"""
from __future__ import annotations

from datetime import datetime, time as dtime
from pathlib import Path
import threading
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import service

APP_DIR = Path(__file__).resolve().parents[2] / "app"
MAX_UPLOAD = 50 * 1024 * 1024
NO_REACTOR = ("Reactor is not connected, so questions cannot be answered yet. "
              "Ask whoever runs this app to set it up (see app/API.md).")

app = FastAPI(title="Ask your conversations", docs_url="/api/docs", openapi_url="/api/openapi.json")
collections: dict[str, dict] = {}
jobs: dict[str, dict] = {}


class Question(BaseModel):
    question: str
    question_date: str | None = None
    history_id: str | None = None


def day(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def get_collection(collection_id: str) -> dict:
    if collection_id not in collections:
        raise HTTPException(404, "Those conversations were not found. Please add them again.")
    return collections[collection_id]


def need_settings() -> dict:
    settings = service.reactor_settings()
    if not settings:
        raise HTTPException(503, NO_REACTOR)
    return settings


def need_ready(collection: dict) -> dict:
    if collection["state"] != "ready":
        raise HTTPException(409, "Please prepare your conversations first.")
    return collection["indexes"]


def newest(collection: dict) -> datetime:
    return collection["summary"]["last"]


def as_question_date(value: str | None, collection: dict) -> str:
    """'YYYY-MM-DD' (end of that day) or the challenge format; default is the newest conversation's day."""
    if not value:
        return service.format_date(datetime.combine(newest(collection).date(), dtime(23, 59)))
    try:
        return service.format_date(datetime.combine(datetime.strptime(value, "%Y-%m-%d").date(), dtime(23, 59)))
    except ValueError:
        pass
    try:
        service.parse_date(value)
    except ValueError:
        raise HTTPException(422, "The date should look like 2023-05-30.") from None
    return value


def pick_history(indexes: dict, history_id: str | None):
    if history_id in indexes:
        return indexes[history_id]
    if history_id and len(indexes) > 1:
        raise HTTPException(422, f"Unknown collection {history_id}.")
    return next(iter(indexes.values()))


def answer_one(index, question: str, question_date: str, question_id: str, settings: dict) -> dict:
    """Retrieve excerpts, ask Reactor, return the API shape of one answer."""
    try:
        record = service.retrieve(index, question, question_date, question_id)
        result = service.ask(record, settings)
    except RuntimeError as exc:
        raise HTTPException(502, f"Sorry, no answer this time: {exc}") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    prediction, found = result["prediction"], service.excerpts(record)
    citations = [{"session_id": c, "date": found[c]["date"], "excerpt": found[c]["text"]}
                 for c in prediction["citations"] if c in found]
    return {"prediction": prediction, "view": {
        "question_id": question_id, "question": question, "answer": prediction["answer"],
        "abstain": prediction["abstain"], "citations": citations, "latency_s": round(result["seconds"], 1)}}


@app.get("/health")
def health():
    return {"ok": True, "reactor_configured": service.reactor_settings() is not None}


@app.post("/collections")
def add_collection(files: list[UploadFile] = File(default=[]), demo: int = 0):
    try:
        if demo:
            histories = service.parse_histories_jsonl((APP_DIR / "demo" / "histories.jsonl").read_bytes())
        else:
            uploads = []
            for f in files:
                data = f.file.read(MAX_UPLOAD + 1)
                if len(data) > MAX_UPLOAD:
                    raise ValueError("that file is too large")
                uploads.append((f.filename or "upload.txt", data))
            histories = service.parse_uploads(uploads)
    except ValueError as exc:
        raise HTTPException(422, f"Sorry, that file could not be read: {exc}.") from None
    summary = service.summarize(histories)
    collection_id = "c_" + uuid.uuid4().hex[:10]
    collections[collection_id] = {"histories": histories, "summary": summary, "state": "pending",
                                  "progress": 0.0, "message": "Not prepared yet.", "indexes": None}
    return {"collection_id": collection_id, "conversations": summary["conversations"],
            "messages": summary["messages"], "date_from": day(summary["first"]), "date_to": day(summary["last"])}


def run_prepare(collection: dict) -> None:
    def progress(fraction, message):
        collection.update(progress=round(min(fraction, 1.0), 3), message=message)

    try:
        collection["indexes"] = service.prepare(collection["histories"], progress)
        collection.update(state="ready", progress=1.0, message="Your conversations are ready to be searched.")
    except Exception as exc:
        collection.update(state="error", message=f"Sorry, preparing failed: {exc}")


@app.post("/collections/{collection_id}/prepare")
def prepare(collection_id: str):
    collection = get_collection(collection_id)
    if collection["state"] in ("pending", "error"):
        collection.update(state="preparing", progress=0.0, message="Starting…")
        threading.Thread(target=run_prepare, args=(collection,), daemon=True).start()
    return {"state": collection["state"]}


@app.get("/collections/{collection_id}/status")
def status(collection_id: str):
    c = get_collection(collection_id)
    return {"state": c["state"], "progress": c["progress"], "message": c["message"]}


@app.post("/collections/{collection_id}/ask")
def ask(collection_id: str, body: Question):
    collection = get_collection(collection_id)
    settings = need_settings()
    indexes = need_ready(collection)
    if not body.question.strip():
        raise HTTPException(422, "Please type a question.")
    return answer_one(pick_history(indexes, body.history_id), body.question.strip(),
                      as_question_date(body.question_date, collection), "q_" + uuid.uuid4().hex[:12], settings)["view"]


def run_batch(job: dict, collection: dict, questions: list[dict], settings: dict) -> None:
    indexes = collection["indexes"]
    for q in questions:
        try:
            out = answer_one(pick_history(indexes, q["history_id"]), q["question"], q["question_date"],
                             q["question_id"], settings)
        except HTTPException as exc:
            job.update(state="error", message=f"Stopped at question {len(job['results']) + 1}: {exc.detail}")
            return
        job["predictions"].append(out["prediction"])
        job["results"].append(out["view"])
    job["state"] = "done"


@app.post("/collections/{collection_id}/batch")
def batch(collection_id: str, file: UploadFile = File(...)):
    collection = get_collection(collection_id)
    settings = need_settings()
    indexes = need_ready(collection)
    try:
        questions = service.parse_questions(file.file.read(MAX_UPLOAD))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, f"Sorry, that file could not be read: {exc}.") from None
    if len(indexes) == 1:
        only = next(iter(indexes))
        questions = [q if q["history_id"] in indexes else {**q, "history_id": only} for q in questions]
    missing = [q["question_id"] for q in questions if q["history_id"] not in indexes]
    if missing:
        raise HTTPException(422, "These questions belong to conversations you have not added: "
                                 + ", ".join(missing[:5]) + ".")
    job_id = "j_" + uuid.uuid4().hex[:10]
    job = {"state": "running", "total": len(questions), "results": [], "predictions": [], "message": ""}
    jobs[job_id] = job
    threading.Thread(target=run_batch, args=(job, collection, questions, settings), daemon=True).start()
    return {"job_id": job_id}


def get_job(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(404, "That batch was not found.")
    return jobs[job_id]


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    results = list(job["results"])
    return {"done": job["state"] == "done", "total": job["total"], "answered": len(results),
            "state": job["state"], "message": job["message"], "results": results}


@app.get("/jobs/{job_id}/predictions.jsonl")
def job_predictions(job_id: str):
    job = get_job(job_id)
    return PlainTextResponse(service.predictions_jsonl(list(job["predictions"])), media_type="application/jsonl",
                             headers={"Content-Disposition": 'attachment; filename="predictions.jsonl"'})


app.mount("/", StaticFiles(directory=APP_DIR / "web", html=True), name="web")
