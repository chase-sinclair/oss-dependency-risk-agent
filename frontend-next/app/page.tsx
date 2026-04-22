"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHealthScores, getSummary } from "@/lib/api";
import type { HealthScore, Summary } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";
import LoadingSpinner from "@/components/LoadingSpinner";

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso.replace("T", " ").replace(/-/g, "/"));
  if (isNaN(d.getTime())) return iso;
  const mins = Math.floor((Date.now() - d.getTime()) / 60000);
  if (mins < 1)  return "just now";
  if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function KpiCard({
  label,
  value,
  sub,
  glow,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  glow?: "crimson" | "emerald" | "violet";
}) {
  const glowColor =
    glow === "crimson" ? "rgba(255,76,76,0.12)"  :
    glow === "emerald" ? "rgba(0,230,118,0.08)"  :
    glow === "violet"  ? "rgba(139,92,246,0.10)" :
    "transparent";

  const borderColor =
    glow === "crimson" ? "rgba(255,76,76,0.25)"  :
    glow === "emerald" ? "rgba(0,230,118,0.2)"   :
    glow === "violet"  ? "rgba(139,92,246,0.2)"  :
    "rgba(255,255,255,0.08)";

  return (
    <div
      className="rounded-xl p-5"
      style={{ background: glowColor, border: `1px solid ${borderColor}` }}
    >
      <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "#8B9BB4" }}>
        {label}
      </p>
      <div className="text-3xl font-bold font-mono" style={{
        color:
          glow === "crimson" ? "#FF4C4C" :
          glow === "emerald" ? "#00E676" :
          glow === "violet"  ? "#8B5CF6" :
          "#F0F6FC",
        textShadow: glow === "crimson" ? "0 0 20px rgba(255,76,76,0.5)" : undefined,
      }}>
        {value}
      </div>
      {sub && <p className="text-xs mt-1" style={{ color: "#8B9BB4" }}>{sub}</p>}
    </div>
  );
}

function ProjectCard({ p, variant }: { p: HealthScore; variant: "risk" | "healthy" }) {
  const org = p.repo_full_name.split("/")[0];
  const isRisk = variant === "risk";

  return (
    <Link
      href={`/projects/${p.repo_full_name}`}
      className="group flex items-center gap-3 px-4 py-3 rounded-xl transition-all"
      style={{
        background: "rgba(22,27,34,0.6)",
        border: isRisk
          ? "1px solid rgba(255,76,76,0.15)"
          : "1px solid rgba(0,230,118,0.12)",
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.borderColor = isRisk
          ? "rgba(255,76,76,0.35)"
          : "rgba(0,230,118,0.3)";
        (e.currentTarget as HTMLElement).style.boxShadow = isRisk
          ? "0 0 12px rgba(255,76,76,0.1)"
          : "0 0 12px rgba(0,230,118,0.08)";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.borderColor = isRisk
          ? "rgba(255,76,76,0.15)"
          : "rgba(0,230,118,0.12)";
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
      }}
    >
      {/* GitHub avatar */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`https://github.com/${org}.png?size=32`}
        alt={org}
        width={28}
        height={28}
        className="rounded-full shrink-0"
        style={{ border: "1px solid rgba(255,255,255,0.1)" }}
        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
      <span className="flex-1 text-sm font-medium truncate" style={{ color: "#F0F6FC" }}>
        {p.repo_full_name}
      </span>
      <div className="flex items-center gap-2">
        {/* Signal dots */}
        <div className="flex gap-1">
          {[p.commit_score, p.issue_score, p.contributor_score].map((s, i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full"
              style={{
                background:
                  s === null  ? "#374151" :
                  s >= 7      ? "#00E676" :
                  s >= 5      ? "#FBBF24" :
                  "#FF4C4C",
              }}
              title={["Commits", "Issues", "Contributors"][i]}
            />
          ))}
        </div>
        <HealthBadge score={p.health_score} size="sm" />
      </div>
    </Link>
  );
}

