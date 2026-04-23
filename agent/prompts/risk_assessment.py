"""
Prompt templates for the Claude risk assessment synthesis step.

Keeping prompts in a dedicated module makes them easy to iterate on
without touching business logic in the synthesize node.
"""

SYSTEM_PROMPT = """\
You are an OSS dependency risk analyst embedded in an engineering platform team. \
Your job is to assess the health and risk level of open-source projects that a \
large organisation depends on.

You will receive quantitative health metrics (0-10 scale) alongside recent GitHub \
activity signals. Based on this data, produce a concise, actionable risk assessment.

Guidelines:
- Be direct. Engineering leads need to act on your output.
- Cite specific metrics when they drive your conclusion.
- Do not speculate beyond what the data shows.
- If a signal is missing or unclear, say so briefly rather than guessing.
"""


def build_risk_assessment_prompt(
    repo_full_name: str,
    health_scores: dict,
    github_signals: dict,
    has_push_data: bool = True,
) -> str:
    """
    Build the user message for a single project risk assessment.

    Args:
        repo_full_name:  "org/repo" string.
        health_scores:   Row dict from gold_health_scores (values are strings or None).
        github_signals:  Dict returned by fetch_project_signals.

    Returns:
        Formatted prompt string ready to send to Claude.
    """
    def fmt(val, decimals: int = 2) -> str:
        """Format a possibly-string float, return 'N/A' if missing."""
        if val is None:
            return "N/A"
        try:
            return f"{float(val):.{decimals}f}"
        except (TypeError, ValueError):
            return str(val)

    metadata  = github_signals.get("metadata", {})
    issues    = github_signals.get("open_issues", [])
    prs       = github_signals.get("recent_prs", [])

    issue_lines = "\n".join(
        f"  - #{i['number']}: {i['title']} "
        f"({i['comments']} comments"
        + (f", labels: {', '.join(i['labels'])}" if i.get("labels") else "")
        + ")"
        for i in issues[:5]
    ) or "  No open issues retrieved."

    pr_lines = "\n".join(
        f"  - #{p['number']}: {p['title']}"
        + (" [draft]" if p.get("draft") else "")
        for p in prs[:3]
    ) or "  No recent PRs retrieved."

    stars        = metadata.get("stars")
    open_issues  = metadata.get("open_issues")
    forks        = metadata.get("forks")
    stars_str    = f"{int(stars):,}"       if stars       is not None else "N/A"
    issues_str   = f"{int(open_issues):,}" if open_issues is not None else "N/A"
    forks_str    = f"{int(forks):,}"       if forks       is not None else "N/A"

    push_data_note = (
        "\n> **Data coverage notice:** No PushEvents were found for this repository in the "
        "current scoring window. Commit frequency and contributor diversity scores are set "
        "to 5.0 (neutral fallback) — they do **not** reflect real activity. Do not cite "
        "these two metrics as evidence of health or risk; treat them as unavailable.\n"
        if not has_push_data else ""
    )

    return f"""\
Assess the dependency risk for: {repo_full_name}

## Quantitative Health Metrics (0-10 scale, higher is healthier)
{push_data_note}
| Signal | Score | Notes |
|---|---|---|
| Overall health score | {fmt(health_scores.get('health_score'))} | |
| Commit frequency | {fmt(health_scores.get('commit_score'))} | {'estimated — no push data' if not has_push_data else ''} |
| Issue resolution rate | {fmt(health_scores.get('issue_score'))} | |
| PR merge rate | {fmt(health_scores.get('pr_score'))} | |
| Contributor diversity | {fmt(health_scores.get('contributor_score'))} | {'estimated — no push data' if not has_push_data else ''} |
| Bus factor (inverted) | {fmt(health_scores.get('bus_factor_score'))} | |

Month-over-month health trend: {fmt(health_scores.get('health_trend'))} \
(positive = improving, negative = deteriorating)

## Repository Metadata
- Stars: {stars_str}
- Open issues: {issues_str}
- Forks: {forks_str}
- Primary language: {metadata.get('language', 'N/A')}
- Archived: {metadata.get('archived', False)}
- Last push: {metadata.get('pushed_at', 'N/A')}

## Recent Open Issues (sample, up to 5)
{issue_lines}

## Recent Open Pull Requests (sample, up to 3)
{pr_lines}

---

Provide a risk assessment with exactly 3 bullet points:

1. **Primary risk signal** — the single most concerning metric or pattern and why it matters
2. **Mitigating factors** — what makes this project resilient despite the low score
3. **Recommended action** — specific, concrete guidance for an engineering team that depends on this project

Each bullet should be 1-2 sentences. Do not add extra bullets or headers.\
"""
