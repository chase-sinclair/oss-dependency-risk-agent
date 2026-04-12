"""
Reusable metric card and score badge components.
"""

from typing import Optional

import streamlit as st


def render_metric_card(
    label: str,
    value: str | float | int | None,
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
    Return a coloured Markdown badge string for a health score.

    Args:
        score: Health score 0-10, or None.

    Returns:
        Markdown string rendering the score in a coloured badge using HTML.
    """
    if score is None:
        return "<span style='color:#888'>N/A</span>"
    score = float(score)
    if score >= 7.0:
        color = "#2ecc71"
        label = "Healthy"
    elif score >= 5.0:
        color = "#f39c12"
        label = "Warning"
    else:
        color = "#e74c3c"
        label = "Critical"
    return (
        f"<span style='background:{color};color:#fff;padding:2px 8px;"
        f"border-radius:4px;font-weight:bold;font-size:0.85em'>"
        f"{score:.2f} — {label}</span>"
    )


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
