"""
ResearchMind — Full Power Edition
Streamlit front-end for a multi-agent research system.

Run:  streamlit run app.py

agents.py must export:
    build_search_agent, build_reader_agent, writer_chain, critic_chain
Optional (enables extra features):
    llm           -> an LLM object with .invoke() for follow-up chat
    get_llm(name) -> factory to switch models from the sidebar
"""

import base64
import csv
import hashlib
import html
import io
import json
import os
import random
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path
from string import Template
from urllib.parse import urlparse

import streamlit as st

import agents as _agents
from agents import build_reader_agent, build_search_agent, writer_chain, critic_chain

# ============================================================================
# Page config
# ============================================================================
st.set_page_config(
    page_title="ResearchMind",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "https://docs.streamlit.io",
        "Report a bug": "https://github.com/streamlit/streamlit/issues",
        "About": (
            "**ResearchMind — Full Power Edition**\n\n"
            "A multi-agent AI research system (Search → Read → Write → Critique) "
            "built with LangChain, Groq and Streamlit."
        ),
    },
)

HISTORY_DIR = Path(__file__).resolve().parent / "research_history"
HISTORY_DIR.mkdir(exist_ok=True)

PRESETS_FILE = HISTORY_DIR / "_presets.json"
TAGS_FILE = HISTORY_DIR / "_tags.json"

EXAMPLE_TOPICS = [
    "LLM agents 2025",
    "CRISPR gene editing",
    "Fusion energy progress",
    "Quantum computing breakthroughs",
    "Future of UX research with AI",
    "Solid-state battery technology",
    "AI in drug discovery 2025",
    "Room-temperature superconductors",
    "Neuromorphic computing chips",
    "Vertical farming economics",
]

TEMPLATES = {
    "None": "",
    "Compare A vs B": "Compare and contrast, with a side-by-side table of pros and cons.",
    "Pros / Cons": "Structure the report with clear Pros and Cons sections followed by a verdict.",
    "Timeline": "Present findings as a chronological timeline with dated milestones.",
    "ELI5": "Explain the topic as if to a smart 12-year-old, with concrete analogies.",
    "Executive brief": "Write a 300-word executive summary followed by 5 key takeaways.",
    "SWOT": "Structure the report as a SWOT analysis (Strengths/Weaknesses/Opportunities/Threats).",
}

STEPS = [
    ("01", "Search Agent", "Gathers recent web information"),
    ("02", "Reader Agent", "Scrapes & extracts deep content"),
    ("03", "Writer Chain", "Drafts the full research report"),
    ("04", "Critic Chain", "Reviews & scores the report"),
]
STATUS_LABEL = {
    "waiting": "WAITING", "running": "RUNNING", "done": "DONE",
    "failed": "FAILED", "skipped": "SKIPPED", "paused": "PAUSED",
}

DEPTHS = ["Brief", "Standard", "Detailed"]
TONES = ["Professional", "Academic", "Conversational", "Executive summary", "Explain like I'm 12"]
LANGUAGES = ["English", "Hindi", "Spanish", "French", "German", "Portuguese", "Japanese", "Arabic",
             "Chinese (Simplified)", "Russian", "Korean", "Italian", "Dutch", "Turkish"]
FOCUSES = ["Balanced", "Latest news", "Academic & research", "Industry & business",
           "Official docs & sources", "Opinion & analysis"]

DEFAULTS = {
    "opt_depth": "Standard",
    "opt_tone": "Professional",
    "opt_lang": "English",
    "opt_focus": "Balanced",
    "opt_extra": "",
    "opt_template": "None",
    "opt_delay": 1.5,
    "opt_retries": 1,
    "opt_ctx": 800,
    "opt_critic": True,
    "opt_batch": False,
    "opt_compare": False,
    "opt_topic2": "",
    "opt_autoscroll": True,
    "opt_cost": 0.0,
}

# ============================================================================
# Session state
# ============================================================================
for _k, _v in DEFAULTS.items():
    st.session_state.setdefault(_k, _v)
st.session_state.setdefault("theme_choice", "Dark")
st.session_state.setdefault("topic_input", "")
st.session_state.setdefault("result", None)
st.session_state.setdefault("meta", None)
st.session_state.setdefault("chat", [])
st.session_state.setdefault("chat_for", None)
st.session_state.setdefault("prev_result", None)
st.session_state.setdefault("prev_meta", None)
st.session_state.setdefault("metrics", {"runs": 0, "words": 0, "seconds": 0.0, "tokens_est": 0})
st.session_state.setdefault("show_help", False)

# ============================================================================
# Theme
# ============================================================================
THEMES = {
    "dark": dict(
        bg="#0a0a0e", bg2="#0d0d12", card="#111116", border="#1f1f27",
        text="#ece8df", body="#d8d4ca", muted="#8b8b96", input="#1b1b21",
        input_border="#2a2a33", orange="#ff8a1f", orange2="#ff6a00",
        glow="rgba(255,138,31,0.10)", btn_text="#1a0d00", chip="#14141a",
        chip_border="#25252d", chip_text="#c9c5bb", divider="#2b2b33",
        ok="#22c55e", warn="#eab308", err="#ef4444",
    ),
    "light": dict(
        bg="#f6f3ec", bg2="#efebe2", card="#ffffff", border="#e3ded2",
        text="#1b1a17", body="#2b2a26", muted="#6e6a60", input="#ffffff",
        input_border="#d8d3c6", orange="#e8710a", orange2="#d45f00",
        glow="rgba(232,113,10,0.10)", btn_text="#ffffff", chip="#ffffff",
        chip_border="#ddd8cb", chip_text="#3a382f", divider="#d9d4c7",
        ok="#15803d", warn="#a16207", err="#b91c1c",
    ),
}


def resolve_theme() -> str:
    choice = st.session_state.get("theme_choice", "Dark")
    if choice == "Dark":
        return "dark"
    if choice == "Light":
        return "light"
    try:
        return "light" if st.context.theme.type == "light" else "dark"
    except Exception:
        return "dark"


CSS = Template("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@800&family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
:root {
  --bg:$bg; --bg2:$bg2; --card:$card; --border:$border; --text:$text; --body:$body;
  --muted:$muted; --input:$input; --input-border:$input_border; --orange:$orange;
  --orange-2:$orange2; --btn-text:$btn_text; --chip:$chip; --chip-border:$chip_border;
  --chip-text:$chip_text; --divider:$divider; --ok:$ok; --warn:$warn; --err:$err;
}
.stApp {
  background: radial-gradient(ellipse 60% 35% at 20% 0%, $glow, transparent 70%), var(--bg);
  color: var(--text); font-family: 'DM Sans', sans-serif;
}
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1280px; padding: 2.2rem 2rem 5rem; }