export default function HomePage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [atRisk, setAtRisk]   = useState<HealthScore[]>([]);
  const [healthy, setHealthy] = useState<HealthScore[]>([]);
  const [error, setError]     = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getSummary(),
      getHealthScores({ max_score: 10, limit: 5, order: "asc" }),
      getHealthScores({ min_score: 0,  limit: 5, order: "desc" }),
    ])
      .then(([s, risk, top]) => { setSummary(s); setAtRisk(risk); setHealthy(top); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load data"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8"><LoadingSpinner message="Loading command center..." /></div>;
  if (error)   return <div className="p-8 text-sm" style={{ color: "#FF4C4C" }}>Error: {error}</div>;

  return (
    <div className="p-8 max-w-6xl">
      {/* Page header + Agent Pulse */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "#F0F6FC" }}>
            Command Center
          </h1>
          <p className="text-sm mt-1" style={{ color: "#8B9BB4" }}>
            Real-time monitoring across {summary?.total_projects ?? "—"} open-source dependencies
          </p>
        </div>

        {/* Agent Pulse pill */}
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-full"
          style={{
            background: "rgba(139,92,246,0.1)",
            border: "1px solid rgba(139,92,246,0.25)",
          }}
        >
          <span
            className="w-2 h-2 rounded-full animate-agent-pulse"
            style={{ background: "#8B5CF6" }}
          />
          <span className="text-xs font-medium" style={{ color: "#8B5CF6" }}>
            {summary?.last_agent_run
              ? `Last investigation: ${relativeTime(summary.last_agent_run)}`
              : "Agent idle"}
          </span>
        </div>
      </div>

      {/* KPI ribbon */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <KpiCard
          label="Projects Monitored"
          value={summary?.total_projects ?? "—"}
        />
        <KpiCard
          label="Critical Risks"
          value={summary?.critical_count ?? "—"}
          sub={
            summary?.total_projects && summary.total_projects > 0
              ? `${Math.round(((summary.critical_count ?? 0) / summary.total_projects) * 100)}% of portfolio`
              : undefined
          }
          glow="crimson"
        />
        <KpiCard
          label="Avg Health Score"
          value={summary?.avg_health_score?.toFixed(1) ?? "—"}
          sub={
            summary?.projects_assessed_count != null && summary?.total_projects != null
              ? `${summary.projects_assessed_count} of ${summary.total_projects} AI analyzed`
              : undefined
          }
          glow="emerald"
        />
      </div>

      {/* Pipeline timestamp */}
      {summary?.last_pipeline_run && (
        <p className="text-xs mb-8" style={{ color: "#4B5563" }}>
          Pipeline last run: {relativeTime(summary.last_pipeline_run)}
        </p>
      )}

      {/* Top 5 lists */}
      <div className="grid grid-cols-2 gap-6">
        <div>
          <h2
            className="text-xs font-semibold uppercase tracking-widest mb-3"
            style={{ color: "#FF4C4C" }}
          >
            ▲ Top 5 At-Risk
          </h2>
          <div className="space-y-2">
            {atRisk.map((p) => (
              <ProjectCard key={p.repo_full_name} p={p} variant="risk" />
            ))}
            {atRisk.length === 0 && (
              <p className="text-sm" style={{ color: "#4B5563" }}>
                No projects in critical range.
              </p>
            )}
          </div>
        </div>

        <div>
          <h2
            className="text-xs font-semibold uppercase tracking-widest mb-3"
            style={{ color: "#00E676" }}
          >
            ▼ Top 5 Healthy
          </h2>
          <div className="space-y-2">
            {healthy.map((p) => (
              <ProjectCard key={p.repo_full_name} p={p} variant="healthy" />
            ))}
            {healthy.length === 0 && (
              <p className="text-sm" style={{ color: "#4B5563" }}>No data yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
