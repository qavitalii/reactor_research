"""History-local retrieval. This module never reads gold answers or question types."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
import snowballstemmer

DATE_FORMAT = "%Y/%m/%d (%a) %H:%M"
STEMMER = snowballstemmer.stemmer("english")
STOP = set(ENGLISH_STOP_WORDS) | {"yeah", "thanks", "thank", "hi", "hello", "hey"}
WORDS = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=200_000)
def stem(word):
    return STEMMER.stemWord(word)


def tokens(text):
    return [stem(w) for w in WORDS.findall(text.lower()) if w not in STOP]


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def partition(history_id):
    # Rephrasings share a history, so cannot leak across tune / holdout.
    return "holdout" if int(hashlib.sha256(history_id.encode()).hexdigest(), 16) % 5 == 0 else "tune"


def needs_coverage(question):
    return bool(re.search(r"\b(how many|how much|total|combined|altogether)\b", question, re.I))


class BM25:
    def __init__(self, texts):
        self.vectorizer = CountVectorizer(analyzer=tokens, dtype=np.float32)
        try:
            counts = self.vectorizer.fit_transform(texts).tocsr()
        except ValueError as exc:
            if "empty vocabulary" not in str(exc):
                raise
            self.matrix = None
            self.size = len(texts)
            return
        lengths = np.asarray(counts.sum(axis=1)).ravel()
        df = np.bincount(counts.indices, minlength=counts.shape[1])
        idf = np.log1p((counts.shape[0] - df + 0.5) / (df + 0.5))
        norm = 1.2 * (0.25 + 0.75 * lengths / max(float(lengths.mean()), 1))
        counts.data *= 2.2 / (counts.data + np.repeat(norm, np.diff(counts.indptr)))
        counts.data *= idf[counts.indices]
        self.matrix = counts.tocsc()

    def score(self, question):
        if self.matrix is None:
            return np.zeros(self.size)
        vocab = self.vectorizer.vocabulary_
        terms = set(tokens(question))
        indices = sorted({vocab[t] for t in terms if t in vocab})
        scores = np.asarray(self.matrix[:, indices].sum(axis=1)).ravel()
        # Repair only unambiguous extra-letter / adjacent-swap errors in search.
        # The original question and source text sent to Reactor remain untouched.
        corrections = set()
        for term in terms - vocab.keys():
            if len(term) < 5 or not term.isalpha():
                continue
            variants = {term[:i] + term[i + 1:] for i in range(len(term))}
            variants |= {term[:i] + term[i + 1] + term[i] + term[i + 2:] for i in range(len(term) - 1)}
            matches = variants & vocab.keys()
            if len(matches) == 1:
                corrections.add(vocab[next(iter(matches))])
        if corrections:
            scores += 0.5 * np.asarray(self.matrix[:, sorted(corrections)].sum(axis=1)).ravel()
        return scores


@dataclass(frozen=True)
class Chunk:
    session: int
    turn: int
    start: int
    end: int
    text: str
    search_text: str


def windows(text, size=1050, overlap=180):
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = max(text.rfind("\n", start + size // 2, end), text.rfind(". ", start + size // 2, end))
            if boundary >= 0:
                end = boundary + 1
        yield start, end
        if end == len(text):
            break
        start = max(start + 1, end - overlap)


class HistoryIndex:
    def __init__(self, history):
        self.history_id = history["history_id"]
        self.sessions = history["sessions"]
        self.dates = [datetime.strptime(s["date"], DATE_FORMAT) for s in self.sessions]
        self.chunks = []
        for si, session in enumerate(self.sessions):
            previous_user = ""
            for ti, turn in enumerate(session["turns"]):
                content = turn["content"]
                for start, end in windows(content):
                    text = content[start:end]
                    context = f"User request: {previous_user[:280]}\n" if turn["role"] == "assistant" else ""
                    self.chunks.append(Chunk(si, ti, start, end, text, f"{context}{turn['role']}: {text}"))
                if turn["role"] == "user":
                    previous_user = content
        self.chunk_sessions = np.array([c.session for c in self.chunks], dtype=np.int32)
        self.chunk_search = BM25([c.search_text for c in self.chunks])
        self.session_search = BM25(["\n".join(t["content"] for t in s["turns"]) for s in self.sessions])

    def rank(self, question, question_date, reranker=None, candidates=72, semantic=None, chunk_dense=False):
        cutoff = datetime.strptime(question_date, DATE_FORMAT)
        allowed = np.array([d <= cutoff for d in self.dates], dtype=bool)
        cs = self.chunk_search.score(question)
        ss = self.session_search.score(question)
        if len(cs):
            cs[~allowed[self.chunk_sessions]] = 0
        ss[~allowed] = 0
        normalized = cs / max(float(cs.max(initial=0)), 1e-8)
        normalized += 0.2 * ss[self.chunk_sessions] / max(float(ss.max(initial=0)), 1e-8)
        lexical_order = np.argsort(-normalized, kind="stable")
        chosen, per_session, per_role = [], Counter(), Counter()
        for i in lexical_order:
            if normalized[i] <= 0:
                break
            si = self.chunks[i].session
            role = self.sessions[si]["turns"][self.chunks[i].turn]["role"]
            if per_session[si] < 6 and per_role[si, role] < 3:
                chosen.append(int(i))
                per_session[si] += 1
                per_role[si, role] += 1
            if len(chosen) >= candidates:
                break
        scores = {i: float(normalized[i]) for i in chosen}
        if reranker and (chosen or semantic and self.chunks):
            ranked = reranker.rank(question, [(i, self.chunks[i].search_text) for i in chosen]) if chosen else []
            dense_rank = {}
            if semantic:
                if not hasattr(self, "semantic_vectors"):
                    self.semantic_vectors = semantic.encode([semantic.session_text(s) for s in self.sessions])
                query_vector = semantic.encode(["Represent this sentence for searching relevant passages: " + question])[0]
                similarities = self.semantic_vectors @ query_vector
                similarities[~allowed] = -np.inf
                dense_order = [int(s) for s in np.argsort(-similarities, kind="stable") if allowed[s]]
                dense_rank = {si: rank for rank, si in enumerate(dense_order)}
                represented = {self.chunks[i].session for i in chosen}
                extra = []
                if chunk_dense:
                    # Dense chunk scores inside shortlisted sessions (both roles), including sessions BM25 already found.
                    if not hasattr(self, "session_chunk_ids"):
                        self.session_chunk_ids = defaultdict(list)
                        for i, c in enumerate(self.chunks):
                            self.session_chunk_ids[c.session].append(i)
                    have = set(chosen)
                    for si in list(dict.fromkeys(dense_order[:12] + sorted(represented, key=lambda s: dense_rank[s])))[:24]:
                        ids = [i for i in self.session_chunk_ids[si] if i not in have]
                        if ids:
                            sims = semantic.encode([self.chunks[i].search_text for i in ids]) @ query_vector
                            extra.extend(ids[j] for j in np.argsort(-sims, kind="stable")[:2 if si in represented else 3])
                for si in ([] if chunk_dense else dense_order[:12]):
                    if si in represented:
                        continue
                    indices = [int(i) for i in lexical_order if self.chunks[i].session == si]
                    # Include user facts even when there are no shared query words.
                    for role, limit in (("user", 2), ("assistant", 1)):
                        extra.extend([i for i in indices if self.sessions[si]["turns"][self.chunks[i].turn]["role"] == role][:limit])
                if extra:
                    ranked += reranker.rank(question, [(i, self.chunks[i].search_text) for i in extra])
                    chosen += extra
                    ranked.sort(key=lambda pair: (-pair[1], pair[0]))
            # Reciprocal rank fusion retains exact-name matches while semantic ranking leads.
            lr = {i: rank for rank, i in enumerate(chosen)}
            scores = {i: 1 / (12 + rank) + 0.25 / (12 + lr[i]) for rank, (i, _) in enumerate(ranked)}
            if dense_rank:
                scores = {i: score + 0.5 / (12 + dense_rank[self.chunks[i].session]) for i, score in scores.items()}
            chosen = sorted(chosen, key=lambda i: (-scores[i], i))
        return chosen, scores

    def pack(self, question, question_date, ranked, scores, budget=14500, max_sessions=6, per_session=4500, coverage=False,
             required_spans=None, report=None):
        """Pack verbatim excerpts; merges overlap and preserves dates, roles, and turn IDs.

        required_spans ({session: [(turn, start, end)]}, highest priority first) are reserved before ranked detail and
        are not limited to max_sessions; those that do not fit are dropped (counted in report["dropped"])."""
        if budget < len(question) + len(question_date):
            raise ValueError("Question and date alone exceed the evidence budget")
        by_session = defaultdict(list)
        for i in ranked:
            by_session[self.chunks[i].session].append(i)
        session_order = sorted(by_session, key=lambda s: (-max(scores[i] for i in by_session[s]), s))[:max_sessions]
        selected = defaultdict(list)
        excerpt_limits = {}
        passages = []
        required = {}
        asked = datetime.strptime(question_date, DATE_FORMAT) if required_spans else None
        # First allocate one excerpt per session for multi-session coverage, then add detail.
        remaining = budget - len(question) - len(question_date)
        for si, spans in (required_spans or {}).items():
            if self.dates[si] > asked:
                raise ValueError("Required evidence is after the question date")
            cost = len(self.render(si, [], extra_ranges=spans)) + 80
            if cost - 80 > per_session or cost > remaining:
                continue
            required[si] = spans
            remaining -= cost
        if report is not None:
            report["dropped"] = len(required_spans or {}) - len(required)
        for round_no in range(6):
            for si in session_order:
                if round_no >= len(by_session[si]) and not (coverage and round_no == 1 and selected.get(si)):
                    continue
                proposed = selected[si] + ([by_session[si][round_no]] if round_no < len(by_session[si]) else [])
                limit = 550 if coverage and round_no == 0 else None
                extra = required.get(si, ())
                text = self.render(si, proposed, limit, extra)
                old = self.render(si, selected[si], excerpt_limits.get(si), extra) if selected[si] or extra else ""
                # Includes conservative overhead for [E#], JSON labels, and client formatting.
                cost = len(text) - len(old) + (80 if not old else 0)
                if len(text) <= per_session and cost <= remaining:
                    selected[si] = proposed
                    excerpt_limits[si] = limit
                    remaining -= cost
        # Chronology helps changes and relative dates. Ranking is retained in metadata.
        for si in sorted(set(selected) | set(required), key=lambda s: (self.dates[s], s)):
            if selected.get(si) or si in required:
                passages.append({"id": self.sessions[si]["session_id"],
                                 "text": self.render(si, selected.get(si, []), excerpt_limits.get(si), required.get(si, ())),
                                 "score": max((scores[i] for i in selected.get(si, [])), default=0.0)})
        return passages

    def render(self, si, chunk_ids, excerpt_limit=None, extra_ranges=()):
        session = self.sessions[si]
        ranges = defaultdict(list)
        for i in chunk_ids:
            c = self.chunks[i]
            ranges[c.turn].append((c.start, min(c.end, c.start + excerpt_limit) if excerpt_limit else c.end))
            # A retrieved request often repeats the question exactly: its answer is
            # in the NEXT turn, so do not spend the context budget on the request alone.
            turn = session["turns"][c.turn]
            if (turn["role"] == "user" and len(turn["content"]) <= 450
                    and re.search(r"\?|\b(?:recommend|suggest|tell me|give me)\b", turn["content"], re.I)
                    and c.turn + 1 < len(session["turns"])):
                following = session["turns"][c.turn + 1]
                if following["role"] == "assistant":
                    ranges[c.turn + 1].append((0, min(excerpt_limit or 1050, len(following["content"]))))
            # Include a short preceding request with assistant excerpts (pronoun resolution).
            if session["turns"][c.turn]["role"] == "assistant" and c.turn > 0:
                previous = session["turns"][c.turn - 1]
                if previous["role"] == "user" and len(previous["content"]) <= 450:
                    ranges[c.turn - 1].append((0, len(previous["content"])))
        # A short user reply after a selected assistant turn often holds the decision
        # ("I'll go with Fissionator"); keep it so a list of options is not cut before the choice.
        for ti in [t for t in ranges if session["turns"][t]["role"] == "assistant"]:
            if ti + 1 < len(session["turns"]):
                following = session["turns"][ti + 1]
                if following["role"] == "user" and len(following["content"]) <= 320:
                    ranges[ti + 1].append((0, len(following["content"])))
        for ti, start, end in extra_ranges:
            ranges[ti].append((start, end))
        lines = [f"Session date: {session['date']}"]
        for ti in sorted(ranges):
            turn = session["turns"][ti]
            merged = []
            for start, end in sorted(ranges[ti]):
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
                else:
                    merged.append((start, end))
            text = "\n[... omitted ...]\n".join(turn["content"][a:b] for a, b in merged)
            if merged[0][0] > 0:
                text = "[... excerpt begins ...] " + text
            if merged[-1][1] < len(turn["content"]):
                text += " [... excerpt ends ...]"
            lines.append(f"{turn['role']} ({turn['turn_id']}): {text}")
        return "\n".join(lines)


class SemanticSearch:
    """Coarse session search over user turns; vectors are cached by content, never date."""
    def __init__(self, cache_dir=".cache"):
        import sqlite3
        from fastembed import TextEmbedding
        self.name = "BAAI/bge-small-en-v1.5"
        self.model = TextEmbedding(self.name, cache_dir=str(Path(cache_dir) / "embeddings"), threads=2)
        self.db = sqlite3.connect(Path(cache_dir) / "embeddings.sqlite", check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector BLOB NOT NULL)")

    @staticmethod
    def session_text(session):
        text = "\n".join("user: " + t["content"] for t in session["turns"] if t["role"] == "user")
        if not text:
            text = "\n".join(t["content"] for t in session["turns"])
        return text if len(text) <= 1900 else text[:1400] + "\n[...]\n" + text[-500:]

    def encode(self, texts):
        vectors, missing = {}, {}
        keys = [hashlib.sha256((self.name + ":" + text).encode()).hexdigest() for text in texts]
        for key, text in zip(keys, texts):
            row = self.db.execute("SELECT vector FROM vectors WHERE key = ?", (key,)).fetchone()
            if row:
                vectors[key] = np.frombuffer(row[0], dtype=np.float32)
            else:
                missing[key] = text
        # Similar-length batches reduce padding work on CPU.
        ordered = sorted(missing, key=lambda key: len(missing[key]))
        for start in range(0, len(ordered), 8):
            batch = ordered[start:start + 8]
            for key, vector in zip(batch, self.model.embed([missing[k] for k in batch], batch_size=8)):
                vector = np.asarray(vector, dtype=np.float32)
                vector = vector / max(float(np.linalg.norm(vector)), 1e-8)
                vectors[key] = vector
                self.db.execute("INSERT OR REPLACE INTO vectors VALUES (?, ?)", (key, vector.tobytes()))
            self.db.commit()
        return np.stack([vectors[key] for key in keys])


class Reranker:
    def __init__(self, cache_dir=".cache", model="ms-marco-MiniLM-L-12-v2"):
        from flashrank import Ranker
        self.cache_dir = Path(cache_dir) / "reranks"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.ranker = Ranker(model_name=model, cache_dir=str(Path(cache_dir) / "models"), max_length=384)
        # Avoid ONNX's default of starting a worker per host core on shared runners.
        import onnxruntime as ort
        from flashrank.Config import model_file_map
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.ranker.session = ort.InferenceSession(
            str(self.ranker.model_dir / model_file_map[model]), sess_options=options,
            providers=["CPUExecutionProvider"])

    def rank(self, question, passages):
        from flashrank import RerankRequest
        key = hashlib.sha256(json.dumps([self.model, 384, question, passages], ensure_ascii=False).encode()).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        results = []
        for start in range(0, len(passages), 12):
            batch = [{"id": i, "text": text} for i, text in passages[start:start + 12]]
            results.extend(self.ranker.rerank(RerankRequest(query=question, passages=batch)))
        ranked = sorted([(r["id"], float(r["score"])) for r in results], key=lambda r: (-r[1], r[0]))
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(ranked))
        tmp.replace(path)
        return ranked