.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
[data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] { color: var(--body); }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--muted); }
.stMarkdown a, a { color: var(--orange); }

.hero { text-align: center; margin-bottom: .8rem; }
.hero .eyebrow { font-family:'JetBrains Mono',monospace; font-size:.72rem; letter-spacing:.35em;
  color: var(--orange); margin-bottom: 1rem; }
.hero .title { font-family:'Syne',sans-serif; font-weight:800;
  font-size: clamp(2.2rem, 5vw, 4.4rem); line-height:1.05; letter-spacing:-.03em;
  color: var(--text); white-space: nowrap; }
.hero .title .accent { color: var(--orange); }
.hero p.sub { max-width: 620px; margin: 1.2rem auto 0; color: var(--muted); font-size:1rem; line-height:1.7; }
.divider { height:1px; margin: 1.8rem 0; background: linear-gradient(90deg, transparent, var(--divider), transparent); }

.label { font-family:'JetBrains Mono',monospace; font-size:.72rem; line-height:1; letter-spacing:.2em;
  color: var(--orange); margin: 0 0 .8rem 0; height: .9rem; }
.label.muted { color: var(--muted); letter-spacing:.25em; margin-top: 1.6rem; }
.label.free { height:auto; }

.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div, [data-baseweb="input"] {
  background: var(--input) !important; color: var(--text) !important;
  border: 1px solid var(--input-border) !important; border-radius: 8px !important;
}
.stTextInput input, .stTextArea textarea { padding:.75rem 1rem !important; font-size:1rem !important; }
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--orange) !important; box-shadow: 0 0 0 1px var(--orange) !important; }
::placeholder { color: var(--muted) !important; opacity: .7 !important; }
[data-baseweb="select"] *, [data-baseweb="popover"] li, [data-baseweb="menu"] li { color: var(--text) !important; }
[data-baseweb="popover"] ul, [data-baseweb="menu"] { background: var(--card) !important; }
[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }

button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"],
button[kind="primary"], button[kind="primaryFormSubmit"] {
  width:100% !important; background: linear-gradient(180deg, var(--orange), var(--orange-2)) !important;
  color: var(--btn-text) !important; border:none !important; border-radius:8px !important;
  font-weight:600 !important; padding:.7rem 1rem !important;
  box-shadow: 0 6px 24px rgba(255,122,0,.25) !important; transition: transform .15s, box-shadow .15s;
}
button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
  transform: translateY(-1px); box-shadow: 0 8px 30px rgba(255,122,0,.4) !important; }
button[data-testid="stBaseButton-primary"] p, button[data-testid="stBaseButton-primaryFormSubmit"] p,
button[kind="primary"] p, button[kind="primaryFormSubmit"] p { color: var(--btn-text) !important; }
button[data-testid="stBaseButton-secondary"], button[kind="secondary"],
[data-testid="stDownloadButton"] button {
  background: var(--chip) !important; color: var(--chip-text) !important;
  border: 1px solid var(--chip-border) !important; border-radius: 6px !important;
  font-size:.8rem !important; padding:.3rem .8rem !important; min-height:0 !important; }
button[data-testid="stBaseButton-secondary"] p, [data-testid="stDownloadButton"] button p { color: var(--chip-text) !important; }
button[data-testid="stBaseButton-secondary"]:hover, button[kind="secondary"]:hover,
[data-testid="stDownloadButton"] button:hover { border-color: var(--orange) !important; }
button[data-testid="stBaseButton-secondary"]:hover p, [data-testid="stDownloadButton"] button:hover p { color: var(--orange) !important; }

.step-card { display:flex; justify-content:space-between; align-items:flex-start; background: var(--card);
  border:1px solid var(--border); border-radius:12px; padding:1rem 1.2rem; margin-bottom:.8rem; transition: all .25s; }
.step-card .num { font-family:'JetBrains Mono',monospace; font-size:.7rem; color: var(--orange); margin-right:.8rem; }
.step-card .name { font-weight:600; color: var(--text); font-size:1rem; }
.step-card .desc { color: var(--muted); font-size:.82rem; margin-top:.5rem; }
.step-card .badge { font-family:'JetBrains Mono',monospace; font-size:.62rem; letter-spacing:.18em;
  color: var(--muted); padding-top:.2rem; white-space: nowrap; }
.step-card.running { border-color: var(--orange); animation: pulse 1.4s ease-in-out infinite; }
.step-card.running .badge { color: var(--orange); }
.step-card.done { border-color: rgba(74,222,128,.45); } .step-card.done .badge { color: var(--ok); }
.step-card.failed { border-color: rgba(248,113,113,.6); } .step-card.failed .badge { color: var(--err); }
.step-card.skipped { opacity:.55; }
.step-card.paused { border-color: var(--warn); } .step-card.paused .badge { color: var(--warn); }
@keyframes pulse { 0%,100% { box-shadow:0 0 0 1px rgba(255,138,31,.3), 0 0 20px rgba(255,138,31,.10);}
                   50% { box-shadow:0 0 0 1px rgba(255,138,31,.6), 0 0 32px rgba(255,138,31,.28);} }

.stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap:.8rem; margin: .5rem 0 1.2rem; }
.stat { background: var(--card); border:1px solid var(--border); border-radius:10px; padding:.8rem 1rem; }
.stat .v { font-size:1.4rem; font-weight:600; color: var(--text); }
.stat .v.accent { color: var(--orange); }
.stat .k { font-family:'JetBrains Mono',monospace; font-size:.62rem; letter-spacing:.15em; color: var(--muted); margin-top:.2rem; }

.src { display:block; background: var(--card); border:1px solid var(--border); border-radius:10px;
  padding:.7rem 1rem; margin-bottom:.6rem; text-decoration:none !important; }
.src:hover { border-color: var(--orange); }
.src .d { font-weight:600; color: var(--text); font-size:.9rem; }
.src .u { color: var(--muted); font-size:.75rem; word-break: break-all; }
.src .n { font-family:'JetBrains Mono',monospace; color: var(--orange); font-size:.7rem; margin-right:.4rem; }

