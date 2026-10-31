"""End to end: a split directory -> predictions.jsonl.

Stages, each resumable and each a plain CLI of its own:
  1. prepare   local hybrid retrieval, packed dated excerpts        -> OUT/requests.jsonl
  2. hints     code-computed timeline passages                      -> OUT/requests-hints.jsonl
  3. runner    Reactor protocol (a fresh history per question)       -> OUT/reactor/results.jsonl, predictions.jsonl
  4. finalize  code-side abstention rules on Reactor's answers      -> OUT/predictions.jsonl
  5. validate  official format and citation ownership checks
Reactor credentials come from REACTOR_BASE_URL, REACTOR_AGENT_ID and REACTOR_ACCESS_KEY.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def stage(name, args, skip_if=None):
    if skip_if is not None and skip_if.exists():
        print(f"[{name}] reusing {skip_if}", flush=True)
        return
    print(f"[{name}] {' '.join(str(a) for a in args)}", flush=True)
    subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("split", type=Path, help="directory with histories.jsonl and questions.jsonl")
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--instructions", type=Path, default=ROOT / "instructions" / "reactor_instructions.txt")
    ap.add_argument("--reranker", default="minilm", help="minilm or an Ettin cross-encoder id")
    ap.add_argument("--chunk-dense", action="store_true")
    ap.add_argument("--decompose", action="store_true")
    ap.add_argument("--no-count-window", action="store_true", help="do not reserve every matching session for counting questions with a named calendar window")
    ap.add_argument("--no-hints", action="store_true")
    ap.add_argument("--retry-abstain", action="store_true", help="ask once more before accepting INSUFFICIENT_EVIDENCE (one extra call; rarely helped)")
    ap.add_argument("--one-history-per-dataset-history", action="store_true",
                    help="share one Reactor history across a history's questions (default: a fresh history per question)")
    ap.add_argument("--count-hints", action="store_true", help="also add the enumerated-mentions hint for counting questions (hurt in our test)")
    ap.add_argument("--max-chars", type=int, default=19500)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--partition", choices=["all", "tune", "holdout"], default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="prepare and preflight only; no Reactor calls")
    args = ap.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    split = args.split.resolve()

    requests = out / "requests.jsonl"
    prepare = ["memchal.prepare", split, requests, "--partition", args.partition, "--reranker", args.reranker]
    prepare += ["--limit", str(args.limit)] if args.limit else []
    prepare += ["--chunk-dense"] if args.chunk_dense else []
    prepare += ["--decompose"] if args.decompose else []
    prepare += [] if args.no_count_window else ["--count-window"]
    stage("prepare", prepare, skip_if=requests)

    hinted = requests
    if not args.no_hints:
        hinted = out / "requests-hints.jsonl"
        stage("hints", ["memchal.hints", requests, hinted] + ([] if args.count_hints else ["--no-counts"]), skip_if=hinted)

    runner = ["memchal.runner", split, hinted, out / "reactor", "--instructions", args.instructions.resolve(),
              "--max-chars", str(args.max_chars), "--timeout", str(args.timeout)]
    runner += ["--retry-abstain"] if args.retry_abstain else []
    runner += [] if args.one_history_per_dataset_history else ["--history-per-question"]
    runner += ["--dry-run"] if args.dry_run else []
    stage("runner", runner)
    if args.dry_run:
        return 0

    raw = out / "reactor" / "predictions.jsonl"
    if not raw.exists():
        print("Reactor run is incomplete; rerun the same command to resume.", flush=True)
        return 1
    final = out / "predictions.jsonl"
    stage("finalize", ["memchal.finalize", split / "questions.jsonl", raw, final])
    stage("validate", ["memchal.validate", split, final])
    predictions = [json.loads(l) for l in final.read_text().splitlines() if l.strip()]
    abstained = sum(p["abstain"] for p in predictions)
    print(f"{len(predictions)} predictions written to {final}: {len(predictions) - abstained} answers, {abstained} abstentions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
