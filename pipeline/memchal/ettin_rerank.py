"""Local Ettin cross-encoder (cross-encoder/ettin-reranker-*-v1) with the same interface and cache as retrieval.Reranker."""
import hashlib
import json
from pathlib import Path


class EttinReranker:
    def __init__(self, cache_dir=".cache", model="cross-encoder/ettin-reranker-68m-v1", max_length=512):
        import torch
        from sentence_transformers import CrossEncoder
        torch.set_num_threads(2)
        self.cache_dir = Path(cache_dir) / "reranks"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model, self.max_length = model, max_length
        self.encoder = CrossEncoder(model, max_length=max_length, device="cpu",
                                    cache_folder=str(Path(cache_dir) / "models"))

    def rank(self, question, passages):
        key = hashlib.sha256(json.dumps([self.model, self.max_length, question, passages], ensure_ascii=False).encode()).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        scores = self.encoder.predict([(question, text) for _, text in passages], batch_size=16) if passages else []
        ranked = sorted([(i, float(s)) for (i, _), s in zip(passages, scores)], key=lambda r: (-r[1], r[0]))
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(ranked))
        tmp.replace(path)
        return ranked
