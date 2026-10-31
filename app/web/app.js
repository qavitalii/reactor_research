"use strict";

const BUSY = "Reactor is reading the excerpts… usually under 2 minutes";
const NO_ANSWER = "The conversations don't say that.";
const $ = (id) => document.getElementById(id);
const state = { collection: null, job: null, newest: "", polling: null };

function show(el, on) { el.hidden = !on; }

function say(el, text) {
  el.textContent = text || "";
  show(el, Boolean(text));
}

function busy(el, text) {
  el.querySelector("span").textContent = text || "";
  show(el, Boolean(text));
}

function setBar(bar, fraction) {
  const pct = Math.max(0, Math.min(100, Math.round(fraction * 100)));
  bar.firstElementChild.style.width = pct + "%";
  bar.setAttribute("aria-valuenow", String(pct));
}

async function call(path, options) {
  let res;
  try {
    res = await fetch(path, options);
  } catch (err) {
    throw new Error("Could not reach the app. Is it still running?");
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail; } catch (err) { detail = ""; }
    if (typeof detail !== "string" || !detail) detail = "Something went wrong (" + res.status + ").";
    throw new Error(detail);
  }
  return res.json();
}

function niceDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  if (!m) return iso || "";
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function citationDate(text) {
  // Excerpt dates look like "2023/05/30 (Tue) 08:08".
  const m = /^(\d{4})\/(\d{2})\/(\d{2})/.exec(text || "");
  return m ? niceDate(m[1] + "-" + m[2] + "-" + m[3]) : (text || "");
}

function resetFrom(step) {
  if (state.polling) { clearTimeout(state.polling); state.polling = null; }
  state.job = null;
  if (step <= 2) {
    show($("prepare-check"), false);
    show($("prepare-bar"), false);
    say($("prepare-msg"), "");
    $("prepare-msg").classList.remove("bad");
    $("prepare-btn").disabled = !state.collection;
    $("prepare-btn").textContent = "Prepare my conversations";
    $("prepare-hint").textContent = state.collection ? "This lets the app find the right conversations quickly. The first time it can take a few minutes." : "Add your conversations first.";
  }
  show($("ask-form"), false);
  show($("batch"), false);
  $("ask-hint").textContent = "Prepare your conversations first.";
  show($("ask-hint"), true);
  $("answer").replaceChildren();
  $("batch-results").replaceChildren();
  say($("ask-error"), "");
  say($("batch-error"), "");
  show($("download"), false);
  show($("batch-bar"), false);
  busy($("ask-busy"), "");
  busy($("batch-busy"), "");
}

function added(info) {
  state.collection = info.collection_id;
  state.newest = info.date_to;
  $("as-of").value = info.date_to;
  say($("add-error"), "");
  say($("add-summary"), info.conversations + " conversations · " + info.messages + " messages · from " +
    niceDate(info.date_from) + " to " + niceDate(info.date_to));
  resetFrom(2);
}

async function upload(files) {
  if (!files.length) return;
  const form = new FormData();
  for (const f of files) form.append("files", f, f.name);
  say($("add-summary"), "");
  try {
    added(await call("/collections", { method: "POST", body: form }));
  } catch (err) {
    state.collection = null;
    resetFrom(2);
    say($("add-error"), err.message);
  }
}

async function loadDemo() {
  say($("add-summary"), "");
  try {
    added(await call("/collections?demo=1", { method: "POST" }));
  } catch (err) {
    say($("add-error"), err.message);
  }
}

function pollStatus(id) {
  call("/collections/" + id + "/status").then((s) => {
    if (id !== state.collection) return;
    setBar($("prepare-bar"), s.progress);
    say($("prepare-msg"), s.message);
    if (s.state === "ready") {
      show($("prepare-check"), true);
      $("prepare-btn").textContent = "Ready";
      $("prepare-hint").textContent = "Your conversations are ready to be searched.";
      show($("ask-hint"), false);
      show($("ask-form"), true);
      show($("batch"), true);
    } else if (s.state === "error") {
      $("prepare-btn").disabled = false;
      $("prepare-btn").textContent = "Try again";
      $("prepare-msg").classList.add("bad");
    } else {
      state.polling = setTimeout(() => pollStatus(id), 1000);
    }
  }).catch((err) => {
    say($("prepare-msg"), err.message);
    state.polling = setTimeout(() => pollStatus(id), 3000);
  });
}

