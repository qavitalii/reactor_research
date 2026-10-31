#!/bin/sh
set -eu
cd "$(dirname "$0")"
ROOT=$(cd ../.. && pwd)
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  export OLLAMA_MODELS="$ROOT/.cache/ollama-models"
  export OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1
  "$ROOT/.cache/ollama-runtime/ollama" serve >"$ROOT/.cache/recall-ollama.log" 2>&1 &
  MODEL_PID=$!
  trap 'kill "$MODEL_PID" 2>/dev/null || true' EXIT INT TERM
  sleep 2
fi
RECALL_RUNTIME="$ROOT/.cache/ollama-runtime/ollama"
if [ ! -x "$RECALL_RUNTIME" ]; then RECALL_RUNTIME=ollama; fi
export OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1
for RECALL_REQUIRED_MODEL in "${RECALL_MODEL:-qwen3:4b-instruct}" "${RECALL_EMBED_MODEL:-qwen3-embedding:4b}"; do
  if ! "$RECALL_RUNTIME" show "$RECALL_REQUIRED_MODEL" >/dev/null 2>&1; then
    "$RECALL_RUNTIME" pull "$RECALL_REQUIRED_MODEL"
  fi
done
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import pypdf' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python server.py