.stTabs [data-baseweb="tab-list"] { gap:1.2rem; border-bottom:1px solid var(--border); flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] { background: transparent; }
.stTabs [data-baseweb="tab"] p { color: var(--muted); }
.stTabs [aria-selected="true"] p { color: var(--orange) !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--orange) !important; }
.stTabs [data-baseweb="tab-border"] { display:none; }
[data-testid="stExpander"] { background: var(--card); border:1px solid var(--border) !important; border-radius:10px; }
[data-testid="stExpander"] summary p { color: var(--text) !important; }
section[data-testid="stSidebar"] { background: var(--bg2); border-right:1px solid var(--border); }
section[data-testid="stSidebar"] .brand { font-family:'Syne',sans-serif; font-weight:800; font-size:1.3rem; color: var(--text); letter-spacing:-.02em; white-space: nowrap; }
section[data-testid="stSidebar"] .brand span { color: var(--orange); }
[data-testid="stChatMessage"] { background: var(--card); border:1px solid var(--border); border-radius:10px; }
[data-testid="stCodeBlock"] pre, .stCodeBlock pre { background: var(--card) !important; }

.toc { background: var(--card); border:1px solid var(--border); border-radius:10px; padding:.8rem 1rem; }
.toc a { display:block; padding:.15rem 0; text-decoration:none; color: var(--body); font-size:.88rem; }
.toc a:hover { color: var(--orange); }
.toc a.l2 { padding-left:1rem; font-size:.82rem; opacity:.9; }
.toc a.l3 { padding-left:2rem; font-size:.78rem; opacity:.8; }

.badge-pill { display:inline-block; padding:.15rem .6rem; border-radius:999px;
  font-family:'JetBrains Mono',monospace; font-size:.62rem; letter-spacing:.1em;
  background: var(--chip); border:1px solid var(--chip-border); color: var(--chip-text); margin-right:.3rem; }
.badge-pill.ok { color: var(--ok); border-color: var(--ok); }
.badge-pill.warn { color: var(--warn); border-color: var(--warn); }

.diff-add { background: rgba(34,197,94,.14); color: var(--ok); padding:0 .3rem; border-radius:3px; }
.diff-del { background: rgba(239,68,68,.14); color: var(--err); padding:0 .3rem; border-radius:3px; text-decoration: line-through; }
</style>
""")

st.markdown(CSS.substitute(**THEMES[resolve_theme()]), unsafe_allow_html=True)

# ============================================================================
# Helpers
# ============================================================================
def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "research"

URL_RE = re.compile(r"https?://[^\s<>\"'\)\]]+")

def extract_sources(*texts: str) -> list[str]:
    seen, out = set(), []
    for t in texts:
        for u in URL_RE.findall(t or ""):
            u = u.rstrip(".,;:!?*")
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def critic_score(feedback: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", feedback or "")
    if m and float(m.group(1)) <= 10:
        return m.group(1)
    return None


def fmt_secs(s: float) -> str:
    return f"{s:.0f}s" if s < 100 else f"{int(s // 60)}m {int(s % 60)}s"


def stats_html(items):
    return '<div class="stats">' + "".join(
        f'<div class="stat"><div class="v{" accent" if acc else ""}">{html.escape(str(v))}</div>'
        f'<div class="k">{html.escape(k)}</div></div>'
        for k, v, acc in items
    ) + "</div>"


def get_llm(model=None):
    if model:
        factory = getattr(_agents, "get_llm", None)
        if callable(factory):
            try:
                return factory(model)
            except Exception:
                pass
    for name in ("llm", "model", "chat_model", "llm_model"):
        if hasattr(_agents, name):
            return getattr(_agents, name)
    return None


def list_models() -> list[str]:
    factory = getattr(_agents, "list_models", None)
    if callable(factory):
        try:
            return list(factory())
        except Exception:
            pass
    return [
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ]


def estimate_tokens(*texts: str) -> int:
    return sum(max(1, len(t or "") // 4) for t in texts)


def to_html_doc(topic: str, report_md: str, feedback_md: str) -> str:
    try:
        from markdown_it import MarkdownIt
        md = MarkdownIt("commonmark").enable("table")
        body, fb = md.render(report_md), md.render(feedback_md)
    except Exception:
        body = f"<pre>{html.escape(report_md)}</pre>"
        fb = f"<pre>{html.escape(feedback_md)}</pre>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{html.escape(topic)}</title>
<style>
@page{{margin:20mm}}
body{{font-family:Georgia,serif;max-width:780px;margin:3rem auto;padding:0 1.2rem;line-height:1.7;color:#222}}
h1,h2,h3{{font-family:system-ui,sans-serif}} h1{{border-bottom:3px solid #ff8a1f;padding-bottom:.3rem}}
.fb{{background:#faf6ef;border-left:4px solid #ff8a1f;padding:.5rem 1.2rem;margin-top:3rem}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ddd;padding:.4rem .7rem}}
code{{background:#f4f4f4;padding:0 .2rem}}
</style></head><body>
<h1>{html.escape(topic)}</h1>{body}
<div class="fb"><h2>Critic feedback</h2>{fb}</div>
</body></html>"""


def copy_button(text: str, key: str, label: str = "📋 Copy"):
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    js = f"""
    <button onclick='navigator.clipboard.writeText(atob("{b64}"));this.innerText="✅ Copied";'
    style='background:#1b1b21;border:1px solid #2a2a33;border-radius:6px;padding:.3rem .8rem;
    color:#c9c5bb;font-family:DM Sans,sans-serif;cursor:pointer;font-size:.8rem'>{label}</button>
    """
    st.markdown(js, unsafe_allow_html=True)


