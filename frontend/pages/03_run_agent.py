"""
Agent Control Room — trigger the LangGraph risk agent and stream live output.
"""

import re
import subprocess
import sys
import threading
from pathlib import Path
from queue import Empty, Queue

import streamlit as st
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv()

st.set_page_config(page_title="Agent Control Room | OSS Risk Agent", layout="wide")

_SCRIPT      = _ROOT / "scripts" / "run_agent.py"
_PYTHON      = sys.executable
_REPORTS_DIR = _ROOT / "docs" / "reports"

_PIPELINE_STEPS = [
    ("Monitor",     "Queries `gold_health_scores` for projects outside the target score range."),
    ("Investigate", "Fetches recent GitHub issues, PRs, and repo metadata for flagged projects."),
    ("Synthesize",  "Sends health metrics + GitHub signals to Claude for a 3-point risk assessment."),
    ("Recommend",   "Maps each project to REPLACE / UPGRADE / MONITOR based on risk score."),
    ("Deliver",     "Renders a Markdown report and writes it to `docs/reports/`."),
]


def _stream_process(proc: subprocess.Popen, queue: Queue) -> None:
    """Push stdout lines into queue. Sends None sentinel on completion."""
    for line in proc.stdout:
        queue.put(line.rstrip("\n"))
    proc.wait()
    queue.put(None)


def _latest_report() -> Path | None:
    if not _REPORTS_DIR.exists():
        return None
    reports = sorted(_REPORTS_DIR.glob("risk_report_*.md"), reverse=True)
    return reports[0] if reports else None


def _last_run_summary() -> dict | None:
    """Parse the most recent report for a summary of the last run."""
    path = _latest_report()
    if not path:
        return None
    stem = path.stem.replace("risk_report_", "")
    date_part = stem[:10]
    time_part = stem[11:16].replace("-", ":") if len(stem) > 10 else ""
    timestamp = f"{date_part} {time_part}".strip()
    text = path.read_text(encoding="utf-8", errors="ignore")
    project_count = len(re.findall(r"^### ", text, re.MULTILINE))
    replace_count = len(re.findall(r"\bREPLACE\b", text))
    upgrade_count = len(re.findall(r"\bUPGRADE\b", text))
    monitor_count = len(re.findall(r"\bMONITOR\b", text))
    return {
        "timestamp":     timestamp,
        "projects":      project_count,
        "replace_count": replace_count,
        "upgrade_count": upgrade_count,
        "monitor_count": monitor_count,
        "filename":      path.name,
    }


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.markdown("---")
    st.subheader("Agent Options")

    dry_run = st.checkbox("Dry run (skip report write)", value=False)

    project_limit = st.number_input(
        "Project limit (0 = all)",
        min_value=0, max_value=100, value=5, step=1,
    )

    st.markdown("**Score range to target**")
    min_score_val = st.slider("Min score", 0.0, 10.0, 0.0, 0.5,
                               help="Only include projects with health score ≥ this value.")
    max_score_val = st.slider("Max score", 0.0, 10.0, 6.0, 0.5,
                               help="Only include projects with health score < this value.")

    st.markdown("---")
    st.caption(
        "The agent queries Databricks for projects within the score range, "
        "fetches GitHub signals, and calls Claude to generate risk assessments."
    )

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Agent Control Room")
st.markdown(
    "Run the 5-node LangGraph pipeline: "
    + "  →  ".join(f"**{name}**" for name, _ in _PIPELINE_STEPS)
)
st.markdown("---")

# ── Pipeline steps preview ────────────────────────────────────────────────────

with st.expander("Pipeline Steps", expanded=False):
    for i, (name, desc) in enumerate(_PIPELINE_STEPS, start=1):
        st.markdown(f"**{i}. {name}** — {desc}")

st.markdown("")

# ── Run button ────────────────────────────────────────────────────────────────

run_col, _ = st.columns([2, 5])
with run_col:
    run_button = st.button("▶  Run Agent", type="primary", use_container_width=True)

# ── Last run summary ──────────────────────────────────────────────────────────

summary = _last_run_summary()
if summary:
    with st.expander(f"Last run: {summary['timestamp']}  ({summary['projects']} projects)", expanded=False):
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Projects Assessed", summary["projects"])
        sc2.metric("REPLACE", summary["replace_count"])
        sc3.metric("UPGRADE",  summary["upgrade_count"])
        sc4.metric("MONITOR",  summary["monitor_count"])
        st.caption(f"Report file: `{summary['filename']}`")

# ── Agent execution ───────────────────────────────────────────────────────────

if run_button:
    cmd = [_PYTHON, str(_SCRIPT)]
    if dry_run:
        cmd.append("--dry-run")
    if project_limit and project_limit > 0:
        cmd.extend(["--limit", str(project_limit)])
    if min_score_val > 0.0:
        cmd.extend(["--min-score", str(min_score_val)])
    if max_score_val < 10.0:
        cmd.extend(["--max-score", str(max_score_val)])

    st.markdown("---")
    st.subheader("Live Output")

    status_slot = st.empty()
    log_slot    = st.empty()

    status_slot.info("Agent running…")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(_ROOT),
        )
    except Exception as exc:
        st.error(f"Failed to start agent process: {exc}")
        st.stop()

    queue: Queue = Queue()
    reader = threading.Thread(target=_stream_process, args=(proc, queue), daemon=True)
    reader.start()

    log_lines: list = []
    while True:
        try:
            line = queue.get(timeout=0.1)
        except Empty:
            continue
        if line is None:
            break
        log_lines.append(line)
        log_slot.code("\n".join(log_lines[-80:]), language=None)

    reader.join()
    return_code = proc.returncode

    if return_code == 0:
        status_slot.success("Agent completed successfully.")
    else:
        status_slot.error(f"Agent exited with code {return_code}.")

    # Post-run download + link to new report
    st.markdown("---")
    full_log = "\n".join(log_lines)
    dl_col, link_col = st.columns([2, 3])
    with dl_col:
        st.download_button(
            label="Download log",
            data=full_log,
            file_name="agent_run.log",
            mime="text/plain",
        )
    if not dry_run:
        with link_col:
            new_report = _latest_report()
            if new_report:
                st.success(f"Report written: `{new_report.name}`")
                if st.button("View Report →"):
                    st.switch_page("pages/04_reports.py")

else:
    st.info("Configure options in the sidebar and click **Run Agent** to start.")
