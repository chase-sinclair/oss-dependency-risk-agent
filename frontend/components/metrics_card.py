"""
Reusable metric card and score badge components.
"""

from typing import Optional

import streamlit as st


def render_metric_card(
    label: str,
    value: "str | float | int | None",
    delta: Optional[float] = None,
    help_text: Optional[str] = None,
) -> None:
    """
    Render a single st.metric card.

    Args:
        label:     Card label.
        value:     Display value (numeric or string).
        delta:     Optional delta shown below the value (positive = green).
        help_text: Optional tooltip text.
    """
    display = "N/A" if value is None else value
    delta_str = f"{delta:+.2f}" if delta is not None else None
    st.metric(label=label, value=display, delta=delta_str, help=help_text)


def score_badge(score: Optional[float]) -> str:
    """
    Return a coloured HTML badge string for a health score.

    Args:
        score: Health score 0-10, or None.

    Returns:
        HTML string rendering the score in a coloured badge.
    """
    if score is None:
        return "<span style='background:#555;color:#fff;padding:2px 8px;border-radius:4px;font-weight:bold;font-size:0.85em'>N/A</span>"
    score = float(score)
    if score >= 7.0:
        bg, label = "#27ae60", "Healthy"
    elif score >= 5.0:
        bg, label = "#e67e22", "Warning"
    else:
        bg, label = "#c0392b", "Critical"
    return (
        f"<span style='background:{bg};color:#fff;padding:3px 10px;"
        f"border-radius:4px;font-weight:bold;font-size:0.85em'>"
        f"{score:.2f} — {label}</span>"
    )


def status_dot(score: Optional[float]) -> str:
    """Return a coloured emoji dot for a health score."""
    if score is None:
        return "⚪"
    score = float(score)
    if score >= 7.0:
        return "🟢"
    if score >= 5.0:
        return "🟡"
    return "🔴"


def render_score_row(
    label: str,
    score: Optional[float],
    max_score: float = 10.0,
    help_text: Optional[str] = None,
) -> None:
    """
    Render a labelled score row with a progress bar and badge.

    Args:
        label:     Signal name.
        score:     Numeric score 0-10.
        max_score: Upper bound for the progress bar (default 10).
        help_text: Optional tooltip.
    """
    col_label, col_bar, col_badge = st.columns([2, 4, 2])
    with col_label:
        st.markdown(f"**{label}**", help=help_text)
    with col_bar:
        if score is not None:
            st.progress(max(0.0, min(1.0, float(score) / max_score)))
        else:
            st.progress(0.0)
    with col_badge:
        st.markdown(score_badge(score), unsafe_allow_html=True)


def render_score_card(label: str, score: Optional[float], help_text: Optional[str] = None) -> None:
    """
    Render a compact score card with label, badge, and mini progress bar.
    Suitable for use in a column grid layout.

    Args:
        label:     Signal name.
        score:     Numeric score 0-10, or None.
        help_text: Optional tooltip.
    """
    score_f = float(score) if score is not None else None
    pct = max(0.0, min(1.0, score_f / 10.0)) if score_f is not None else 0.0

    st.markdown(f"**{label}**", help=help_text)
    st.markdown(score_badge(score_f), unsafe_allow_html=True)
    st.progress(pct)