# ============================================================================
# Persistence: presets, tags
# ============================================================================
def load_presets() -> dict:
    try:
        return json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_presets(d: dict):
    PRESETS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def load_tags() -> dict:
    try:
        return json.loads(TAGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_tags(d: dict):
    TAGS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================================
# Prompt shaping
# ============================================================================
def collect_opts() -> dict:
    return {k: st.session_state[k] for k in DEFAULTS}


def search_prompt(topic: str, o: dict) -> str:
    p = f"Find recent, reliable and detailed information about: {topic}"
    if o["opt_focus"] != "Balanced":
        p += f"\nPrioritise sources about: {o['opt_focus'].lower()}."
    return p


def writer_topic(topic: str, o: dict) -> str:
    notes = []
    if o["opt_depth"] == "Brief":
        notes.append("Keep the report brief (roughly 400 words).")
    elif o["opt_depth"] == "Detailed":
        notes.append("Write a detailed, in-depth report (1500+ words) with clear sections.")
    if o["opt_tone"] != "Professional":
        notes.append(f"Use this tone/style: {o['opt_tone']}.")
    if o["opt_lang"] != "English":
        notes.append(f"Write the entire report in {o['opt_lang']}.")
    tpl = TEMPLATES.get(o.get("opt_template", "None"), "")
    if tpl:
        notes.append(tpl)
    if o["opt_extra"].strip():
        notes.append(o["opt_extra"].strip())
    if not notes:
        return topic
    return f"{topic}\n\nAdditional instructions for the report: " + " ".join(notes)


# ============================================================================
# Pipeline tracker + engine
# ============================================================================
def pipeline_html(statuses, times, progress: float = None) -> str:
    cards = []
    for (num, name, desc), s, t in zip(STEPS, statuses, times):
        label = STATUS_LABEL[s]
        if t is not None and s in ("done", "failed"):
            label += f" · {t:.1f}s"
        cards.append(
            f'<div class="step-card {s}"><div><div><span class="num">{num}</span>'
            f'<span class="name">{html.escape(name)}</span></div>'
            f'<div class="desc">{html.escape(desc)}</div></div>'
            f'<div class="badge">{label}</div></div>'
        )
    body = "".join(cards)
    if progress is not None:
        pct = max(0, min(100, progress * 100))
        body += (
            f'<div style="margin-top:.6rem">'
            f'<div style="height:6px;background:var(--border);border-radius:3px;overflow:hidden">'
            f'<div style="height:100%;width:{pct:.0f}%;background:linear-gradient(90deg,'
            f'var(--orange),var(--orange-2));transition:width .3s"></div></div>'
            f'<div style="font-family:JetBrains Mono,monospace;font-size:.62rem;'
            f'letter-spacing:.15em;color:var(--muted);margin-top:.35rem">PROGRESS {pct:.0f}%</div></div>'
        )
    return body


class Tracker:
    def __init__(self, cards_box, log_box, total_hint: float = 60.0):
        self.cards_box, self.log_box = cards_box, log_box
        self.status = ["waiting"] * 4
        self.times = [None] * 4
        self.logs: list[str] = []
        self.t0 = time.time()
        self.total_hint = total_hint
        self.render()

    def _progress(self):
        done = sum(1 for s in self.status if s in ("done", "skipped", "failed"))
        if done == 0:
            elapsed = time.time() - self.t0
            return min(0.3, elapsed / max(1.0, self.total_hint * 3))
        return done / 4.0

    def render(self):
        self.cards_box.markdown(pipeline_html(self.status, self.times, self._progress()),
                                unsafe_allow_html=True)

    def set(self, i, status, elapsed=None):
        self.status[i] = status
        if elapsed is not None:
            self.times[i] = elapsed
        self.render()

    def log(self, msg: str):
        self.logs.append(f"[{datetime.now():%H:%M:%S}] {msg}")
        self.log_box.code("\n".join(self.logs[-120:]), language="text")


def call_with_retry(fn, retries: int, label: str, log=None):
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as e:
            if attempt >= retries:
                raise
            wait = 2 * (2 ** attempt)
            if log:
                log(f"{label} failed ({e}); retrying in {wait}s [{attempt + 1}/{retries}]")
            time.sleep(wait)
            attempt += 1


def run_step(tr: Tracker, i: int, label: str, fn, retries: int):
    tr.set(i, "running")
    tr.log(f"{label}: started")
    t0 = time.time()
    try:
        out = call_with_retry(fn, retries, label, tr.log)
    except Exception as e:
        tr.set(i, "failed", time.time() - t0)
        tr.log(f"{label}: FAILED - {e}")
        raise
    el = time.time() - t0
    tr.set(i, "done", el)
    tr.log(f"{label}: done in {el:.1f}s")
    return out


def execute(topic: str, o: dict, tr: Tracker, resume_state: dict | None = None) -> dict | None:
    state = dict(resume_state) if resume_state else {}
    t_start = time.time()
    delay, retries = float(o["opt_delay"]), int(o["opt_retries"])

    if state:
        for i, key in enumerate(["search_results", "scraped_content", "report", "feedback"]):
            if key in state and state.get(key):
                tr.set(i, "done", tr.times[i])
        tr.log("Resuming from saved state…")

    try:
        if not state.get("search_results"):
            def do_search():
                agent = build_search_agent()
                r = agent.invoke({"messages": [("user", search_prompt(topic, o))]})
                return str(r["messages"][-1].content)
            state["search_results"] = run_step(tr, 0, "Search agent", do_search, retries)
            time.sleep(delay)

        if not state.get("scraped_content"):
            def do_read():
                agent = build_reader_agent()
                r = agent.invoke({"messages": [("user",
                    f"Based on the following search results about '{topic}', "
                    f"pick the most relevant URL and scrape it for deeper content.\n\n"
                    f"Search Results:\n{state['search_results'][: int(o['opt_ctx'])]}")]})
                return str(r["messages"][-1].content)
            state["scraped_content"] = run_step(tr, 1, "Reader agent", do_read, retries)
            time.sleep(delay)

        if not state.get("report"):
            def do_write():
                research = (f"SEARCH RESULTS :\n {state['search_results']}\n\n"
                            f"DETAILED SCRAPED CONTENT : \n {state['scraped_content']}")
                return str(writer_chain.invoke({"topic": writer_topic(topic, o), "research": research}))
            state["report"] = run_step(tr, 2, "Writer chain", do_write, retries)

        if o["opt_critic"] and not state.get("feedback"):
            time.sleep(delay)
            state["feedback"] = run_step(
                tr, 3, "Critic chain",
                lambda: str(critic_chain.invoke({"report": state["report"]})), retries)
        elif not o["opt_critic"]:
            state["feedback"] = state.get("feedback") or "_Critic step was skipped (disabled in settings)._"
            tr.set(3, "skipped")
            tr.log("Critic chain: skipped")

    except Exception as e:
        failed = next((STEPS[i][1] for i, s in enumerate(tr.status) if s == "failed"), "pipeline")
        st.error(f"Pipeline failed at **{failed}**: {e}")
        st.session_state["_failed_state"] = state
        st.session_state["_failed_topic"] = topic
        return None

    meta = {
        "topic": topic,
        "created": datetime.now().isoformat(timespec="seconds"),
        "times": tr.times,
        "total": time.time() - t_start,
        "opts": o,
    }
    save_run(state, meta)

    if st.session_state.result:
        st.session_state.prev_result = st.session_state.result
        st.session_state.prev_meta = st.session_state.meta

    st.session_state.result, st.session_state.meta = state, meta
    st.session_state.chat, st.session_state.chat_for = [], meta["created"]
    st.session_state["_failed_state"] = None

    m = st.session_state.metrics
    m["runs"] += 1
    m["words"] += len(state["report"].split())
    m["seconds"] += meta["total"]
    m["tokens_est"] += estimate_tokens(state["report"], state.get("search_results", ""),
                                       state.get("scraped_content", ""))
    return state


# ============================================================================
# History
# ============================================================================
def save_run(state: dict, meta: dict):
    name = f"{datetime.now():%Y%m%d-%H%M%S}__{slugify(meta['topic'])}.json"
    (HISTORY_DIR / name).write_text(
        json.dumps({"meta": meta, "state": state}, ensure_ascii=False, indent=2), encoding="utf-8")
    meta["file"] = name
    list_history.clear()


@st.cache_data(show_spinner=False)
def list_history(_stamp: float = 0.0) -> list[dict]:
    tags = load_tags()
    rows = []
    for f in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            m = data["meta"]
            report = data.get("state", {}).get("report", "")
            fb = data.get("state", {}).get("feedback", "")
            rows.append({
                "file": f.name,
                "topic": m["topic"],
                "created": m["created"],
                "words": len(report.split()) if report else 0,
                "score": critic_score(fb),
                "tags": tags.get(f.name, []),
                "snippet": (report or "")[:500],
            })
        except Exception:
            continue
    return rows


def history_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in HISTORY_DIR.glob("*.json"):
            if not f.name.startswith("_"):
                z.write(f, f.name)
    return buf.getvalue()


def history_csv() -> bytes:
    rows = list_history(HISTORY_DIR.stat().st_mtime)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["file", "topic", "created", "words", "score", "tags"])
    for r in rows:
        w.writerow([r["file"], r["topic"], r["created"], r["words"],
                    r["score"] or "", ",".join(r["tags"])])
    return buf.getvalue().encode("utf-8")


