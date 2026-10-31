# Local models

All models run on the CPU inside the pipeline; none of them produces an answer. Reactor is the only model that answers.
Weights are not committed: each library downloads them on first use into `.cache/` (set `cache_dir` in
`memchal/retrieval.py` to move it). Pin versions with `requirements.txt`.

| Role | Model | Size | Loader | Source |
| --- | --- | --- | --- | --- |
| Session embeddings (semantic candidates) | `BAAI/bge-small-en-v1.5` (ONNX, quantized) | 33M | `fastembed.TextEmbedding` | https://huggingface.co/BAAI/bge-small-en-v1.5 |
| Excerpt reranking (default) | `ms-marco-MiniLM-L-12-v2` (ONNX) | 33M | `flashrank.Ranker`, `max_length=384` | https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-12-v2 |
| Excerpt reranking (`--reranker cross-encoder/ettin-reranker-68m-v1`) | `cross-encoder/ettin-reranker-68m-v1` (Apache-2.0, 2026) | 68M | `sentence_transformers.CrossEncoder`, `max_length=512`, CPU torch | https://huggingface.co/cross-encoder/ettin-reranker-68m-v1 |

The Ettin reranker needs `pip install -r requirements-ettin.txt` (CPU torch + sentence-transformers, ~700 MB of wheels).
On our dev-large holdout (38 answerable questions, 500 conversations per history) it put every gold conversation into
the packet for 89.5% of questions vs 86.8% with MiniLM, at the same speed; see `experiments/retrieval-ablations/`.

Embedding vectors are cached in `.cache/embeddings.sqlite` keyed by model name and text hash, reranker scores in
`.cache/reranks/` keyed by model, question and candidate texts, so repeated runs over the same history are fast.
