from memchal.retrieval import HistoryIndex, partition, windows


def session(sid, date, turns):
    return {"session_id": sid, "date": date,
            "turns": [{"turn_id": f"{sid}_t{i}", "role": role, "content": text}
                      for i, (role, text) in enumerate(turns)]}


def retrieve(sessions, question, date="2026/10/30 (Fri) 12:00", budget=4000):
    index = HistoryIndex({"history_id": "h_test", "sessions": sessions})
    ranked, scores = index.rank(question, date)
    return index, index.pack(question, date, ranked, scores, budget=budget)


def test_temporal_filter_excludes_future_facts():
    sessions = [session("old", "2026/10/29 (Thu) 09:00", [("user", "My cat is called Pepper.")]),
                session("future", "2026/11/01 (Sun) 09:00", [("user", "My cat is called Pumpkin.")])]
    _, passages = retrieve(sessions, "What is my cat called?")
    assert [p["id"] for p in passages] == ["old"]
    assert "Pumpkin" not in str(passages)


def test_dates_belong_to_history_even_when_session_ids_repeat():
    a = session("same", "2026/10/01 (Thu) 09:00", [("user", "I ran a marathon yesterday.")])
    b = {**a, "date": "2026/10/12 (Mon) 09:00"}
    _, pa = retrieve([a], "When did I run a marathon?")
    _, pb = retrieve([b], "When did I run a marathon?")
    assert a["date"] in pa[0]["text"]
    assert b["date"] in pb[0]["text"]
    assert a["date"] not in pb[0]["text"]


def test_changes_keep_old_and_new_evidence_in_order():
    sessions = [session("new", "2026/10/29 (Thu) 09:00", [("user", "My 5K personal best is now 24:30.")]),
                session("old", "2026/10/01 (Thu) 09:00", [("user", "My 5K personal best is 25:50.")])]
    _, passages = retrieve(sessions, "What is my personal best for 5K?")
    assert [p["id"] for p in passages] == ["old", "new"]
    assert "25:50" in passages[0]["text"]
    assert "24:30" in passages[1]["text"]


def test_assistant_excerpt_retains_request_speaker_and_turn_ids():
    s = session("s1", "2026/10/01 (Thu) 09:00", [
        ("user", "Which restaurant in Rome do you recommend?"),
        ("assistant", "I recommend Roscioli for a romantic dinner.")])
    index = HistoryIndex({"history_id": "h", "sessions": [s]})
    assistant = next(i for i, c in enumerate(index.chunks) if c.turn == 1)
    text = index.render(0, [assistant])
    assert "user (s1_t0):" in text
    assert "assistant (s1_t1):" in text
    assert "Roscioli" in text


def test_retrieving_a_request_includes_its_answer():
    s = session("s1", "2026/10/01 (Thu) 09:00", [
        ("user", "Which restaurant in Rome do you recommend?"),
        ("assistant", "I recommend Roscioli for a romantic dinner.")])
    index = HistoryIndex({"history_id": "h", "sessions": [s]})
    user = next(i for i, c in enumerate(index.chunks) if c.turn == 0)
    assert "Roscioli" in index.render(0, [user])


def test_empty_history_is_supported():
    _, passages = retrieve([], "What is my cat's name?")
    assert passages == []


def test_overlapping_excerpts_are_merged_without_duplicating_content():
    content = " ".join(f"word{i}" for i in range(700))
    s = session("s", "2026/10/01 (Thu) 09:00", [("user", content)])
    index = HistoryIndex({"history_id": "h", "sessions": [s]})
    text = index.render(0, list(range(len(index.chunks))))
    assert text.endswith(content)
    assert text.count("word100 ") == 1


def test_windows_cover_every_character_including_very_long_words():
    for text in ["x" * 5000, "short", "first. " * 900]:
        covered = set()
        for a, b in windows(text):
            assert a < b <= len(text)
            covered.update(range(a, b))
        assert covered == set(range(len(text)))


