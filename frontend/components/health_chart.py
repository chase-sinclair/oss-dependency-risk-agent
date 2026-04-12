"""
Reusable Plotly bar chart component for health score visualisation.
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def _score_color(score: float) -> str:
    if score >= 7.0:
        return "#2ecc71"   # green
    if score >= 5.0:
        return "#f39c12"   # yellow/amber
    return "#e74c3c"       # red


def render_health_bar_chart(
    df: pd.DataFrame,
    score_col: str = "health_score",
    label_col: str = "repo_full_name",
    title: str = "Health Scores",
    height: Optional[int] = None,
) -> None:
    """
    Render a horizontal bar chart of health scores.

    Args:
        df:         DataFrame containing at least label_col and score_col.
        score_col:  Column name for the numeric health score (0-10).
        label_col:  Column name for the repo label on the y-axis.
        title:      Chart title.
        height:     Chart height in pixels. Defaults to 40px per bar, min 300.
    """
    if df.empty:
        st.info("No data to display.")
        return

    plot_df = df[[label_col, score_col]].copy()
    plot_df[score_col] = pd.to_numeric(plot_df[score_col], errors="coerce").fillna(0.0)
    plot_df = plot_df.sort_values(score_col, ascending=True)

    colors = [_score_color(v) for v in plot_df[score_col]]
    chart_height = height or max(300, len(plot_df) * 40)

    fig = go.Figure(
        go.Bar(
            x=plot_df[score_col],
            y=plot_df[label_col],
            orientation="h",
            marker_color=colors,
            text=[f"{v:.2f}" for v in plot_df[score_col]],
            textposition="outside",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        title=title,
        xaxis=dict(range=[0, 10.5], title="Health Score (0-10)"),
        yaxis=dict(title=""),
        height=chart_height,
        margin=dict(l=20, r=60, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")

    st.plotly_chart(fig, use_container_width=True)


def render_trend_chart(
    df: pd.DataFrame,
    month_col: str = "event_month",
    score_col: str = "health_score",
    repo_col: str = "repo_full_name",
    title: str = "Health Score Over Time",
) -> None:
    """
    Render a line chart of health score trend over time for one or more repos.

    Args:
        df:         DataFrame with month_col, score_col, and optionally repo_col.
        month_col:  Column containing the time period.
        score_col:  Column containing the numeric health score.
        repo_col:   Column for grouping multiple repos (one line per repo).
        title:      Chart title.
    """
    if df.empty:
        st.info("No trend data available.")
        return

    plot_df = df.copy()
    plot_df[score_col] = pd.to_numeric(plot_df[score_col], errors="coerce")
    plot_df = plot_df.sort_values(month_col)

    fig = go.Figure()

    repos = plot_df[repo_col].unique() if repo_col in plot_df.columns else [""]
    for repo in repos:
        subset = plot_df[plot_df[repo_col] == repo] if repo else plot_df
        fig.add_trace(
            go.Scatter(
                x=subset[month_col],
                y=subset[score_col],
                mode="lines+markers",
                name=repo,
            )
        )

    fig.add_hline(y=7.0, line_dash="dot", line_color="#2ecc71", annotation_text="Healthy (7.0)")
    fig.add_hline(y=5.0, line_dash="dot", line_color="#f39c12", annotation_text="Warning (5.0)")

    fig.update_layout(
        title=title,
        xaxis_title="Month",
        yaxis=dict(range=[0, 10], title="Health Score"),
        height=350,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")

    st.plotly_chart(fig, use_container_width=True)
