from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class HealthScore(BaseModel):
    repo_full_name: str
    org_name: Optional[str] = None
    health_score: float
    health_trend: Optional[float] = None
    commit_score: Optional[float] = None
    issue_score: Optional[float] = None
    pr_score: Optional[float] = None
    contributor_score: Optional[float] = None
    bus_factor_score: Optional[float] = None
    data_days_available: Optional[int] = None
    has_push_data: Optional[bool] = None
    computed_at: Optional[str] = None


class Summary(BaseModel):
    total_projects: int
    critical_count: int
    warning_count: int
    healthy_count: int
    avg_health_score: float
    last_pipeline_run: Optional[str] = None
    last_agent_run: Optional[str] = None
    projects_assessed_count: int
    assessed_repos: list[str] = []


class ReportMeta(BaseModel):
    filename: str
    timestamp: str
    project_count: int
    file_size_kb: float


class SearchRequest(BaseModel):
    query: str
    filter: Optional[str] = None
    top_k: int = 5


class SearchResult(BaseModel):
    repo_full_name: str
    health_score: Optional[float] = None
    recommendation: Optional[str] = None
    similarity_score: float
    excerpt: Optional[str] = None
    report_date: Optional[str] = None


class AgentRunRequest(BaseModel):
    dry_run: bool = False
    limit: Optional[int] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None


class AgentRunResponse(BaseModel):
    status: str
    run_id: str


class AgentRunSummary(BaseModel):
    assessed: int
    replace_count: int
    upgrade_count: int
    monitor_count: int


class AgentStatus(BaseModel):
    status: str  # "running" | "complete" | "failed"
    summary: Optional[AgentRunSummary] = None
    report_filename: Optional[str] = None


class ReadyProject(BaseModel):
    org: str
    repo: str
    package_name: str
    ecosystem: str
    health_score: Optional[float] = None   # None = monitored but not yet scored


class AddedProject(BaseModel):
    org: str
    repo: str
    package_name: str
    ecosystem: str
    confidence: str  # high | low


class UnresolvedPackage(BaseModel):
    name: str
    reason: str = "not found"


class OnboardResponse(BaseModel):
    parsed_count: int
    ready_projects: list[ReadyProject]
    added_projects: list[AddedProject]
    unresolved_packages: list[UnresolvedPackage]