def test_budget_counts_question_dates_and_labels():
    sessions = [session(f"s{i}", "2026/10/01 (Thu) 09:00", [("user", "My marathon was yesterday. " * 200)])
                for i in range(20)]
    question, date, budget = "When was my marathon?", "2026/10/30 (Fri) 12:00", 2900
    _, passages = retrieve(sessions, question, date, budget)
    assert sum(len(p["text"]) + 80 for p in passages) + len(question) + len(date) <= budget
    assert passages
    assert len({p["id"] for p in passages}) == len(passages)


def test_no_matching_evidence_does_not_manufacture_passages():
    _, passages = retrieve([session("s", "2026/10/01 (Thu) 09:00", [("user", "Hello there.")])],
                           "What is my hamster's name?")
    assert passages == []


def test_partition_is_by_history_not_question_wording():
    assert partition("same-history") == partition("same-history")
    assert {partition(f"h{i}") for i in range(100)} == {"tune", "holdout"}


def test_histories_do_not_mix():
    _, first = retrieve([session("a", "2026/10/01 (Thu) 09:00", [("user", "My cat is Pepper.")])], "My cat?")
    _, second = retrieve([session("b", "2026/10/01 (Thu) 09:00", [("user", "My cat is Miso.")])], "My cat?")
    assert "Miso" not in str(first)
    assert "Pepper" not in str(second)


def test_semantic_search_can_rescue_zero_keyword_overlap():
    import numpy as np

    class Semantic:
        session_text = staticmethod(lambda s: s["turns"][0]["content"])

        def encode(self, texts):
            return np.array([[1.0, 0.0] for _ in texts])

    class Rerank:
        def rank(self, query, passages):
            return [(i, 0.9) for i, _ in passages]

    index = HistoryIndex({"history_id": "h", "sessions": [
        session("s", "2026/10/01 (Thu) 09:00", [("user", "Purchased a desk.")])]})
    ranked, scores = index.rank("Which furniture?", "2026/10/30 (Fri) 12:00", Rerank(), semantic=Semantic())
    assert ranked
    assert "Purchased a desk." in index.pack("Which furniture?", "2026/10/30 (Fri) 12:00", ranked, scores)[0]["text"]


def test_coverage_packing_keeps_many_sessions_within_budget():
    sessions = [session(f"s{i}", "2026/10/01 (Thu) 09:00", [("user", "Bought a desk yesterday. " * 100)])
                for i in range(12)]
    index = HistoryIndex({"history_id": "h", "sessions": sessions})
    question, date = "How many desks did I buy?", "2026/10/30 (Fri) 12:00"
    ranked, scores = index.rank(question, date)
    passages = index.pack(question, date, ranked, scores, max_sessions=12, coverage=True)
    assert len(passages) == 12
    assert sum(len(p["text"]) + 80 for p in passages) + len(question) + len(date) <= 14500


def test_unambiguous_typo_expansion_is_search_only():
    from memchal.retrieval import BM25
    index = BM25(["I started a business.", "My cat is Pepper."])
    assert index.score("buisiness")[0] > 0
    assert index.score("hamster").sum() == 0


def test_short_user_reply_after_selected_assistant_turn_is_kept():
    history = {"history_id": "h_x", "sessions": [{"session_id": "s_1", "date": "2023/05/20 (Sat) 10:00", "turns": [
        {"turn_id": "t_1", "role": "user", "content": "Can you suggest names for my zombie character?"},
        {"turn_id": "t_2", "role": "assistant", "content": "Sure: Fissionator, Rotgut, Gravewalker and seven more zombie names to pick from."},
        {"turn_id": "t_3", "role": "user", "content": "I'll go with Fissionator."},
        {"turn_id": "t_4", "role": "assistant", "content": "Great choice."}]}]}
    index = HistoryIndex(history)
    chosen = [i for i, c in enumerate(index.chunks) if c.turn == 1]
    text = index.render(0, chosen)
    assert "I'll go with Fissionator." in text
    assert "Great choice." not in text
