"""Date-window coverage for counting questions: one short verbatim span from EVERY session inside a named
calendar window that mentions the question's entity. Pure and deterministic; no models, gold or question types."""
import calendar
from datetime import datetime, timedelta
import re

from .retrieval import DATE_FORMAT, needs_coverage, tokens

MONTHS = {name.lower(): n for n in range(1, 13) for name in (calendar.month_name[n], calendar.month_abbr[n])}
MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
NUMBERS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
# Query grammar, not entity vocabulary.
NOISE = set(tokens(" ".join(MONTHS) + " number times time month year week day days past last this since between "
                   "from during throughout total combined altogether overall far recently currently ago did done does have has had get got been"))
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _month_end(year, month):
    return datetime(year + (month == 12), month % 12 + 1, 1) - timedelta(microseconds=1)


def _shift_months(date, months):
    month = date.year * 12 + date.month - 1 - months
    year, month = divmod(month, 12)
    day = min(date.day, calendar.monthrange(year, month + 1)[1])
    return date.replace(year=year, month=month + 1, day=day)


def _latest_month(month, asked):
    """Unqualified month names mean the latest such month not after the question date."""
    return asked.year - (month > asked.month)


def count_window(question, question_date):
    """(start, end) of the calendar window a counting question names, resolved against question_date; else None."""
    if not needs_coverage(question):
        return None
    asked = datetime.strptime(question_date, DATE_FORMAT)
    m = re.search(rf"\bbetween\s+({MONTH})\b(?:\s+(\d{{4}}))?\s+and\s+({MONTH})\b(?:\s+(\d{{4}}))?", question, re.I)
    if m:
        a, ay, b, by = MONTHS[m[1].lower()], m[2], MONTHS[m[3].lower()], m[4]
        by = int(by) if by else (int(ay) if ay and a <= b else _latest_month(b, asked))
        ay = int(ay) if ay else by - (a > b)
        return datetime(ay, a, 1), min(_month_end(by, b), asked)
    m = re.search(rf"\b(since|from|in|during|throughout)\s+(?:the (?:start|beginning) of\s+)?({MONTH})\b"
                  rf"(?:\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?!\d))?(?:,?\s+(\d{{4}})\b)?", question, re.I)
    if m:
        mode, month, day, year = m.groups()
        month = MONTHS[month.lower()]
        year = int(year) if year else _latest_month(month, asked)
        try:
            start = datetime(year, month, int(day or 1))
        except ValueError:
            return None
        end = asked if mode.lower() in {"since", "from"} else _month_end(year, month)
        return start, min(end, asked)
    m = re.search(r"\b(?:since|from)\s+(\d{4}-\d{2}-\d{2})\b", question, re.I)
    if m:
        try:
            return datetime.fromisoformat(m[1]), asked
        except ValueError:
            return None
    m = re.search(r"\b(?:the\s+)?(?:past|last)\s+(\d+|" + "|".join(NUMBERS) + r"|a|an)?\s*(day|week|month|year)s?\b",
                  question, re.I)
    if m and (m[1] or "the past" in m[0].lower()):
        n = m[1].lower() if m[1] else "1"
        n = 1 if n in {"a", "an"} else int(n) if n.isdigit() else NUMBERS[n]
        unit = m[2].lower()
        start = asked - timedelta(days=n * (1 if unit == "day" else 7)) if unit in {"day", "week"} \
            else _shift_months(asked, n * (12 if unit == "year" else 1))
        return start, asked
    m = re.search(r"\b(this|last)\s+(month|year)\b", question, re.I)
    if m:
        month_mode = m[2].lower() == "month"
        if m[1].lower() == "this":
            return datetime(asked.year, asked.month if month_mode else 1, 1), asked
        if month_mode:
            first = _shift_months(asked.replace(day=1), 1)
            return first, _month_end(first.year, first.month)
        return datetime(asked.year - 1, 1, 1), _month_end(asked.year - 1, 12)
    return None


def entity_terms(question):
    """Distinctive stemmed query terms: no count/time grammar, month names or bare numbers."""
    return sorted({t for t in tokens(question) if t not in NOISE and not t.isdigit()})


def _best_span(turn_text, terms, limit):
    """(start, end, matched) of the best sentence mentioning the terms, clipped around its first match."""
    best, start = None, 0
    for boundary in [*SENTENCE_END.finditer(turn_text), None]:
        end = boundary.start() if boundary else len(turn_text)
        hits = [(m.start(), tokens(m[0])) for m in re.finditer(r"\w+", turn_text[start:end])]
        matched = {t for _, ts in hits for t in ts if t in terms}
        if matched:
            key = (len(matched), bool(re.search(r"\d", turn_text[start:end])), -start)
            if best is None or key > best[0]:
                anchor = start + next(p for p, ts in hits if terms.intersection(ts))
                left = max(start, anchor - limit // 3)
                right = min(end, left + limit)
                best = (key, (max(start, right - limit), right), matched)
        if boundary:
            start = boundary.end()
    return best


def window_evidence(index, question, question_date, ranked, limit=240, cap=4000):
    """({session: [(turn, start, end)]}, metadata) for a count window; ({}, None) when the question has none."""
    window = count_window(question, question_date)
    if window is None:
        return {}, None
    asked = datetime.strptime(question_date, DATE_FORMAT)
    terms = set(entity_terms(question))
    meta = {"window": [window[0].isoformat(), window[1].isoformat()], "terms": sorted(terms),
            "sessions": 0, "truncated": False}
    first_rank = {}
    for rank, i in enumerate(ranked):
        first_rank.setdefault(index.chunks[i].session, rank)
    candidates = []
    for si, session in enumerate(index.sessions):
        if not window[0] <= index.dates[si] <= min(window[1], asked) or not terms:
            continue
        best = None
        for ti, turn in enumerate(session["turns"]):
            found = _best_span(turn["content"], terms, limit)
            if found:
                key = (found[0][0], turn["role"] == "user", found[0][1], -ti)
                if best is None or key > best[0]:
                    best = (key, ti, found)
        if best:
            _, ti, found = best
            candidates.append((-len(found[2]), first_rank.get(si, len(ranked)), index.dates[si], si, (ti, *found[1])))
    spans, used = {}, 0
    for *_, si, span in sorted(candidates, key=lambda c: c[:4]):
        cost = len(index.render(si, [], extra_ranges=[span]))
        if used + cost > cap:
            meta["truncated"] = True
            continue
        spans[si] = [span]
        used += cost
    meta["sessions"] = len(spans)
    return spans, meta


def required_spans(index, question, question_date, ranked):
    """{session_index: [(turn_index, start, end)]} for every matching session in the question's count window."""
    return window_evidence(index, question, question_date, ranked)[0]
