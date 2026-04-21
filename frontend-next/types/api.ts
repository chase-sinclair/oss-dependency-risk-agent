export interface HealthScore {
  repo_full_name: string;
  org_name: string | null;
  health_score: number;
  health_trend: number | null;
  commit_score: number | null;
  issue_score: number | null;
  pr_score: number | null;
  contributor_score: number | null;
  bus_factor_score: number | null;
  data_days_available: number | null;
  computed_at: string | null;
}

export interface Summary {
  total_projects: number;
  critical_count: number;
  warning_count: number;
  healthy_count: number;
  avg_health_score: number;
  last_pipeline_run: string | null;
  last_agent_run: string | null;
  projects_assessed_count: number;
  assessed_repos: string[];
}

export interface ReportMeta {
  filename: string;
  timestamp: string;
  project_count: number;
  file_size_kb: number;
}

export interface SearchRequest {
  query: string;
  filter: string | null;
  top_k: number;
}

export interface SearchResult {
  repo_full_name: string;
  health_score: number | null;
  recommendation: string | null;
  similarity_score: number;
  excerpt: string | null;
  report_date: string | null;
}

export interface AgentRunRequest {
  dry_run: boolean;
  limit: number | null;
  min_score: number | null;
  max_score: number | null;
}

export interface AgentRunResponse {
  status: string;
  run_id: string;
}

export interface AgentRunSummary {
  assessed: number;
  replace_count: number;
  upgrade_count: number;
  monitor_count: number;
}

export interface AgentStatus {
  status: "running" | "complete" | "failed";
  summary: AgentRunSummary | null;
  report_filename: string | null;
}
