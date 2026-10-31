"""Side-by-side report of A/B arms (partial results allowed): answer status via score.py matching, evidence F1, latency."""
import json, sys, statistics
sys.path.insert(0, "/home/alex/code/personal/memory-challenge")
from score import answer_matched, evidence_f1
from reactor.predictions import strip_labels
gold = {json.loads(l)["question_id"]: json.loads(l) for l in open("/home/alex/code/personal/memory-challenge/artifacts/ab-20261030/gold46.jsonl")}
arms = {}
for name in sys.argv[1:]:
    path = f"/home/alex/code/personal/memory-challenge/artifacts/ab-20261030/{name}/results.jsonl"
    try:
        arms[name] = {json.loads(l)["question_id"]: json.loads(l) for l in open(path)}
    except FileNotFoundError:
        arms[name] = {}
def status(r, g):
    if r is None: return "-"
    if g["abstain"] or r["abstained"]: return "correct" if g["abstain"] == r["abstained"] else "WRONG-abst"
    return "correct" if answer_matched(strip_labels(r["answer"]), g) else "unjudged"
rows = []
for qid, g in gold.items():
    rs = {a: arms[a].get(qid) for a in arms}
    if all(r is None for r in rs.values()): continue
    rows.append((g, rs))
for g, rs in rows:
    print(f"\n[{g['question_type']}{' ABSTAIN' if g['abstain'] else ''}] gold={g['answer'][:70]!r}")
    for a, r in rs.items():
        if r is None: print(f"   {a:9s}: -"); continue
        f1 = None if g["abstain"] else evidence_f1([c["id"] for c in r["citations"] if c.get("id")], g["evidence"])
        print(f"   {a:9s}: {status(r, g):10s} f1={'-' if f1 is None else f'{f1:.2f}'} lat={r.get('latency_s',0):.0f}s | {r['answer'][:110].replace(chr(10),' ')}")
print("\n=== summary (questions present in each arm)")
for a in arms:
    rs = [(gold[q], r) for q, r in arms[a].items()]
    if not rs: print(a, "no results"); continue
    st = [status(r, g) for g, r in rs]
    f1s = [evidence_f1([c["id"] for c in r["citations"] if c.get("id")], g["evidence"]) for g, r in rs if not g["abstain"]]
    lat = [r.get("latency_s", 0) for g, r in rs]
    print(f"{a}: n={len(rs)} correct={st.count('correct')} unjudged={st.count('unjudged')} wrong_abst={st.count('WRONG-abst')} "
          f"evidenceF1={statistics.mean(f1s) if f1s else 0:.3f} latency median={statistics.median(lat):.0f}s max={max(lat):.0f}s")
