"""Prepared evidence (+ code-computed hint passages) -> official Reactor client -> validated, resumable predictions.

Variant of run_reactor.py for A/B experiments: a passage marked {"hint": true} has no source id, so Reactor
can read it but a citation of it maps to nothing and is dropped by the official converter.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time

from .audit import audit, read
from reactor import client
from reactor import predictions as official_predictions
from .lease import agent_lease
from .validate import validate

ROOT = Path(__file__).resolve().parents[1]  # the pipeline/ directory
REPAIR = "Your previous answer had missing or invalid citations. Answer again with valid [E#] labels from this evidence."
FORMAT_REPAIR = ("Your previous answer was not in the required form: give one value, with the unit the question asks "
                 "for, no alternatives, then the [E#] citations.")
UNIT_QUESTION = re.compile(r"\bhow many (days?|weeks?|months?|hours?|years?)\b", re.I)
RECHECK = ("Check again: if any excerpt is about the asked entity or event, answer from it. "
           "Answer INSUFFICIENT_EVIDENCE only if none is.")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_result(path, result):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def needs_format_repair(answer, question):
    """A bare alternative ("A or B") or a bare number for a "how many <unit>" question. Length and several numbers are fine."""
    if client._INSUFFICIENT.match(answer):
        return False
    value = official_predictions.strip_labels(answer)
    if re.search(r"\w\s+or\s+\w", value, re.I):
        return True
    # "Nell (previously Juniper)", "Amici (earlier statement booked Osteria)": two candidates in one line.
    if re.search(r"\((?:previously|earlier|formerly|before|originally|initially|renamed)\b|\b(?:previously|formerly) (?:named|called|known as)\b|\brenamed from\b", value, re.I):
        return True
    return bool(UNIT_QUESTION.search(question) and re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", value))


def format_request(record, instructions, ref, max_chars=16000, repair=False, recheck=False, format_repair=False):
    passages = []
    for p in record["passages"]:
        if p.get("hint"):
            passages.append({"id": None, "text": p["text"]})
            continue
        header, body = p["text"].split("\n", 1)
        if not header.startswith("Session date: "):
            raise ValueError("Evidence is missing its session date")
        # Move the date into the official source label instead of duplicating it.
        passages.append({"id": p["id"], "date": header.removeprefix("Session date: "), "text": body})
    if passages:
        passages = client.load_evidence(json.dumps(passages))
    date = client.parse_question_date(record["question_date"])
    policy = instructions.strip() + ("\n\n" + RECHECK if recheck else "") + ("\n\n" + REPAIR if repair else "")
    if format_repair:
        policy += "\n\n" + FORMAT_REPAIR
    message = policy + "\n\n" + client.build_message(record["question"], passages, ref, date)
    if len(message) > max_chars:
        raise ValueError(f"{record['question_id']}: serialized message is {len(message)} chars, limit {max_chars}")
    return message, passages, date


def preflight(split, records, instructions, max_chars):
    if not records:
        raise ValueError("No prepared requests")
    # Hints are not sources: audit the evidence passages only.
    integrity = audit(split, [{**r, "passages": [p for p in r["passages"] if not p.get("hint")]} for r in records],
                      allow_subset=True)
    normal, repair = [], []
    for r in records:
        normal.append(len(format_request(r, instructions, "1234abcd", max_chars)[0]))
        repair.append(len(format_request(r, instructions, "1234abcd", max_chars, repair=True, recheck=True)[0]))
    return {**integrity, "exact_reactor_serialization_checked": True,
            "max_message_chars": max(normal), "max_repair_message_chars": max(repair),
            "message_limit": max_chars, "reactor_histories_required": len({r["history_id"] for r in records})}


def checked_prediction(result, record):
    """Use the official converter, rejecting unsupported citations instead of silently dropping them."""
    if result.get("status") != "answered" or result.get("question_id") != record["question_id"]:
        raise ValueError("Not an answer for this question")
    answer = result.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Empty final answer")
    if client.final_answers(result.get("reply", "")).get(result.get("ref")) != answer:
        raise ValueError("Answer does not match its final-answer reference")
    passages = [{"id": p["id"], "text": p["text"]} for p in record["passages"]]
    cited, unknown = client.citations(answer, passages)
    abstained = bool(client._INSUFFICIENT.match(answer))
    if result.get("citations") != cited or result.get("abstained") != abstained:
        raise ValueError("Stored citation or abstention metadata does not match the reply")
    if not abstained and (unknown or not cited):
        raise ValueError("Factual answer has missing or unknown evidence citations")
    mapped, skipped, notes = official_predictions.convert([result], {"agent"}, {p["id"] for p in passages})
    # A cited hint has no id; the official converter leaves it out and says so. That is expected.
    hint_labels = {f"E{n}" for n, p in enumerate(record["passages"], 1) if p.get("hint")}
    notes = [n for n in notes if not any(f" {label} cites a passage you gave no id" in n for label in hint_labels)]
    if skipped or notes or len(mapped) != 1:
        raise ValueError("Official prediction conversion rejected the answer")
    errors = validate(mapped, [record], [{"history_id": record["history_id"],
                                        "sessions": [{"session_id": p["id"]} for p in passages]}])
    if errors:
        raise ValueError("; ".join(errors))
    return mapped[0]


def load_completed(path, records):
    by_id = {r["question_id"]: r for r in records}
    completed = {}
    if path.exists():
        for result in read(path):
            qid = result.get("question_id")
            if qid not in by_id or qid in completed:
                raise ValueError("Checkpoint contains unknown or duplicate questions")
            checked_prediction(result, by_id[qid])
            completed[qid] = result
    return completed


def execute(records, out, *, base_url, agent_id, access_key, instructions, timeout=300,
            max_chars=16000, max_questions=0, retry_abstain=False, history_per_question=False):
    """One history per dataset history, sequential questions, successful answers checkpointed immediately.

    With retry_abstain, an INSUFFICIENT_EVIDENCE answer is asked once more in the same history (RECHECK);
    the question is an abstention only when both answers are. A validated non-abstaining answer with a bare
    alternative or a missing unit is asked once more (FORMAT_REPAIR); the second answer is kept unless it
    abstains or fails validation, in which case the first answer stands."""
    results_path, attempts_path = out / "results.jsonl", out / "attempts.jsonl"
    completed = load_completed(results_path, records)
    if len(completed) != len(records) and (out / "predictions.jsonl").exists():
        raise ValueError("Predictions exist but their results are incomplete; use a fresh output directory")
    groups = defaultdict(list)
    for r in records:
        if r["question_id"] not in completed:
            # Every request carries its full evidence, so a fresh Reactor history per question is safe; it also
            # avoids the busy/previous_pending wait after each answer within one history (~40 s a question).
            groups[(r["history_id"], r["question_id"]) if history_per_question else r["history_id"]].append(r)
    asked = 0
    for key, questions in groups.items():
        dataset_history = key[0] if isinstance(key, tuple) else key
        if max_questions and asked >= max_questions:
            break
        # Like the official example, a resumed run creates a fresh history for
        # remaining questions. Every question carries its own full evidence.
        try:
            history = client.new_history(base_url, agent_id, access_key, timeout=timeout)
        except (OSError, ValueError) as exc:
            error = str(exc).replace(access_key, "[redacted]")
            append_result(attempts_path, {"status": "error", "stage": "new_history",
                                         "dataset_history_id": dataset_history, "error": error})
            raise RuntimeError(f"Could not start a Reactor history: {error}") from None
        history_id = history.get("history_id")
        if not isinstance(history_id, str) or not history_id:
            raise ValueError("Reactor returned no history_id")
        append_result(attempts_path, {"status": "history", "dataset_history_id": dataset_history, **history})
        for record in questions:
            if max_questions and asked >= max_questions:
                break
            attempt, transport_retries, recheck = 0, 0, False
            format_repaired, first = False, None
            while attempt < 2:
                ref = secrets.token_hex(4)
                message, passages, date = format_request(record, instructions, ref, max_chars, repair=attempt > 0,
                                                          recheck=recheck, format_repair=format_repaired)
                meta = {"question_id": record["question_id"], "question": record["question"],
                        "question_date": date, "dataset_history_id": dataset_history,
                        "history_id": history_id, "ref": ref, "message_chars": len(message),
                        "format_repair": format_repaired}
                try:
                    response, retries = client.ask_retrying(base_url, agent_id, access_key, message,
                                                           timeout=timeout, ref=ref, history=history_id)
                except (client.NoAnswer, OSError, ValueError) as exc:
                    status = ("timeout" if isinstance(exc, client.TimedOut) else
                              "refused" if isinstance(exc, client.Refused) else
                              "closed" if isinstance(exc, client.Closed) else "error")
                    error = str(exc).replace(access_key, "[redacted]")
                    diagnostic = {"other_replies": getattr(exc, "other_replies", []),
                                  "late_replies": getattr(exc, "late_replies", [])}
                    if isinstance(exc, client.Refused):
                        diagnostic.update(code=exc.code, forwarded=exc.forwarded)
                        diagnostic.update({"current_history_id" if k == "history_id" else k: v
                                           for k, v in exc.details.items()})
                    append_result(attempts_path, {**meta, "status": status, "error": error, **diagnostic,
                                                 "retries": getattr(exc, "retries", 0)})
                    # PARTICIPANTS.md: a closed chat is transient ("ask again"). Retry the same request a few
                    # times before giving up; a transport failure never becomes an evidence abstention.
                    if (status == "closed" and transport_retries < 3) or (status == "timeout" and transport_retries < 1):
                        transport_retries += 1
                        print(f"{record['question_id']}: {status}; retrying in 15 s ({transport_retries})", flush=True)
                        time.sleep(15)
                        continue
                    raise RuntimeError(f"{record['question_id']}: {status}; saved progress, rerun to resume") from None
                cited, unknown = client.citations(response["answer"], passages)
                result = {**meta, **response, "status": "answered", "retries": retries,
                          "citations": cited, "unknown_citations": unknown,
                          "uncited": bool(passages) and not cited,
                          "abstained": bool(client._INSUFFICIENT.match(response["answer"])), "rechecked": recheck}
                try:
                    checked_prediction(result, record)
                except ValueError as exc:
                    append_result(attempts_path, {**result, "validation_error": str(exc)})
                    if attempt == 1 and not format_repaired:
                        raise RuntimeError(f"{record['question_id']}: invalid answer after citation repair; saved progress") from None
                    if attempt == 1:
                        result = first
                    else:
                        attempt += 1
                        continue
                else:
                    append_result(attempts_path, result)
                    if format_repaired and result["abstained"]:
                        result = first
                if (not format_repaired and not result["abstained"]
                        and needs_format_repair(result["answer"], record["question"])):
                    print(f"{record['question_id']}: answer not in required form; asking once more", flush=True)
                    attempt, format_repaired, first = 0, True, result
                    continue
                if result["abstained"] and retry_abstain and not recheck:
                    print(f"{record['question_id']}: abstained; asking once more", flush=True)
                    attempt, recheck = 0, True
                    continue
                append_result(results_path, result)
                completed[record["question_id"]] = result
                asked += 1
                print(f"{len(completed)}/{len(records)}: {record['question_id']} "
                      f"{'abstained' if result['abstained'] else 'answered'}", flush=True)
                break
    complete = len(completed) == len(records)
    if complete:
        predictions = [checked_prediction(completed[r["question_id"]], r) for r in records]
        destination = out / "predictions.jsonl"
        tmp = destination.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in predictions), encoding="utf-8")
        tmp.replace(destination)
    receipt = {"complete": complete, "completed_questions": len(completed), "requested_questions": len(records),
               "new_answers": asked, "predictions_written": complete}
    write_json(out / "receipt.json", receipt)
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("split", type=Path)
    ap.add_argument("requests", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="validate actual official messages without credentials or network")
    ap.add_argument("--base-url", default=os.environ.get("REACTOR_BASE_URL"))
    ap.add_argument("--agent-id", default=os.environ.get("REACTOR_AGENT_ID"))
    ap.add_argument("--instructions", type=Path, default=ROOT / "instructions" / "reactor_instructions.txt")
    ap.add_argument("--timeout", type=float, default=client.DEFAULT_TIMEOUT)
    ap.add_argument("--max-chars", type=int, default=client.MAX_CHARS)
    ap.add_argument("--max-questions", type=int, default=0, help="stop after this many new answers; rerun to continue")
    ap.add_argument("--retry-abstain", action="store_true", help="ask once more before accepting INSUFFICIENT_EVIDENCE")
    ap.add_argument("--history-per-question", action="store_true", help="a fresh Reactor history for every question")
    args = ap.parse_args()
    if args.timeout <= 0 or args.max_chars <= 0 or args.max_questions < 0:
        ap.error("timeout and max-chars must be positive; max-questions must be nonnegative")
    try:
        records = list(read(args.requests))
        instructions = args.instructions.read_text(encoding="utf-8").strip()
        report = preflight(args.split, records, instructions, args.max_chars)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / "preflight.json", report)
        if args.dry_run:
            print(json.dumps(report, indent=2))
            return 0
        key = os.environ.get("REACTOR_ACCESS_KEY", "")
        if not args.base_url or not args.agent_id or not key:
            raise ValueError("Set REACTOR_BASE_URL, REACTOR_AGENT_ID and REACTOR_ACCESS_KEY (key only via environment)")
        problem = client.environment_problem()
        if problem:
            raise ValueError(problem)
        client._base(args.base_url, ws=False)
        manifest = {"requests_sha256": digest(args.requests.read_bytes()),
                    "instructions_sha256": digest(instructions.encode()), "max_chars": args.max_chars,
                    "base_url": args.base_url.rstrip("/"), "agent_id": args.agent_id,
                    "retry_abstain": args.retry_abstain, "history_per_question": args.history_per_question,
                    "runtime_sha256": {name: digest((ROOT / name).read_bytes()) for name in
                                       ["memchal/runner.py", "memchal/hints.py", "memchal/audit.py", "memchal/validate.py",
                                        "reactor/client.py", "reactor/predictions.py", "memchal/lease.py"]}}
        manifest_path = args.output_dir / "manifest.json"
        if manifest_path.exists():
            if json.loads(manifest_path.read_text()) != manifest:
                raise ValueError("Run inputs, endpoint or client changed; use a fresh output directory")
        else:
            if (args.output_dir / "results.jsonl").exists():
                raise ValueError("Existing results have no provenance manifest; use a fresh output directory")
            write_json(manifest_path, manifest)
        with agent_lease(args.agent_id):
            receipt = execute(records, args.output_dir, base_url=args.base_url, agent_id=args.agent_id,
                              access_key=key, instructions=instructions, timeout=args.timeout,
                              max_chars=args.max_chars, max_questions=args.max_questions,
                              retry_abstain=args.retry_abstain, history_per_question=args.history_per_question)
        print(json.dumps(receipt, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        key = os.environ.get("REACTOR_ACCESS_KEY", "")
        message = str(exc).replace(key, "[redacted]") if key else str(exc)
        print(f"error: {message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