def load_run(fname: str):
    data = json.loads((HISTORY_DIR / fname).read_text(encoding="utf-8"))
    if st.session_state.result:
        st.session_state.prev_result = st.session_state.result
        st.session_state.prev_meta = st.session_state.meta
    st.session_state.result, st.session_state.meta = data["state"], {**data["meta"], "file": fname}
    st.session_state.topic_input = data["meta"]["topic"]
    st.session_state.chat, st.session_state.chat_for = [], data["meta"]["created"]


def delete_run(fname: str):
    (HISTORY_DIR / fname).unlink(missing_ok=True)
    tags = load_tags()
    tags.pop(fname, None)
    save_tags(tags)
    list_history.clear()
    if (st.session_state.meta or {}).get("file") == fname:
        st.session_state.result = st.session_state.meta = None


def clear_history():
    for f in HISTORY_DIR.glob("*.json"):
        if not f.name.startswith("_"):
            f.unlink(missing_ok=True)
    save_tags({})
    list_history.clear()
    st.session_state.result = st.session_state.meta = None


def rename_run(fname: str, new_topic: str):
    if not new_topic.strip():
        return
    p = HISTORY_DIR / fname
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data["meta"]["topic"] = new_topic.strip()
        new_name = f"{datetime.now():%Y%m%d-%H%M%S}__{slugify(new_topic)}.json"
        (HISTORY_DIR / new_name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        p.unlink(missing_ok=True)
        list_history.clear()
    except Exception as e:
        st.sidebar.error(f"Rename failed: {e}")


def set_topic(v: str):
    st.session_state.topic_input = v

def random_topic():
    st.session_state.topic_input = random.choice(EXAMPLE_TOPICS)

def reset_settings():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v

def toggle_help():
    st.session_state.show_help = not st.session_state.show_help


# ============================================================================
# Sidebar
# ============================================================================
with st.sidebar:
    st.markdown('<div class="brand">Research<span>Mind</span></div>', unsafe_allow_html=True)
    st.caption("Full-power multi-agent research control panel")

    st.markdown('<div class="label free" style="margin-top:1rem">APPEARANCE</div>', unsafe_allow_html=True)
    st.radio("Theme", ["Dark", "Light", "Auto"], key="theme_choice", horizontal=True,
             help="Auto follows Streamlit's own theme (⋮ menu → Settings).")

    st.markdown('<div class="label free" style="margin-top:1rem">SETTINGS</div>', unsafe_allow_html=True)

    with st.expander("📝 Report", expanded=False):
        st.select_slider("Depth", options=DEPTHS, key="opt_depth")
        st.selectbox("Tone", TONES, key="opt_tone")
        st.selectbox("Language", LANGUAGES, key="opt_lang")
        st.selectbox("Structure template", list(TEMPLATES.keys()), key="opt_template")
        st.text_area("Custom instructions", key="opt_extra", height=80,
                     placeholder="e.g. Include a pros/cons table and end with key takeaways.")

        presets = load_presets()
        preset_names = ["—"] + list(presets.keys())
        chosen = st.selectbox("Custom preset", preset_names, key="opt_preset_pick")
        if chosen != "—" and presets.get(chosen):
            if st.button("Apply preset", use_container_width=True):
                st.session_state.opt_extra = presets[chosen]
                st.rerun()
        with st.expander("💾 Manage presets"):
            pname = st.text_input("Preset name", key="preset_name")
            if st.button("Save current text as preset", use_container_width=True):
                if pname.strip() and st.session_state.opt_extra.strip():
                    presets[pname.strip()] = st.session_state.opt_extra.strip()
                    save_presets(presets)
                    st.success(f"Saved '{pname}'")
            if presets:
                del_name = st.selectbox("Delete preset", list(presets.keys()), key="preset_del")
                if st.button("Delete", use_container_width=True):
                    presets.pop(del_name, None)
                    save_presets(presets)
                    st.rerun()

    with st.expander("🔍 Search", expanded=False):
        st.selectbox("Source focus", FOCUSES, key="opt_focus")

    with st.expander("⚙️ Pipeline", expanded=False):
        st.slider("Delay between steps (s)", 0.0, 5.0, step=0.5, key="opt_delay")
        st.slider("Auto-retries per step", 0, 3, key="opt_retries")
        st.slider("Search context passed to reader (chars)", 400, 3000, step=100, key="opt_ctx")
        st.toggle("Run critic step", key="opt_critic")
        st.toggle("Auto-scroll log", key="opt_autoscroll")
        st.number_input("$ per 1M tokens (for cost estimate)", 0.0, 100.0, step=0.1,
                        key="opt_cost", format="%.2f")

    with st.expander("🤖 Model"):
        models = list_models()
        st.selectbox("Model (if agents.get_llm supports it)", models, key="opt_model")
        st.caption("Model switching requires `get_llm(name)` in agents.py.")

    st.toggle("Batch mode (one topic per line)", key="opt_batch")
    st.toggle("Compare mode (two topics side-by-side)", key="opt_compare")
    st.button("↺ Reset settings", on_click=reset_settings, use_container_width=True)

    st.markdown('<div class="label free" style="margin-top:1.2rem">HISTORY</div>', unsafe_allow_html=True)
    rows = list_history(HISTORY_DIR.stat().st_mtime)

    q = st.text_input("Search history", placeholder="Filter by title or content…",
                      label_visibility="collapsed")
    tag_filter = st.text_input("Filter by tag", placeholder="tag filter…",
                               label_visibility="collapsed")

    def _matches(r):
        if q:
            ql = q.lower()
            if ql not in r["topic"].lower() and ql not in (r.get("snippet") or "").lower():
                return False
        if tag_filter and tag_filter.strip() not in r.get("tags", []):
            return False
        return True

    shown = [r for r in rows if _matches(r)]

    if not rows:
        st.caption("Saved runs appear here and persist between sessions.")
    for r in shown[:25]:
        score = f" · ⭐{r['score']}" if r.get("score") else ""
        tag_str = " ".join(f"#{t}" for t in r.get("tags", []))
        c1, c2 = st.columns([5, 1])
        c1.button(
            f"{r['topic'][:26]}{score}",
            key=f"ld_{r['file']}", on_click=load_run, args=(r["file"],),
            help=f"{r['created'].replace('T', ' ')} — {r['words']} words {('| ' + tag_str) if tag_str else ''}",
            use_container_width=True,
        )
        c2.button("✕", key=f"dl_{r['file']}", on_click=delete_run, args=(r["file"],), help="Delete")
    if len(shown) > 25:
        st.caption(f"+{len(shown) - 25} more (use the filter)")

    if rows:
        st.download_button("⬇ History (.zip)", history_zip(), "researchmind_history.zip",
                           "application/zip", use_container_width=True)
        st.download_button("⬇ History (.csv)", history_csv(), "researchmind_history.csv",
                           "text/csv", use_container_width=True)
        st.button("🗑 Clear history", on_click=clear_history, use_container_width=True)

    with st.expander("🏷 Tag current run"):
        if st.session_state.meta and st.session_state.meta.get("file"):
            tags_all = load_tags()
            cur = tags_all.get(st.session_state.meta["file"], [])
            newtag = st.text_input("New tag", key="newtag", placeholder="e.g. biotech")
            if st.button("Add tag", use_container_width=True):
                if newtag.strip() and newtag.strip() not in cur:
                    cur.append(newtag.strip())
                    tags_all[st.session_state.meta["file"]] = cur
                    save_tags(tags_all)
                    list_history.clear()
                    st.rerun()
            if cur:
                st.write("Current tags: " + " ".join(f"`#{t}`" for t in cur))
                rm = st.selectbox("Remove tag", cur, key="rmtag")
                if st.button("Remove", use_container_width=True):
                    cur.remove(rm)
                    tags_all[st.session_state.meta["file"]] = cur
                    save_tags(tags_all)
                    list_history.clear()
                    st.rerun()
        else:
            st.caption("Run something first to tag it.")

    with st.expander("📊 Session metrics"):
        m = st.session_state.metrics
        st.markdown(
            f"- **Runs:** {m['runs']}\n"
            f"- **Words written:** {m['words']:,}\n"
            f"- **Time spent:** {fmt_secs(m['seconds'])}\n"
            f"- **Tokens est.:** {m['tokens_est']:,}\n"
            f"- **Est. cost:** ${m['tokens_est'] * st.session_state.opt_cost / 1_000_000:.4f}"
        )

    with st.expander("ℹ️ About & tips"):
        st.markdown(
            "**Pipeline:** Search → Read → Write → Critique.\n\n"
            "- Press **Ctrl/⌘+Enter** in topic box to run.\n"
            "- **Batch** queues many topics.\n"
            "- **Compare** shows two reports side-by-side.\n"
            "- **Rewrite** re-runs only writer/critic on saved research.\n"
            "- **Resume** appears after a failure to skip completed steps.\n"
            "- ⋮ menu keeps Deploy, theme, and screencast working."
        )

# ============================================================================
# Keyboard shortcuts
# ============================================================================
st.markdown("""
<script>
document.addEventListener('keydown', function(e) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    const btn = document.querySelector('button[kind="primaryFormSubmit"]');
    if (btn) { e.preventDefault(); btn.click(); }
  }
});
</script>
""", unsafe_allow_html=True)

# ============================================================================
# Hero
# ============================================================================
st.markdown(
    """
<div class="hero">
  <div class="eyebrow">MULTI-AGENT AI SYSTEM · FULL POWER EDITION</div>
  <div class="title">Research<span class="accent">Mind</span></div>
  <p class="sub">Four specialized AI agents collaborate — searching, scraping, writing, and
  critiquing — to deliver a polished research report on any topic.</p>
</div>
<div class="divider"></div>
""",
    unsafe_allow_html=True,
)

# ============================================================================
# Input + Pipeline
# ============================================================================
left, _gap, right = st.columns([1, 0.12, 1])
batch = st.session_state.opt_batch
compare = st.session_state.opt_compare

with left:
    st.markdown(
        '<div class="label">RESEARCH TOPICS</div>' if batch
        else '<div class="label">RESEARCH TOPIC</div>',
        unsafe_allow_html=True,
    )
    with st.form("topic_form", clear_on_submit=False):
        if batch:
            st.text_area("Topics", key="topic_input", height=130, label_visibility="collapsed",
                         placeholder="One topic per line…")
        else:
            st.text_input("Research topic", key="topic_input", label_visibility="collapsed",
                          placeholder="e.g. Quantum computing breakthroughs in 2025")
            if compare:
                st.text_input("Second topic (compare)", key="opt_topic2",
                              placeholder="e.g. Classical computing vs Quantum — future outlook")
        run_clicked = st.form_submit_button("Run Research Pipeline", type="primary",
                                            use_container_width=True)

    st.markdown('<div class="label muted">TRY →</div>', unsafe_allow_html=True)
    for ex in EXAMPLE_TOPICS[:3]:
        st.button(ex, key=f"ex_{ex}", on_click=set_topic, args=(ex,))
    st.button("🎲 Surprise me", key="rand", on_click=random_topic)

with right:
    st.markdown('<div class="label">PIPELINE</div>', unsafe_allow_html=True)
    batch_box = st.empty()
    pipeline_box = st.empty()
    meta0 = st.session_state.meta
    if st.session_state.result and meta0:
        times0 = meta0.get("times") or [None] * 4
        sts0 = ["done"] * 4
        if not meta0.get("opts", {}).get("opt_critic", True):
            sts0[3] = "skipped"
        pipeline_box.markdown(pipeline_html(sts0, times0, 1.0), unsafe_allow_html=True)
    else:
        pipeline_box.markdown(pipeline_html(["waiting"] * 4, [None] * 4, 0), unsafe_allow_html=True)
    with st.expander("🧾 Live agent log"):
        log_box = st.empty()
        log_box.caption("Logs appear here while the pipeline runs.")

# ============================================================================
# Run
# ============================================================================
if run_clicked:
    raw = st.session_state.topic_input or ""
    topics = ([t.strip() for t in raw.splitlines() if t.strip()] if batch
              else ([raw.strip()] if raw.strip() else []))

    if compare and not batch and st.session_state.opt_topic2.strip():
        topics = [raw.strip(), st.session_state.opt_topic2.strip()]

    if not topics or not topics[0]:
        st.warning("Please enter a research topic first.")
    else:
        opts = collect_opts()
        st.session_state.result = st.session_state.meta = None

        if compare and len(topics) == 2:
            cA, cB = st.columns(2)
            results = []
            for col, topic in zip((cA, cB), topics):
                with col:
                    st.markdown(f'<div class="label free">TOPIC: {html.escape(topic)}</div>',
                                unsafe_allow_html=True)
                    pbox = st.empty()
                    with st.expander("🧾 Log"):
                        lbox = st.empty()
                    tr = Tracker(pbox, lbox)
                    if not execute(topic, opts, tr):
                        break
                    results.append((topic, dict(st.session_state.result), dict(st.session_state.meta)))
            if len(results) == 2:
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                st.markdown('<div class="label free">COMPARISON</div>', unsafe_allow_html=True)
                ca, cb = st.columns(2)
                for col, (topic, state, meta) in zip((ca, cb), results):
                    with col:
                        st.markdown(f"### {html.escape(topic)}")
                        score = critic_score(state["feedback"])
                        st.markdown(stats_html([
                            ("WORDS", f"{len(state['report'].split()):,}", False),
                            ("SCORE", f"{score}/10" if score else "—", True),
                            ("SOURCES", str(len(extract_sources(state['search_results']))), False),
                        ]), unsafe_allow_html=True)
                        st.markdown(state["report"])
                st.session_state.result = results[-1][1]
                st.session_state.meta = results[-1][2]
                st.toast("Compare complete ✅")
            batch_box.empty()

        else:
            ok_all = True
            resume = st.session_state.get("_failed_state")
            resume_topic = st.session_state.get("_failed_topic")
            for n, t in enumerate(topics, 1):
                if len(topics) > 1:
                    batch_box.markdown(
                        f'<div class="label free" style="margin-bottom:.8rem">'
                        f'TOPIC {n}/{len(topics)} — {html.escape(t[:60])}</div>',
                        unsafe_allow_html=True)
                tr = Tracker(pipeline_box, log_box)
                use_resume = resume if (resume and resume_topic == t) else None
                if not execute(t, opts, tr, resume_state=use_resume):
                    ok_all = False
                    break
            batch_box.empty()
            if ok_all:
                st.toast(f"Research complete{'' if len(topics) == 1 else f' ({len(topics)} topics)'} ✅")

        if st.session_state.get("_failed_state"):
            st.warning("Pipeline failed. You can resume from the last successful step.")
            if st.button("▶ Resume from last successful step"):
                tr = Tracker(pipeline_box, log_box)
                if execute(st.session_state["_failed_topic"], collect_opts(), tr,
                           resume_state=st.session_state["_failed_state"]):
                    st.rerun()


# ============================================================================
# Helpers used by results
# ============================================================================
def ask_followup(llm, question: str, state: dict, history: list[dict]) -> str:
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-6:])
    prompt = (
        "You are a research assistant. Answer the question using ONLY the report and sources below. "
        "Cite sources by their URL when relevant. If the answer isn't supported, say so.\n\n"
        f"REPORT:\n{state['report'][:12000]}\n\n"
        f"SOURCES / SEARCH RESULTS:\n{state['search_results'][:3000]}\n\n"
        f"CONVERSATION SO FAR:\n{convo}\n\nQUESTION: {question}"
    )
    resp = llm.invoke(prompt)
    return str(getattr(resp, "content", resp))


