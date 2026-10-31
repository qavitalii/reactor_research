"""Deterministic hints for Reactor, computed by code from the prepared evidence only.

A hint is an extra passage without a source id (so it cannot become a citation). It restates the
session dates of the excerpts as a day-number timeline, so that durations become a subtraction of
two small integers instead of calendar arithmetic, and names the most recent excerpt. For counting
questions a second hint lists, per excerpt, the sentences that mention the asked thing, so Reactor
counts from an enumerated list instead of scanning prose. Gold answers, question types and retrieval
internals are never read here. A third hint flags excerpts where the asked thing is attributed to someone
other than the user ("my sister's cat", "Bjørn's beehives").
"""
from __future__ import annotations

from datetime import datetime
import re

DATE_FORMAT = "%Y/%m/%d (%a) %H:%M"
TEMPORAL = re.compile(r"\b(how (many|much) (days?|weeks?|months?|years?|hours?|time)|how long|days? (ago|apart|before|after|between|later|earlier)"
                      r"|weeks? (ago|apart|before|after|between|later|earlier)|months? (ago|apart|before|after|between|later|earlier)"
                      r"|ago|since|until|first|last|earliest|latest|most recent|recently|order|sequence|before|after|between|when did)\b", re.I)
COUNT = re.compile(r"\b(how many|how much|total|combined|altogether)\b", re.I)
COUNT_STOP = {"how", "many", "much", "total", "combined", "altogether", "times", "time", "did", "do", "does", "have",
              "has", "had", "since", "past", "last", "ago", "month", "months", "week", "weeks", "year", "years", "day",
              "days", "different", "number", "far", "spent", "spend", "far", "new", "got", "get", "bought", "buy",
              "went", "go", "make", "made", "taken", "take", "took", "used", "use", "visited", "visit", "attended",
              "attend", "mention", "mentioned", "including", "include", "various", "kind", "kinds", "type", "types"}
UPDATE = re.compile(r"\b(now|current(ly)?|right now|these days|at the moment|so far|still|latest|most recent|recent|new|updated?|changed?|moved|anymore|last time)\b", re.I)


def wants_timeline(question: str) -> bool:
    return bool(TEMPORAL.search(question) or UPDATE.search(question))


def passage_date(text: str) -> datetime:
    header = text.split("\n", 1)[0]
    if not header.startswith("Session date: "):
        raise ValueError("Evidence is missing its session date header")
    return datetime.strptime(header.removeprefix("Session date: "), DATE_FORMAT)


def timeline_hint(record: dict) -> dict | None:
    """One hint passage for the record's excerpts, or None when the question does not need it."""
    passages = record["passages"]
    if not passages or not wants_timeline(record["question"]):
        return None
    dates = [passage_date(p["text"]) for p in passages]
    asked = datetime.strptime(record["question_date"], DATE_FORMAT)
    origin = min(dates).date()
    lines = ["Note computed by code from the session dates above (do not cite this note; cite the excerpts it refers to).",
             "Day numbers count from the earliest excerpt; days between two excerpts = difference of their day numbers:"]
    for n, (p, d) in enumerate(zip(passages, dates), 1):
        lines.append(f"[E{n}] {d:%Y-%m-%d} ({d:%a}) = day {(d.date() - origin).days}")
    latest = max(range(len(dates)), key=lambda i: (dates[i], i)) + 1
    lines.append(f"Question date {asked:%Y-%m-%d} ({asked:%a}) = day {(asked.date() - origin).days}; "
                 f"[E{latest}] is the most recent retrieved session. That does not establish the latest value "
                 "of the requested fact. Use the latest applicable explicit update about the same entity/event. "
                 "These numbers describe session dates, not event dates; use them for an event only when "
                 "the source explicitly establishes that the event occurred on the session date.")
    return {"id": None, "text": "\n".join(lines), "hint": True}


def _stem():
    import snowballstemmer
    return snowballstemmer.stemmer("english").stemWord


