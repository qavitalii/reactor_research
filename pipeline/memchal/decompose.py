"""Two-part questions ("days between X and Y", "total cost of X and Y", "which came first, X or Y"): search each part
separately and give each part's best sessions the same packing weight as the whole question, so a strong match for
one part cannot crowd out the other. Search text only; the question sent to Reactor is unchanged."""
import re

PARTS = re.compile(r"\b(?:between|apart were|apart was|first,?|(?:cost|total|price|amount) of)\s+(?P<x>[^?]+?),?\s+(?:and|or)\s+(?P<y>[^?]+?)\??$",
                   re.I)


def parts(question):
    m = PARTS.search(question.strip())
    if not m:
        return []
    x, y = m.group("x").strip(" ,"), m.group("y").strip(" ,")
    if len(x.split()) < 2 or len(y.split()) < 1:
        return []
    return [x, y]


def rank_decomposed(index, question, question_date, reranker, candidates, semantic, **kwargs):
    chosen, scores = index.rank(question, question_date, reranker, candidates, semantic, **kwargs)
    subqueries = parts(question)
    if not subqueries or not scores:
        return chosen, scores
    top = max(scores.values())
    merged = dict(scores)
    for sub in subqueries:
        sub_chosen, sub_scores = index.rank(sub, question_date, reranker, candidates, semantic, **kwargs)
        if not sub_scores:
            continue
        scale = top / max(sub_scores.values())
        for i in sub_chosen:
            merged[i] = max(merged.get(i, 0.0), sub_scores[i] * scale)
    return sorted(merged, key=lambda i: (-merged[i], i)), merged
