"""
Run Agent page — trigger a live agent run and stream log output.
"""

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

st.set_page_config(page_title="Run Agent | OSS Risk Agent", layout="wide")

_SCRIPT = _ROOT / "scripts" / "run_agent.py"
_PYTHON = sys.executable


def _stream_process(proc: subprocess.Popen, queue: Queue) -> None:
    """Read stdout from proc line by line and push to queue. Sentinel None on finish."""
    for line in proc.stdout:
        queue.put(line.rstrip("\n"))
    proc.wait()
    queue.put(None)  # sentinel


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.markdown("---")
    st.subheader("Agent Options")
    dry_run = st.checkbox("Dry run (skip report write)", value=False)
    project_limit = st.number_input(
        "Project limit (0 = no limit)",
        min_value=0,
        max_value=50,
        value=5,
        step=1,
    )
    st.markdown("---")
    st.caption(
        "The agent queries Databricks for low-health projects, "
        "fetches GitHub signals, and calls Claude to generate risk assessments."
    )

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Run Agent")
st.markdown(
    "Trigger the 5-node LangGraph pipeline: "
    "**Monitor** → **Investigate** → **Synthesize** → **Recommend** → **Deliver**"
)
st.markdown("---")

run_button = st.button("Run Agent", type="primary", use_container_width=False)

if run_button:
    cmd = [_PYTHON, str(_SCRIPT)]
    if dry_run:
        cmd.append("--dry-run")
    if project_limit and project_limit > 0:
        cmd.extend(["--limit", str(project_limit)])

    st.subheader("Live Output")
    log_area = st.empty()
    status_area = st.empty()

    log_lines: list[str] = []
    queue: Queue = Queue()

    with status_area:
        st.info("Agent running...")

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

    # Stream output in background thread
    reader = threading.Thread(target=_stream_process, args=(proc, queue), daemon=True)
    reader.start()

    while True:
        try:
            line = queue.get(timeout=0.1)
        except Empty:
            continue

        if line is None:
            break

        log_lines.append(line)
        # Show last 60 lines to avoid overflowing the page
        visible = log_lines[-60:]
        log_area.code("\n".join(visible), language=None)

    reader.join()
    return_code = proc.returncode

    if return_code == 0:
        status_area.success("Agent completed successfully.")
    else:
        status_area.error(f"Agent exited with code {return_code}.")

    st.markdown("---")
    if not dry_run:
        st.info("Report written to `docs/reports/`. View it on the **Reports** page.")

    # Offer full log download
    full_log = "\n".join(log_lines)
    st.download_button(
        label="Download full log",
        data=full_log,
        file_name="agent_run.log",
        mime="text/plain",
    )

else:
    st.info("Configure options in the sidebar and click **Run Agent** to start.")

    # Show what the pipeline will do
    st.markdown("### Pipeline Steps")
    steps = [
        ("1. Monitor", "Queries `gold_health_scores` for projects below the health threshold."),
        ("2. Investigate", "Fetches recent GitHub issues, PRs, and repo metadata for each flagged project."),
        ("3. Synthesize", "Sends health metrics + GitHub signals to Claude for a 3-point risk assessment."),
        ("4. Recommend", "Maps each project to REPLACE / UPGRADE / MONITOR based on risk score."),
        ("5. Deliver", "Renders a Markdown report and writes it to `docs/reports/`."),
    ]
    for title, desc in steps:
        st.markdown(f"**{title}** — {desc}")
