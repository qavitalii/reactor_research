"""Memory demo: add conversations, prepare them, ask questions. Run from the repo root: streamlit run app/app.py"""
from datetime import date, datetime, time as dtime
import html
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(ROOT))

import streamlit as st

from memchal import service

DEMO = Path(__file__).resolve().parent / "demo"
ACCENT = "#2f6f6a"
CSS = f"""
<style>
.block-container {{max-width: 46rem; padding-top: 3rem;}}
h1, h2, h3 {{font-weight: 600;}}
.step {{margin-top: 3rem; color: {ACCENT}; font-size: 1.35rem; font-weight: 600;}}
.step span {{display: inline-block; width: 1.9rem; height: 1.9rem; line-height: 1.9rem; margin-right: .6rem;
  text-align: center; border-radius: 50%; background: {ACCENT}; color: white; font-size: 1rem;}}
.answer {{font-size: 1.9rem; line-height: 1.35; margin: 1rem 0 1.2rem; font-weight: 500;}}
.calm {{color: #6b7280; font-weight: 400;}}
.asked {{color: #6b7280; margin-top: 2rem;}}
.card {{border-left: 4px solid {ACCENT}; padding: .2rem 0 .2rem 1.2rem; margin-bottom: 1rem;}}
.stButton > button[kind="primary"], .stDownloadButton > button {{background: {ACCENT}; border-color: {ACCENT}; color: white;}}
</style>
"""


def step(number, title):
    st.markdown(f'<div class="step"><span>{number}</span>{title}</div>', unsafe_allow_html=True)


def nice_date(value):
    return service.parse_date(value).strftime("%A %d %B %Y") if isinstance(value, str) else value.strftime("%d %b %Y")


def load_demo():
    histories = service.parse_histories_jsonl((DEMO / "histories.jsonl").read_bytes())
    questions = service.parse_questions((DEMO / "questions.jsonl").read_bytes())
    return histories, questions


def set_histories(histories, signature, demo_questions=None):
    st.session_state.update(histories=histories, signature=signature, indexes=None, single=None, batch=None,
                            demo_questions=demo_questions)


def show_card(result):
    """The answer card: the answer, the conversations it is based on, and Reactor's latency."""
    prediction, record = result["prediction"], result["record"]
    if prediction["abstain"]:
        st.markdown('<div class="card"><div class="answer calm">The conversations don\'t say that.</div></div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="card"><div class="answer">{html.escape(prediction["answer"])}</div></div>',
                    unsafe_allow_html=True)
    found = service.excerpts(record)
    cited = [found[c] for c in prediction["citations"] if c in found]
    if cited:
        st.markdown("**Based on these conversations:**")
        for c in cited:
            with st.expander(nice_date(c["date"])):
                st.text(c["text"])
    st.caption(f"Reactor answered in {result['seconds']:.0f} seconds.")


def show_batch(box, results, total, final):
    with box.container():
        for r in results:
            st.markdown(f'<div class="asked">{html.escape(r["record"]["question"])}</div>', unsafe_allow_html=True)
            show_card(r)
        if final and results:
            data = service.predictions_jsonl([r["prediction"] for r in results])
            label = "Download predictions.jsonl" if len(results) == total else "Download the answers so far"
            st.download_button(label, data, "predictions.jsonl", "application/json", type="primary")


st.set_page_config(page_title="Ask your conversations", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)
st.title("Ask your conversations")
st.write("Find what was said in months of chats, and get an answer you can check.")

# Step 1: add conversations
step(1, "Add your conversations")
files = st.file_uploader("Upload a chat export (.txt or .md) or a histories.jsonl file", accept_multiple_files=True,
                         type=["txt", "md", "jsonl", "json"], label_visibility="collapsed")
signature = tuple((f.name, f.size) for f in files)
if files and signature != st.session_state.get("signature"):
    try:
        set_histories(service.parse_uploads([(f.name, f.getvalue()) for f in files]), signature)
    except ValueError as exc:
        st.session_state.update(histories=None, signature=None, indexes=None)
        st.error(f"Sorry, that file could not be read: {exc}.")
if st.button("Try the demo conversations"):
    histories, questions = load_demo()
    set_histories(histories, "demo", questions)
histories = st.session_state.get("histories")
if histories:
    s = service.summarize(histories)
    st.success(f"{s['conversations']} conversations, {s['messages']} messages, "
               f"from {nice_date(s['first'])} to {nice_date(s['last'])}.")

