"""
Reports — view, compare, and download past risk reports from docs/reports/.
"""

import re
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Reports | OSS Risk Agent", layout="wide")

_REPORTS_DIR = _ROOT / "docs" / "reports"

# Recommendation keywords that mark section jumps
_REC_TYPES = ["REPLACE", "UPGRADE", "MONITOR"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_reports() -> list:
    if not _REPORTS_DIR.exists():
        return []
    return sorted(_REPORTS_DIR.glob("risk_report_*.md"), reverse=True)


def _count_projects(text: str) -> int:
    return len(re.findall(r"^### ", text, re.MULTILINE))


def _friendly_label(path: Path) -> str:
    """Return 'YYYY-MM-DD HH:MM (N projects)' label for a report file."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    stem = path.stem.replace("risk_report_", "")  # 2026-04-12T19-36-29
    date_part = stem[:10]
    time_part = stem[11:16].replace("-", ":") if len(stem) > 10 else ""
    n = _count_projects(text)
    return f"{date_part} {time_part} ({n} projects)"


def _parse_recommendations(text: str) -> dict:
    """
    Extract {org/repo: recommendation} from a report.

    Looks for ### org/repo sections and the first REPLACE/UPGRADE/MONITOR
    keyword that appears in a Recommendation line within the section.
    """
    recs = {}
    sections = re.split(r"\n(?=### )", text)
    for section in sections:
        header = re.match(r"^### ([^\n]+)", section)
        if not header:
            continue
        repo = header.group(1).strip()
        m = re.search(
            r"(?:Recommendation|recommendation)[^\n]*?[ :*`]*\b(REPLACE|UPGRADE|MONITOR)\b",
            section,
        )
        if m:
            recs[repo] = m.group(1)
    return recs


def _rec_color(rec: str) -> str:
    return {"REPLACE": "#c0392b", "UPGRADE": "#e67e22", "MONITOR": "#2980b9"}.get(rec, "#555")


# ── Load reports ──────────────────────────────────────────────────────────────

reports = _load_reports()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.markdown("---")
    st.subheader("Reports")

    if not reports:
        st.info("No reports found.")
        st.stop()

    report_labels = [_friendly_label(r) for r in reports]
    selected_idx = st.selectbox(
        "Select report",
        range(len(reports)),
        format_func=lambda i: report_labels[i],
    )

    st.markdown("---")
    st.subheader("Compare")
    compare_mode = st.checkbox("Compare two reports", value=False)
    compare_idx  = None
    if compare_mode and len(reports) > 1:
        compare_idx = st.selectbox(
            "Compare with",
            [i for i in range(len(reports)) if i != selected_idx],
            format_func=lambda i: report_labels[i],
        )

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Reports")
st.markdown("---")

if not reports:
    st.warning(
        "No reports found in `docs/reports/`. "
        "Run the agent from the **Agent Control Room** to generate one."
    )
    st.stop()

selected_path = reports[selected_idx]
report_text   = selected_path.read_text(encoding="utf-8", errors="ignore")

# ── Top action bar ────────────────────────────────────────────────────────────

col_title, col_actions = st.columns([5, 3])

with col_title:
    st.subheader(report_labels[selected_idx])
    size_kb = selected_path.stat().st_size / 1024
    st.caption(f"`{selected_path.name}`  ·  {size_kb:.1f} KB  ·  {_count_projects(report_text)} projects")

with col_actions:
    btn1, btn2, btn3 = st.columns(3)
    with btn1:
        st.download_button(
            label="Download",
            data=report_text,
            file_name=selected_path.name,
            mime="text/markdown",
            use_container_width=True,
        )
    with btn2:
        # Convert markdown to minimal HTML for download
        html_body = report_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_content = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<style>body{font-family:sans-serif;max-width:900px;margin:40px auto;"
            "padding:0 20px;line-height:1.6}pre{background:#f4f4f4;padding:12px;"
            "border-radius:4px}h3{border-top:1px solid #ddd;padding-top:12px}</style>"
            f"</head><body><pre style='white-space:pre-wrap'>{html_body}</pre></body></html>"
        )
        st.download_button(
            label="Export HTML",
            data=html_content,
            file_name=selected_path.stem + ".html",
            mime="text/html",
            use_container_width=True,
        )
    with btn3:
        if st.button("Print", use_container_width=True):
            components.html(
                "<script>window.parent.print();</script>",
                height=0,
            )

st.markdown("---")

# ── Comparison view ───────────────────────────────────────────────────────────

if compare_mode and compare_idx is not None:
    st.subheader("Report Comparison")
    compare_path = reports[compare_idx]
    compare_text = compare_path.read_text(encoding="utf-8", errors="ignore")

    recs1 = _parse_recommendations(report_text)
    recs2 = _parse_recommendations(compare_text)

    all_repos  = sorted(set(recs1) | set(recs2))
    diff_rows  = []
    changed    = 0
    for repo in all_repos:
        r1 = recs1.get(repo, "—")
        r2 = recs2.get(repo, "—")
        is_changed = r1 != r2
        if is_changed:
            changed += 1
        diff_rows.append({
            "Project": repo,
            report_labels[selected_idx][:16]: r1,
            report_labels[compare_idx][:16]:  r2,
            "Changed": "⚠" if is_changed else "",
        })

    diff_df = pd.DataFrame(diff_rows)

    st.caption(
        f"Comparing **{report_labels[selected_idx]}** vs **{report_labels[compare_idx]}**  ·  "
        f"**{changed}** recommendation change(s)"
    )
    st.dataframe(diff_df, use_container_width=True, hide_index=True)
    st.markdown("---")

# ── Recommendation jump filter ────────────────────────────────────────────────

st.subheader("Jump to Section")
active_recs = [r for r in _REC_TYPES if r in report_text]
if active_recs:
    filter_rec = st.radio(
        "Filter by recommendation",
        ["All"] + active_recs,
        horizontal=True,
        label_visibility="collapsed",
    )
else:
    filter_rec = "All"

# ── Report body ───────────────────────────────────────────────────────────────

st.markdown("---")
view_mode = st.radio("View as", ["Rendered", "Raw Markdown"], horizontal=True)

if filter_rec == "All":
    display_text = report_text
else:
    # Extract only sections containing the chosen recommendation type
    sections = re.split(r"\n(?=### )", report_text)
    header_text = sections[0] if sections and not sections[0].startswith("### ") else ""
    matching = [
        s for s in sections[1:]
        if re.search(
            rf"(?:Recommendation|recommendation)[^\n]*?[ :*`]*\b{filter_rec}\b",
            s,
        )
    ]
    if matching:
        display_text = header_text + "\n" + "\n".join(matching)
        st.caption(f"Showing {len(matching)} {filter_rec} project(s)")
    else:
        st.info(f"No {filter_rec} projects found in this report.")
        display_text = ""

if display_text:
    if view_mode == "Rendered":
        st.markdown(display_text)
    else:
        st.code(display_text, language="markdown")