def key_stems(question: str) -> set[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    stem = _stem()
    words = re.findall(r"[a-z][a-z'-]+", question.lower())
    return {stem(w.strip("'-")) for w in words if w not in ENGLISH_STOP_WORDS and w not in COUNT_STOP and len(w) > 2}


def count_hint(record: dict, max_chars: int = 1600) -> dict | None:
    """Per excerpt, the sentences that mention the asked thing (user turns first), dated; None when not a count question."""
    question = record["question"]
    if not COUNT.search(question) or not record["passages"]:
        return None
    stems = key_stems(question)
    if not stems:
        return None
    stem = _stem()
    lines = ["Mentions found by code (do not cite this note; cite the excerpts). Count distinct events that match the",
             "question; a plan, a cancelled event or a repeated mention of the same event is not another event:"]
    budget = max_chars - sum(len(l) + 1 for l in lines)
    for n, p in enumerate(record["passages"], 1):
        if p.get("hint"):
            continue
        date = passage_date(p["text"]).strftime("%Y-%m-%d")
        found = []
        for line in p["text"].split("\n")[1:]:
            m = re.match(r"(user|assistant) \(t_[0-9a-f]+\): (.*)", line)
            if not m:
                continue
            role, content = m.group(1), m.group(2)
            for sentence in re.split(r"(?<=[.!?])\s+", content):
                words = {stem(w) for w in re.findall(r"[a-z][a-z'-]+", sentence.lower())}
                if words & stems:
                    found.append((0 if role == "user" else 1, role, sentence.strip()))
        found.sort(key=lambda f: f[0])
        for _, role, sentence in found[:3]:
            text = sentence if len(sentence) <= 160 else sentence[:157] + "..."
            entry = f"[E{n}] {date} ({role}): {text}"
            if len(entry) + 1 > budget:
                break
            lines.append(entry)
            budget -= len(entry) + 1
    if len(lines) == 2:
        return None
    return {"id": None, "text": "\n".join(lines), "hint": True}


RELATIONS = ("sister brother neighbor neighbour daughter son friend mother mom father dad wife husband cousin aunt uncle "
             "colleague coworker roommate partner girlfriend boyfriend grandmother grandfather grandma grandpa niece nephew "
             "boss teacher").split()
RELATION = "|".join(RELATIONS)
# "my sister's cat", "my neighbor has a ...", "for my daughter", "Bjørn's beehives"
RELATION_CUE = re.compile(rf"\b(?:my|your)\s+({RELATION})(?:[’']s)?\s+(?:(?:has|have|keeps|owns|got)\s+)?(?:(?:a|an|the|new|old)\s+)?([a-z][\w-]*(?:\s+[a-z][\w-]*)?)", re.I)
FOR_CUE = re.compile(rf"\bfor\s+my\s+({RELATION})\b(.{{0,40}})", re.I)
NAME_CUE = re.compile(r"\b([A-Z][^\W\d_]+)[’']s\s+([a-z][\w-]*(?:\s+[a-z][\w-]*)?)")
ASKS_ABOUT_OTHER = re.compile(rf"\b(?:[A-Z][^\W\d_]+[’']s|her|his|their|(?:my|your)\s+(?:{RELATION})s?)\b")
# Possessives that are not people (sentence starts, contractions, "assistant's"/"user's").
NOT_NAMES = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "today", "yesterday", "tomorrow",
             "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
             "december", "christmas", "easter", "thanksgiving", "halloween", "valentine", "year", "week", "weekend", "month",
             "it", "that", "there", "here", "what", "who", "let", "he", "she", "where", "how", "when", "why", "this",
             "user", "assistant", "today", "tomorrow", "yesterday"}


def _cues(sentence: str):
    """(phrase shown, words matched against the question) for one sentence; the user's own things yield nothing."""
    for m in RELATION_CUE.finditer(sentence):
        yield f"the {m[1].lower()}'s {m[2].lower()}", m[2]
    for m in FOR_CUE.finditer(sentence):
        yield f"something for the {m[1].lower()}", sentence
    for m in NAME_CUE.finditer(sentence):
        if m[1].lower() not in NOT_NAMES:
            yield f"{m[1]}'s {m[2].lower()}", m[2]


def ownership_hint(record: dict, max_chars: int = 600) -> dict | None:
    """Excerpts where the asked thing belongs to someone other than the user; None when there are none."""
    stems = key_stems(record["question"])
    if not stems or ASKS_ABOUT_OTHER.search(record["question"]):
        return None
    stem = _stem()
    lines = ["Ownership cues found by code (do not cite this note):"]
    budget = max_chars - len(lines[0]) - 130
    entries = []
    for n, p in enumerate(record["passages"], 1):
        if p.get("hint"):
            continue
        date = passage_date(p["text"]).strftime("%Y-%m-%d")
        owners: dict[str, None] = {}
        for line in p["text"].split("\n")[1:]:
            m = re.match(r"(user|assistant) \(t_[0-9a-f]+\): (.*)", line)
            if not m or m.group(1) != "user":
                continue
            for sentence in re.split(r"(?<=[.!?])\s+", m.group(2)):
                for phrase, words in _cues(sentence):
                    if {stem(w) for w in re.findall(r"[a-z][a-z'-]+", words.lower())} & stems:
                        owners[phrase] = None
        if owners:
            entry = f"[E{n}] {date} mentions " + ", ".join(list(owners)[:2]) + " (not the user's)"
            if len(entry) + 2 > budget:
                break
            entries.append(entry)
            budget -= len(entry) + 2
    if not entries:
        return None
    text = lines[0] + " " + "; ".join(entries) + ". The question is about the user's own things unless it names someone else."
    return {"id": None, "text": text, "hint": True}


def with_hints(record: dict, counts: bool = True) -> dict:
    hints = [h for h in (timeline_hint(record), count_hint(record) if counts else None, ownership_hint(record)) if h]
    if not hints:
        return record
    return {**record, "passages": [*record["passages"], *hints]}


if __name__ == "__main__":
    import argparse, json, sys
    ap = argparse.ArgumentParser(description="prepared requests.jsonl -> requests with hint passages")
    ap.add_argument("requests"); ap.add_argument("output")
    ap.add_argument("--no-counts", action="store_true", help="timeline hints only")
    args = ap.parse_args()
    n = added = 0
    with open(args.requests, encoding="utf-8") as f, open(args.output, "w", encoding="utf-8") as out:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            hinted = with_hints(record, counts=not args.no_counts)
            added += len(hinted["passages"]) != len(record["passages"])
            out.write(json.dumps(hinted, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} requests written, {added} with hints", file=sys.stderr)
