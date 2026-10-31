# Recall

**Memory you can trace.** Find answers in conversation histories and open the original sources behind them.

Built by **Dealer Handshake** for the Reactive AI Memory Retrieval Challenge, START Warsaw × Poland Tech Week, October 30–31, 2026.

## Demo

[Open the Recall demo](https://d7evc6l18pol2.cloudfront.net/#ask)

The hosted prototype uses prepared fictional examples and keyword search for imported files. Live Reactor answering is available through the backend application described below.

## Repository

| Path | Contents |
| --- | --- |
| [`app/`](app/README.md) | Web interface, Streamlit app, sample conversations, and a mock Reactor server |
| [`pipeline/`](pipeline/README.md) | Retrieval and answer pipeline, official Reactor client, experiments, and tests |
| [`predictions.jsonl`](predictions.jsonl) | Submitted predictions: one answer, abstention flag, and source citations per question |
| [`idea/slides.pptx`](idea/slides.pptx) | Presentation slides |

## Final submission

The submitted file contains **146 predictions: 131 answers and 15 abstentions**. It includes a wider-retrieval rerun of 15 questions flagged during an audit of the raw histories. These are submission counts, not an accuracy score.

The [final-run report](pipeline/experiments/final-run/RESULT.md) describes the configuration, timing, rerun, and merge rules. Raw Reactor replies are included alongside the report. Predictions are preserved from the final research snapshot of October 31, 2026; the presentation has been corrected to reflect that run and distinguish development results from the unscored test submission.

## Run the web app

Use Python 3.11 or newer. From the repository root:

```sh
python3 -m venv .venv-app
.venv-app/bin/pip install -r app/requirements.txt
.venv-app/bin/python -m uvicorn memchal.api:app --app-dir pipeline --port 8787
```

Open [localhost:8787](http://127.0.0.1:8787). Add conversation files or try the included demo, prepare the search index, and ask a question. Local search models download on first use.

Answering requires `REACTOR_BASE_URL`, `REACTOR_AGENT_ID`, and `REACTOR_ACCESS_KEY` in the server environment. See the [Reactor setup instructions](pipeline/reactor/QUICKSTART.md) for connecting the real service.

To try the protocol without credentials, start the mock in a separate terminal:

```sh
.venv-app/bin/python app/mock_reactor.py 8766
```

Apply its three printed `export` commands in the app's terminal, then restart the web app. The mock returns prepared test answers; real answers require Reactor.

See [app setup](app/README.md), [HTTP API](app/API.md), and [pipeline commands](pipeline/README.md) for details. The full challenge datasets are not included; supply your own dataset directory when running the pipeline.

## Checks

```sh
.venv-app/bin/python -m pytest -q pipeline/tests
bash app/check_api.sh
```

The API check uses the local mock Reactor. The root `predictions.jsonl` is preserved from the submitted research run.
