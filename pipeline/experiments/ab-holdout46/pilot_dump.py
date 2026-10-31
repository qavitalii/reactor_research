"""Dump everything Reactor said per pilot question (both arms) next to the gold, for behaviour analysis."""
import json, sys
sys.path.insert(0, "/home/alex/code/personal/memory-challenge")
from score import answer_matched, evidence_f1
from reactor.predictions import strip_labels
ROOT = "/home/alex/code/personal/memory-challenge/artifacts/ab-20261030/"
gold = {json.loads(l)["question_id"]: json.loads(l) for l in open(ROOT + "gold-pilot6.jsonl")}
def load(name):
    try: return [json.loads(l) for l in open(ROOT + name)]
    except FileNotFoundError: return []
ARMS = sys.argv[1:] or ["baseline", "hints", "instr2"]
arms = {a: {r["question_id"]: r for r in load(f"pilot-{a}/results.jsonl")} for a in ARMS}
attempts = {a: load(f"pilot-{a}/attempts.jsonl") for a in ARMS}
for qid, g in gold.items():
    print("=" * 100); print(f"[{g['question_type']}{' | UNANSWERABLE' if g['abstain'] else ''}]  gold={g['answer']!r}  evidence={g['evidence']}")
    for arm, rs in arms.items():
        r = rs.get(qid)
        if not r:
            errs = [a for a in attempts[arm] if a.get("question_id") == qid]
            print(f"--- {arm}: no final result yet; attempts={[a.get('status') for a in errs]}"); continue
        cites = [(c["label"], c.get("id")) for c in r["citations"]]
        ok = ("correct" if g["abstain"] == r["abstained"] else "WRONG") if (g["abstain"] or r["abstained"]) else ("match" if answer_matched(strip_labels(r["answer"]), g) else "unjudged")
        f1 = None if g["abstain"] else evidence_f1([i for _, i in cites if i], g["evidence"])
        print(f"--- {arm}: {ok} | latency {r['latency_s']:.0f}s cycle {r.get('cycle')} msg {r['message_chars']} chars | f1={f1}")
        print(f"    answer: {r['answer']!r}")
        print(f"    citations: {cites} unknown={r.get('unknown_citations')}")
        for o in r.get("other_replies", []) or []:
            print(f"    interim: {str(o)[:300]!r}")
        reply = r.get("reply", "")
        if reply.strip() != r["answer"] and not reply.strip().endswith(r["answer"]):
            print(f"    full reply: {reply[:600]!r}")