async function prepare() {
  const id = state.collection;
  if (!id) return;
  $("prepare-btn").disabled = true;
  $("prepare-msg").classList.remove("bad");
  show($("prepare-bar"), true);
  setBar($("prepare-bar"), 0);
  say($("prepare-msg"), "Starting…");
  try {
    await call("/collections/" + id + "/prepare", { method: "POST" });
    pollStatus(id);
  } catch (err) {
    $("prepare-btn").disabled = false;
    say($("prepare-msg"), err.message);
  }
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function card(result, withQuestion) {
  const box = el("div", "card");
  if (withQuestion) box.appendChild(el("div", "q", result.question));
  box.appendChild(result.abstain ? el("div", "answer calm", NO_ANSWER) : el("div", "answer", result.answer));
  if (result.citations && result.citations.length) {
    const list = el("div", "sources");
    list.appendChild(el("strong", "", "Based on these conversations:"));
    for (const c of result.citations) {
      const d = el("details");
      d.appendChild(el("summary", "", citationDate(c.date)));
      d.appendChild(el("pre", "", c.excerpt));
      list.appendChild(d);
    }
    box.appendChild(list);
  }
  if (typeof result.latency_s === "number") {
    box.appendChild(el("div", "latency", "Reactor answered in " + Math.round(result.latency_s) + " seconds."));
  }
  return box;
}

async function ask(event) {
  event.preventDefault();
  const question = $("question").value.trim();
  if (!question || !state.collection) return;
  $("ask-btn").disabled = true;
  say($("ask-error"), "");
  $("answer").replaceChildren();
  busy($("ask-busy"), BUSY);
  try {
    const result = await call("/collections/" + state.collection + "/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, question_date: $("as-of").value || null }),
    });
    $("answer").replaceChildren(card(result, false));
  } catch (err) {
    say($("ask-error"), err.message);
  } finally {
    busy($("ask-busy"), "");
    $("ask-btn").disabled = false;
  }
}

function renderBatch(job) {
  const answered = job.results.length;
  $("batch-results").replaceChildren(...job.results.map((r) => card(r, true)));
  setBar($("batch-bar"), job.total ? answered / job.total : 0);
  if (job.done) {
    busy($("batch-busy"), "");
    const link = $("download");
    link.href = "/jobs/" + state.job + "/predictions.jsonl";
    show(link, true);
    say($("batch-error"), "");
    return;
  }
  if (job.state === "error") {
    busy($("batch-busy"), "");
    say($("batch-error"), job.message);
    if (answered) { $("download").href = "/jobs/" + state.job + "/predictions.jsonl"; $("download").textContent = "Download the answers so far"; show($("download"), true); }
    return;
  }
  busy($("batch-busy"), answered + " of " + job.total + " answered. " + BUSY + " each.");
  state.polling = setTimeout(pollJob, 1000);
}

function pollJob() {
  const job = state.job;
  call("/jobs/" + job).then((data) => {
    if (job === state.job) renderBatch(data);
  }).catch((err) => {
    say($("batch-error"), err.message);
    state.polling = setTimeout(pollJob, 3000);
  });
}

async function startBatch(files) {
  if (!files.length || !state.collection) return;
  const form = new FormData();
  form.append("file", files[0], files[0].name);
  say($("batch-error"), "");
  $("batch-results").replaceChildren();
  $("download").textContent = "Download predictions.jsonl";
  show($("download"), false);
  show($("batch-bar"), true);
  setBar($("batch-bar"), 0);
  busy($("batch-busy"), "Starting…");
  try {
    const started = await call("/collections/" + state.collection + "/batch", { method: "POST", body: form });
    state.job = started.job_id;
    pollJob();
  } catch (err) {
    busy($("batch-busy"), "");
    show($("batch-bar"), false);
    say($("batch-error"), err.message);
  }
}

function wireDrop(label, onFiles) {
  const input = label.querySelector("input");
  input.addEventListener("change", () => { onFiles(Array.from(input.files)); input.value = ""; });
  label.addEventListener("dragover", (e) => { e.preventDefault(); label.classList.add("over"); });
  label.addEventListener("dragleave", () => label.classList.remove("over"));
  label.addEventListener("drop", (e) => {
    e.preventDefault();
    label.classList.remove("over");
    onFiles(Array.from(e.dataTransfer.files));
  });
}

document.addEventListener("DOMContentLoaded", () => {
  wireDrop($("drop"), upload);
  wireDrop(document.querySelector("label[for=batch-input]"), startBatch);
  $("demo-btn").addEventListener("click", loadDemo);
  $("prepare-btn").addEventListener("click", prepare);
  $("ask-form").addEventListener("submit", ask);
  resetFrom(2);
});
