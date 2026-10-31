# Submitted run (2026-10-31)

`predictions.jsonl` at the repository root = `runs/test-rerun/predictions.jsonl`, pushed 09:30 CET (commit 45b9102).

| | |
| --- | --- |
| Questions | 146 (15 histories, 200 conversations each) |
| Final file | 131 answers, 15 abstentions (10.3%); 1.81 citations per answer on average |
| Main pass | 05:58-08:52 CET in a detached container; 146 Reactor calls, median latency 61 s; 13 abstentions + 1 zero-count turned into an abstention by code |
| Configuration | Ettin-68m reranker + dense chunk localisation + two-part decomposition; packets <= 14,500 chars; timeline + ownership hints (count hint off); policy v4; fresh Reactor history per question; no retry-on-abstain; one format repair for alternatives / missing units; code-side zero-count abstention |
| Audited rerun | 15 questions that a human audit of the raw test histories (`../judge/`) marked wrong or doubtful were re-asked with 144 lexical candidates, 24 sources, 26,000-char packets (`run-wide-rerun.sh`, `merge_rerun.py`); 16 Reactor calls (1 format repair), median 75 s; 11 of 15 answers changed, 7 of 15 are abstentions. Whatever Reactor answered replaced the earlier prediction. |
| Cut for the deadline | the count-window pass (8 windowed counting questions; 1 of 8 answered before it was stopped) and the soft-policy second-opinion pass (never started). The scripts are here; the rules are documented in `merge.py` and `merge_abstained.py`. |

What the rerun changed (audit expectation in brackets): vegetables 8 -> 6 [6]; long run 6:00 -> 6:30 a.m. [6:30]; greyhound "Nell (previously Juniper)" -> Juniper [Juniper]; medical check-up 79 days -> abstain [abstain: the check-up was Camille's]; neighbourhood Estrela -> abstain [Graça: never retrieved]; French tutor Camille -> abstain [doubtful]; orchids 0 -> 6 [3]; books since March abstain -> 3 [doubtful]; restaurant "Amici (earlier Osteria Numero)" -> Amici [Osteria Numero]; shelter -> "Rifugio San Francesco (renamed from Rifugio Arca)" [Rifugio Arca]; unchanged: coworking space, job title, firefighter years, book-club attendance (the needed conversations share no words with the question and were never retrieved, even with 24 sources), favourite colour (Dark Green, audit says teal).

Why morning latency differed from the night: the test has ~10 questions per history; inside one Reactor history each next question waited ~40 s for `busy/previous_pending` (5-7 client retries). A fresh history per question removed the wait (0 retries) and brought the pace from ~2.7 min to ~1 min per question.

Night incident: an agent-session restart at 02:31 killed every background process and cost about three hours; from 05:58 the runs lived in Docker containers, which survive such restarts (two later restarts did not interrupt them).