def rewrite_report(topic: str, state: dict, o: dict):
    with st.status("Rewriting report with current settings…", expanded=False) as s:
        try:
            research = (f"SEARCH RESULTS :\n {state['search_results']}\n\n"
                        f"DETAILED SCRAPED CONTENT : \n {state['scraped_content']}")
            retries = int(o["opt_retries"])
            state["report"] = call_with_retry(
                lambda: str(writer_chain.invoke({"topic": writer_topic(topic, o), "research": research})),
                retries, "Writer")
            if o["opt_critic"]:
                state["feedback"] = call_with_retry(
                    lambda: str(critic_chain.invoke({"report": state["report"]})), retries, "Critic")
            else:
                state["feedback"] = "_Critic step was skipped (disabled in settings)._"
            meta = st.session_state.meta
            meta["opts"] = o
            if meta.get("file"):
                (HISTORY_DIR / meta["file"]).write_text(
                    json.dumps({"meta": meta, "state": state}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
            s.update(label="Report rewritten", state="complete")
        except Exception as e:
            s.update(label="Rewrite failed", state="error")
            st.error(str(e))


def extract_toc(md: str):
    toc = []
    for m in re.finditer(r"^(#{1,3})\s+(.+)$", md, re.M):
        level, title = len(m.group(1)), m.group(2).strip()
        anchor = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        toc.append((level, title, anchor))
    return toc


def simple_diff(a: str, b: str) -> str:
    A = (a or "").splitlines()[:120]
    B = (b or "").splitlines()[:120]
    out = []
    for la, lb in zip(A, B):
        if la == lb:
            out.append(html.escape(la))
        else:
            out.append(f'<span class="diff-del">{html.escape(la)}</span>'
                       f'<br><span class="diff-add">{html.escape(lb)}</span>')
    if len(A) != len(B):
        longer = A if len(A) > len(B) else B
        for line in longer[min(len(A), len(B)):]:
            tag = "diff-del" if len(A) > len(B) else "diff-add"
            out.append(f'<span class="{tag}">{html.escape(line)}</span>')
    return "<br>".join(out)


# ============================================================================
# Results
# ============================================================================
result, meta = st.session_state.result, st.session_state.meta
if result and meta:
    topic = meta["topic"]
    report, feedback = result["report"], result["feedback"]
    sources = extract_sources(result["search_results"], result["scraped_content"])
    words = len(report.split())
    chars = len(report)
    sentences = len(re.findall(r"[.!?]+\s", report)) or 1
    score = critic_score(feedback)
    toc = extract_toc(report)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label free">RESULTS</div>', unsafe_allow_html=True)
    st.markdown(f"### {html.escape(topic)}", unsafe_allow_html=True)

    est_cost = (estimate_tokens(report, result.get("search_results", ""),
                                result.get("scraped_content", ""))
                * st.session_state.opt_cost / 1_000_000)
    st.markdown(stats_html([
        ("WORDS", f"{words:,}", False),
        ("READ TIME", f"{max(1, round(words / 200))} min", False),
        ("SECTIONS", str(len(re.findall(r'^#{1,3}\s', report, re.M))), False),
        ("SOURCES", str(len(sources)), False),
        ("CRITIC SCORE", f"{score}/10" if score else "—", True),
        ("TOTAL TIME", fmt_secs(meta["total"]) if meta.get("total") else "—", False),
        ("EST. COST", f"${est_cost:.4f}", False),
    ]), unsafe_allow_html=True)

    tabs = st.tabs([
        "Report", "Critic", f"Sources ({len(sources)})", "Ask AI",
        "Diff", "Search Results", "Scraped Content", "Details", "TOC",
    ])

    with tabs[0]:
        st.markdown(report)

        st.markdown('<div class="label free" style="margin-top:1.5rem">EXPORT</div>',
                    unsafe_allow_html=True)
        base = slugify(topic)
        d1, d2, d3, d4 = st.columns(4)
        d1.download_button("⬇ Markdown", report, f"{base}.md", "text/markdown",
                           use_container_width=True)
        d2.download_button("⬇ HTML (print)", to_html_doc(topic, report, feedback),
                           f"{base}.html", "text/html", use_container_width=True)
        d3.download_button("⬇ Text", report, f"{base}.txt", "text/plain",
                           use_container_width=True)
        d4.download_button("⬇ Full JSON",
                           json.dumps({"meta": meta, "state": result},
                                      ensure_ascii=False, indent=2),
                           f"{base}.json", "application/json", use_container_width=True)

        zbytes = io.BytesIO()
        with zipfile.ZipFile(zbytes, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{base}.md", report)
            z.writestr(f"{base}.html", to_html_doc(topic, report, feedback))
            z.writestr(f"{base}_critic.md", feedback)
            z.writestr(f"{base}_sources.txt", "\n".join(sources))
            z.writestr(f"{base}_meta.json",
                       json.dumps({"meta": meta}, ensure_ascii=False, indent=2))
        st.download_button("⬇ Everything (.zip)", zbytes.getvalue(), f"{base}.zip",
                           "application/zip", use_container_width=True)

        r1, r2 = st.columns(2)
        if r1.button("↻ Rewrite with current settings", use_container_width=True,
                     help="Re-runs only the writer and critic on saved research."):
            rewrite_report(topic, result, collect_opts())
            st.rerun()
        copy_button(report, "copy_report", "📋 Copy report")

        with st.expander("📋 Copy-ready markdown"):
            st.code(report, language="markdown")

    with tabs[1]:
        if score:
            st.markdown(f"**Score: {score}/10**")
        st.markdown(feedback)
        copy_button(feedback, "copy_fb", "📋 Copy feedback")

    with tabs[2]:
        if not sources:
            st.caption("No URLs were found in the search results.")
        for i, u in enumerate(sources, 1):
            dom = urlparse(u).netloc.replace("www.", "") or u
            st.markdown(
                f'<a class="src" href="{html.escape(u)}" target="_blank" rel="noopener">'
                f'<div class="d"><span class="n">[{i}]</span>{html.escape(dom)}</div>'
                f'<div class="u">{html.escape(u)}</div></a>',
                unsafe_allow_html=True)
        if sources:
            copy_button("\n".join(sources), "copy_src", "📋 Copy source list")

    with tabs[3]:
        llm = get_llm(st.session_state.opt_model)
        if llm is None:
            st.info("Follow-up chat needs an LLM object named `llm` (or `get_llm()`) "
                    "exported from `agents.py`. Everything else works without it.")
        else:
            if st.session_state.chat_for != meta["created"]:
                st.session_state.chat, st.session_state.chat_for = [], meta["created"]
            for m in st.session_state.chat:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])
            with st.form("ask_form", clear_on_submit=True):
                qn = st.text_input("Ask a follow-up question about this report",
                                   label_visibility="collapsed",
                                   placeholder="Ask a follow-up question about this report…")
                asked = st.form_submit_button("Ask", type="primary")
            if asked and qn.strip():
                st.session_state.chat.append({"role": "user", "content": qn.strip()})
                with st.spinner("Thinking…"):
                    try:
                        ans = ask_followup(llm, qn.strip(), result, st.session_state.chat[:-1])
                    except Exception as e:
                        ans = f"⚠️ Couldn't answer: {e}"
                st.session_state.chat.append({"role": "assistant", "content": ans})
                st.rerun()

    with tabs[4]:
        prev = st.session_state.prev_result
        if not prev:
            st.info("Run another topic (or load a different history entry) to see a diff.")
        else:
            st.markdown(f"**Previous topic:** {html.escape(st.session_state.prev_meta['topic'])}")
            st.markdown(simple_diff(prev["report"], report), unsafe_allow_html=True)

    with tabs[5]:
        st.markdown(result["search_results"])

    with tabs[6]:
        st.markdown(result["scraped_content"])

    with tabs[7]:
        times = meta.get("times") or [None] * 4
        st.markdown(stats_html([(STEPS[i][1].upper(),
                                 f"{t:.1f}s" if t is not None else "—", False)
                                for i, t in enumerate(times)]), unsafe_allow_html=True)
        
        _unique_words = len(set(re.findall(r'\w+', report.lower())))
        
        st.markdown(stats_html([
            ("CHARS", f"{chars:,}", False),
            ("SENTENCES", f"{sentences:,}", False),
            ("AVG WORDS/SENT", f"{words / max(1, sentences):.1f}", False),
            ("UNIQUE WORDS", f"{_unique_words:,}", False),
        ]), unsafe_allow_html=True)
        
        st.json({"created": meta.get("created"), "file": meta.get("file"),
                 "settings": meta.get("opts")})

    with tabs[8]:
        if not toc:
            st.caption("No headings found in the report.")
        else:
            items = "".join(
                f'<a class="l{lv}" href="#{html.escape(anchor)}">{html.escape(title)}</a>'
                for lv, title, anchor in toc
            )
            st.markdown(f'<div class="toc">{items}</div>', unsafe_allow_html=True)