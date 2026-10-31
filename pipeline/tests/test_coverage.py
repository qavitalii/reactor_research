from datetime import datetime

import pytest

from memchal.coverage import count_window, entity_terms, required_spans, window_evidence
from memchal.retrieval import HistoryIndex
from test_retrieval import session

ASKED = "2023/09/10 (Sun) 12:00"


def span(question, asked=ASKED):
    window = count_window(question, asked)
    return window and (window[0].strftime("%Y-%m-%d"), window[1].strftime("%Y-%m-%d"))


@pytest.mark.parametrize("question,expected", [
    ("How many books did I read in August?", ("2023-08-01", "2023-08-31")),
    ("How many books did I read in December?", ("2022-12-01", "2022-12-31")),
    ("How many books did I read in September?", ("2023-09-01", "2023-09-10")),
    ("How many books did I read last month?", ("2023-08-01", "2023-08-31")),
    ("How many books did I read this year?", ("2023-01-01", "2023-09-10")),
    ("How many books did I read since April?", ("2023-04-01", "2023-09-10")),
    ("How many books have I read in the past two months?", ("2023-07-10", "2023-09-10")),
    ("How many books did I read between May and June?", ("2023-05-01", "2023-06-30")),
    ("How many books did I read between November and February?", ("2022-11-01", "2023-02-28")),
])
def test_count_windows_resolve_against_question_date(question, expected):
    assert span(question) == expected


def test_last_month_crosses_year_boundary():
    assert span("How many trips did I take last month?", "2024/01/05 (Fri) 09:00") == ("2023-12-01", "2023-12-31")


def test_no_window():
    assert span("How many books do I own?") is None
    assert span("What did I read in August?") is None


def test_entity_terms_drop_count_and_calendar_words():
    assert entity_terms("How many books did I read in August 2023?") == ["book", "read"]
    assert "august" not in entity_terms("How many total concerts since April?")


def make_index(n=20):
    sessions = [session(f"s{i}", f"2023/08/{i + 1:02} (Tue) 09:00",
                        [("user", f"I finished a novel today, number {i}. " + "Filler sentence. " * 40)]) for i in range(n)]
    sessions += [session("july", "2023/07/31 (Mon) 09:00", [("user", "I finished a novel.")]),
                 session("future", "2023/09/11 (Mon) 09:00", [("user", "I finished a novel.")]),
                 session("unrelated", "2023/08/15 (Tue) 09:00", [("user", "The weather is nice.")])]
    return HistoryIndex({"history_id": "h", "sessions": sessions})


Q = "How many novels did I finish in August?"


def test_required_spans_cover_window_only_and_are_short():
    index = make_index()
    spans, meta = window_evidence(index, Q, ASKED, [])
    ids = {index.sessions[si]["session_id"] for si in spans}
    assert ids <= {f"s{i}" for i in range(20)}
    assert meta["truncated"] == (len(spans) < 20) and meta["sessions"] == len(spans) > 5
    for si, [(ti, a, b)] in spans.items():
        assert b - a <= 240 and "novel" in index.sessions[si]["turns"][ti]["content"][a:b]
    assert required_spans(index, Q, ASKED, []) == spans
    assert required_spans(index, "How many novels do I own?", ASKED, []) == {}


def test_pack_includes_unranked_matching_session_and_respects_budget():
    index = make_index(8)
    ranked, scores = index.rank(Q, ASKED)
    top = {index.chunks[i].session for i in ranked[:1]}
    spans = required_spans(index, Q, ASKED, ranked)
    outside = next(si for si in spans if si not in top)
    plain = index.pack(Q, ASKED, ranked[:1], {i: scores[i] for i in ranked[:1]}, budget=3000, max_sessions=1)
    report = {}
    packed = index.pack(Q, ASKED, ranked[:1], {i: scores[i] for i in ranked[:1]}, budget=3000, max_sessions=1,
                        required_spans=spans, report=report)
    sid = index.sessions[outside]["session_id"]
    assert sid not in {p["id"] for p in plain}
    assert sid in {p["id"] for p in packed}
    assert sum(len(p["text"]) + 80 for p in packed) + len(Q) + len(ASKED) <= 3000
    assert report["dropped"] == 0


def test_pack_drops_lowest_priority_required_sessions_instead_of_raising():
    index = make_index(8)
    spans = required_spans(index, Q, ASKED, [])
    report = {}
    packed = index.pack(Q, ASKED, [], {}, budget=700, required_spans=spans, report=report)
    assert report["dropped"] == len(spans) - len(packed) > 0
    assert [p["id"] for p in packed] == [index.sessions[si]["session_id"] for si in sorted(spans, key=lambda s: index.dates[s])
                                         if index.sessions[si]["session_id"] in {p["id"] for p in packed}]
    assert sum(len(p["text"]) + 80 for p in packed) + len(Q) + len(ASKED) <= 700


def test_pack_unchanged_without_required_spans():
    index = make_index(4)
    ranked, scores = index.rank(Q, ASKED)
    assert index.pack(Q, ASKED, ranked, scores) == index.pack(Q, ASKED, ranked, scores, required_spans={})
