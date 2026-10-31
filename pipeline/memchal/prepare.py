"""Build Reactor evidence requests without loading gold.jsonl."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time

from .retrieval import HistoryIndex, Reranker, SemanticSearch, needs_coverage, partition, read_jsonl


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("split", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--mode", choices=["bm25", "rerank", "hybrid"], default="hybrid")
    ap.add_argument("--partition", choices=["all", "tune", "holdout"], default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=int, default=14500)
    ap.add_argument("--sessions", type=int, default=0, help="maximum sources; 0 chooses 12 for counting questions, otherwise 6")
    ap.add_argument("--per-session", type=int, default=4500)
    ap.add_argument("--candidates", type=int, default=72)
    ap.add_argument("--reranker", default="minilm", help="minilm (default) or an Ettin cross-encoder id")
    ap.add_argument("--chunk-dense", action="store_true", help="dense chunk selection inside shortlisted sessions")
    ap.add_argument("--decompose", action="store_true", help="search both parts of two-part questions (decompose.py)")
    ap.add_argument("--only-two-part", action="store_true", help="keep only questions decompose.parts() splits")
    ap.add_argument("--only-count", action="store_true", help="keep only counting/total questions (needs_coverage)")
    ap.add_argument("--ids", type=Path, help="keep only the question_ids listed in this jsonl/txt file")
    ap.add_argument("--count-window", action="store_true",
                    help="reserve one span from every matching session in a counting question's named date window")
    args = ap.parse_args()
    if args.limit < 0 or args.sessions < 0 or min(args.budget, args.per_session, args.candidates) <= 0:
        ap.error("limits must be nonnegative, and budget, per-session and candidates must be positive")
    questions = [q for q in read_jsonl(args.split / "questions.jsonl")
                 if args.partition == "all" or partition(q["history_id"]) == args.partition]
    if args.ids:
        import json as _json
        wanted = set()
        for line in args.ids.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                wanted.add(_json.loads(line)["question_id"] if line.startswith("{") else line)
        questions = [q for q in questions if q["question_id"] in wanted]
    if args.only_count:
        questions = [q for q in questions if needs_coverage(q["question"])]
    if args.only_two_part:
        from .decompose import parts
        questions = [q for q in questions if parts(q["question"])]
    # Stable sampling across the file, whose original order groups question types.
    if args.limit:
        import hashlib
        questions = sorted(questions, key=lambda q: hashlib.sha256(q["history_id"].encode()).hexdigest())[:args.limit]
    grouped = defaultdict(list)
    for q in questions:
        grouped[q["history_id"]].append(q)
    reranker = None
    if args.mode != "bm25":
        if args.reranker == "minilm":
            reranker = Reranker()
        else:
            from .ettin_rerank import EttinReranker
            reranker = EttinReranker(model=args.reranker)
    semantic = SemanticSearch() if args.mode == "hybrid" else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    part = args.output.with_suffix(args.output.suffix + ".part")
    started, done = time.monotonic(), 0
    with part.open("w", encoding="utf-8") as f:
        for history in read_jsonl(args.split / "histories.jsonl"):
            if history["history_id"] not in grouped:
                continue
            index = HistoryIndex(history)
            for q in grouped[history["history_id"]]:
                if args.decompose:
                    from .decompose import rank_decomposed
                    ranked, scores = rank_decomposed(index, q["question"], q["question_date"], reranker, args.candidates,
                                                     semantic, chunk_dense=args.chunk_dense)
                else:
                    ranked, scores = index.rank(q["question"], q["question_date"], reranker, args.candidates, semantic,
                                                chunk_dense=args.chunk_dense)
                coverage = needs_coverage(q["question"])
                max_sessions = args.sessions or (12 if coverage else 6)
                required, evidence, report = {}, None, {}
                if args.count_window:
                    from .coverage import window_evidence
                    required, evidence = window_evidence(index, q["question"], q["question_date"], ranked)
                passages = index.pack(q["question"], q["question_date"], ranked, scores,
                                      args.budget, max_sessions, args.per_session, coverage, required, report)
                record = {**q, "passages": passages, "retrieval": {
                    "mode": args.mode, "partition": partition(q["history_id"]),
                    "config": {"budget": args.budget, "max_sessions": max_sessions, "coverage": coverage,
                               "per_session": args.per_session, "lexical_candidates": args.candidates},
                    "chars": sum(len(p["text"]) + 80 for p in passages) + len(q["question"]) + len(q["question_date"]),
                    "ranked_sessions": list(dict.fromkeys(index.sessions[index.chunks[i].session]["session_id"] for i in ranked))}}
                if evidence:
                    record["retrieval"]["required_evidence"] = {**evidence, "dropped": report["dropped"]}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                done += 1
                if done % 10 == 0 or done == len(questions):
                    print(f"Prepared {done}/{len(questions)} in {time.monotonic() - started:.1f}s", flush=True)
    if done != len(questions):
        raise SystemExit(f"Only found histories for {done}/{len(questions)} questions")
    part.replace(args.output)


if __name__ == "__main__":
    main()