# Step 2: prepare
step(2, "Prepare")
if not histories:
    st.caption("Add your conversations first.")
else:
    if st.session_state.get("indexes"):
        st.success("Your conversations are ready to be searched.")
    else:
        st.write("This lets the app find the right conversations quickly. It takes a few seconds to a minute. "
                 "The first time, it also downloads the search tools, which can take a few minutes.")
        if st.button("Prepare my conversations", type="primary"):
            bar, status = st.progress(0.0), st.empty()

            def progress(fraction, message):
                bar.progress(min(fraction, 1.0))
                status.write(message)

            try:
                st.session_state.indexes = service.prepare(histories, progress)
                st.rerun()
            except Exception as exc:
                st.error(f"Sorry, preparing failed: {exc}")

# Step 3: ask
step(3, "Ask")
indexes = st.session_state.get("indexes")
settings = service.reactor_settings()
if not indexes:
    st.caption("Prepare your conversations first.")
else:
    if not settings:
        st.info("Reactor is not connected, so questions cannot be answered yet. "
                "Ask whoever runs this app to set it up (see the README).")
    mode = st.radio("What would you like to do?", ["Ask one question", "Answer a list of questions"],
                    horizontal=True, label_visibility="collapsed")
    if mode == "Ask one question":
        ids = list(indexes)
        hid = ids[0] if len(ids) == 1 else st.selectbox(
            "Which collection?", ids, format_func=lambda h: f"{h} ({len(indexes[h].sessions)} conversations)")
        newest = max(indexes[hid].dates).date()
        question = st.text_input("Your question", placeholder="What is my cat's name?")
        as_of = st.date_input("As of", value=newest, key=f"asof-{hid}-{newest}",
                              help="Conversations after this day are ignored.")
        if st.button("Get the answer", type="primary", disabled=not (question.strip() and settings)):
            with st.spinner("Reactor is reading the excerpts… usually under 2 minutes."):
                try:
                    record = service.retrieve(indexes[hid], question.strip(),
                                              service.format_date(datetime.combine(as_of, dtime(23, 59))),
                                              "q_" + uuid.uuid4().hex[:12])
                    st.session_state.single = service.ask(record, settings)
                except Exception as exc:
                    st.session_state.single = None
                    st.error(f"Sorry, no answer this time: {exc}")
        if st.session_state.get("single"):
            show_card(st.session_state.single)
    else:
        demo_questions = st.session_state.get("demo_questions")
        uploaded = st.file_uploader("Upload questions.jsonl", type=["jsonl"])
        questions = None
        try:
            if uploaded:
                questions = service.parse_questions(uploaded.getvalue())
            elif demo_questions and st.checkbox("Use the demo questions", value=True):
                questions = demo_questions
        except ValueError as exc:
            st.error(f"Sorry, that file could not be read: {exc}.")
        if questions:
            if len(indexes) == 1:
                only = next(iter(indexes))
                questions = [q if q["history_id"] in indexes else {**q, "history_id": only} for q in questions]
            missing = [q["question_id"] for q in questions if q["history_id"] not in indexes]
            if missing:
                st.error(f"These questions belong to conversations you have not added: {', '.join(missing[:5])}.")
            else:
                st.write(f"{len(questions)} questions ready.")
        box = st.container()
        if questions and not missing and st.button("Answer all questions", type="primary", disabled=not settings):
            results, bar = [], st.progress(0.0, text=f"0 of {len(questions)} answered")
            for q in questions:
                bar.progress(len(results) / len(questions), text=f"{len(results)} of {len(questions)} answered. "
                             "Reactor is reading the excerpts… usually under 2 minutes each.")
                try:
                    record = service.retrieve(indexes[q["history_id"]], q["question"], q["question_date"], q["question_id"])
                    results.append(service.ask(record, settings))
                except Exception as exc:
                    st.error(f"Stopped at question {len(results) + 1}: {exc}")
                    break
                show_batch(box, results, len(questions), final=False)
            bar.progress(len(results) / len(questions), text=f"{len(results)} of {len(questions)} answered")
            st.session_state.batch = results
            show_batch(box, results, len(questions), final=True)
        elif st.session_state.get("batch") and questions:
            show_batch(box, st.session_state.batch, len(questions), final=True)

st.markdown("---")
st.caption("Answers are produced by Reactor from the excerpts shown; nothing else is used.")
