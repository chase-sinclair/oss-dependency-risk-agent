"""
Synthesize node — calls Claude to produce a risk assessment for each project.

Pairs quantitative health scores (from flagged_projects) with qualitative
GitHub signals (from investigation_results) and sends them to the Claude API.
Stores results in AgentState.risk_assessments keyed by repo_full_name.
"""

import logging
import os
import time

import anthropic
from dotenv import load_dotenv

from agent.graphs.state import AgentState
from agent.prompts.risk_assessment import SYSTEM_PROMPT, build_risk_assessment_prompt

load_dotenv()

logger = logging.getLogger(__name__)

_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
_MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "512"))
_MAX_RETRIES = int(os.environ.get("AGENT_MAX_RETRIES", "3"))
_RETRY_DELAY = float(os.environ.get("AGENT_RETRY_DELAY_SECONDS", "5.0"))


def _call_claude(client: anthropic.Anthropic, prompt: str) -> str:
    """Call Claude with retry logic. Returns the text response."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except anthropic.RateLimitError as exc:
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "synthesize: rate limit hit (attempt %d/%d), sleeping %.1fs: %s",
                    attempt, _MAX_RETRIES, _RETRY_DELAY, exc,
                )
                time.sleep(_RETRY_DELAY)
            else:
                raise
        except anthropic.APIError as exc:
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "synthesize: API error (attempt %d/%d), sleeping %.1fs: %s",
                    attempt, _MAX_RETRIES, _RETRY_DELAY, exc,
                )
                time.sleep(_RETRY_DELAY)
            else:
                raise


def synthesize(state: AgentState) -> dict:
    """
    Generate a Claude risk assessment for each investigated project.

    Returns:
        Dict with key: risk_assessments — {repo_full_name: assessment_text}.
    """
    flagged = state.get("flagged_projects", [])
    investigation = state.get("investigation_results", {})

    if not flagged:
        logger.info("synthesize: no flagged projects to assess")
        return {"risk_assessments": {}}

    # Build a lookup from repo_full_name -> health score row
    health_lookup: dict[str, dict] = {
        row["repo_full_name"]: row
        for row in flagged
        if row.get("repo_full_name")
    }

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    assessments: dict = {}

    logger.info("synthesize: generating risk assessments for %d projects", len(flagged))

    for repo, signals in investigation.items():
        if "error" in signals:
            logger.warning("synthesize: skipping %s due to investigation error: %s", repo, signals["error"])
            assessments[repo] = f"Risk assessment unavailable: {signals['error']}"
            continue

        health_scores = health_lookup.get(repo, {})
        raw_push = health_scores.get("has_push_data")
        has_push = raw_push if isinstance(raw_push, bool) else str(raw_push).lower() not in ("false", "0", "none", "")
        prompt = build_risk_assessment_prompt(
            repo_full_name=repo,
            health_scores=health_scores,
            github_signals=signals,
            has_push_data=has_push,
        )

        logger.info("synthesize: calling Claude for %s", repo)
        try:
            assessment = _call_claude(client, prompt)
            assessments[repo] = assessment
            logger.debug("synthesize: assessment for %s:\n%s", repo, assessment[:200])
        except Exception as exc:
            logger.error("synthesize: Claude call failed for %s: %s", repo, exc)
            assessments[repo] = f"Risk assessment failed: {exc}"

    logger.info("synthesize: completed %d assessments", len(assessments))
    return {"risk_assessments": assessments}
