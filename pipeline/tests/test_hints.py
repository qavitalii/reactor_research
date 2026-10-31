from memchal.hints import count_hint, key_stems, ownership_hint, timeline_hint, with_hints

DATE = "2023/05/20 (Sat) 10:00"


def passage(sid, date, text):
    return {"id": sid, "text": f"Session date: {date}\nuser (t_a1): {text}\nassistant (t_a2): Sounds great.", "score": 0.5}


def test_key_stems_drop_question_words():
    assert key_stems("How many times did I visit the museum last month?") == {"museum"}


def test_count_hint_lists_dated_mentions_per_excerpt():
    record = {"question": "How many museums did I visit in May?", "question_date": "2023/05/30 (Tue) 20:00",
              "passages": [passage("s_1", DATE, "I visited the art museum today. Then I had lunch."),
                           passage("s_2", "2023/05/25 (Thu) 09:00", "Weather is nice."),
                           passage("s_3", "2023/05/27 (Sat) 09:00", "Went to the science museum with my sister.")]}
    hint = count_hint(record)
    assert hint["id"] is None and hint["hint"]
    assert "[E1] 2023-05-20 (user): I visited the art museum today." in hint["text"]
    assert "[E3] 2023-05-27 (user): Went to the science museum with my sister." in hint["text"]
    assert "[E2]" not in hint["text"]
    assert "lunch" not in hint["text"]


def test_non_count_question_gets_no_count_hint_and_hints_are_appended_in_order():
    record = {"question": "What is my cat's name now?", "question_date": "2023/05/30 (Tue) 20:00",
              "passages": [passage("s_1", DATE, "My cat is Pepper.")]}
    assert count_hint(record) is None
    hinted = with_hints(record)
    assert [p.get("hint") for p in hinted["passages"]] == [None, True]
    assert timeline_hint(record)["text"] == hinted["passages"][1]["text"]


def test_ownership_hint_flags_decoy_and_ignores_users_own_things():
    decoy = {"question": "What is my cat's name?", "question_date": "2023/05/30 (Tue) 20:00",
             "passages": [passage("s_1", DATE, "My sister's cat Whiskers keeps scratching the couch."),
                          passage("s_2", "2023/05/25 (Thu) 09:00", "My cat is Pepper."),
                          passage("s_3", "2023/05/26 (Fri) 09:00", "Bjørn’s beehives are doing well.")]}
    hint = ownership_hint(decoy)
    assert hint["id"] is None and hint["hint"] and len(hint["text"]) <= 600
    assert "[E1] 2023-05-20 mentions the sister's cat whiskers (not the user's)" in hint["text"]
    assert "[E2]" not in hint["text"] and "[E3]" not in hint["text"]  # beehives do not match the question
    assert "do not cite this note" in hint["text"]
    own = {**decoy, "passages": [decoy["passages"][1]]}
    assert ownership_hint(own) is None
    assert not any("Ownership" in p["text"] for p in with_hints(own)["passages"])
    assert with_hints(decoy)["passages"][-1]["text"] == hint["text"]


def test_ownership_hint_names_other_owners_and_skips_questions_about_them():
    record = {"question": "How many beehives do I have?", "question_date": "2023/05/30 (Tue) 20:00",
              "passages": [passage("s_1", DATE, "My neighbor has a few beehives. Bjørn’s beehives are in the orchard."),
                           passage("s_2", DATE, "It's a lovely day. I put up two beehives.")]}
    text = ownership_hint(record)["text"]
    assert "[E1]" in text and "the neighbor's few beehives" in text and "[E2]" not in text
    assert with_hints(record)["passages"][-1]["text"] == text
    assert ownership_hint({**record, "question": "How many beehives does my neighbor have?"}) is None


def test_weekday_and_holiday_possessives_are_not_owners():
    record = {"question": "What is the name of my ceramics class instructor now?", "question_date": "2023/08/30 (Wed) 20:00",
              "passages": [passage("s_1", DATE, "Tuesday's class was great; the instructor Maya showed us glazing."),
                           passage("s_2", "2023/05/25 (Thu) 09:00", "Christmas's class list is out.")]}
    from memchal.hints import ownership_hint
    assert ownership_hint(record) is None
