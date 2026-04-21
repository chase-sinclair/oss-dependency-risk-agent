"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHealthScores, getSummary } from "@/lib/api";
import type { HealthScore, Summary } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";
import LoadingSpinner from "@/components/LoadingSpinner";

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function HomePage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [atRisk, setAtRisk] = useState<HealthScore[]>([]);
  const [healthy, setHealthy] = useState<HealthScore[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getSummary(),
      getHealthScores({ max_score: 10, limit: 5, order: "asc" }),
      getHealthScores({ min_score: 0, limit: 5, order: "desc" }),
    ])
      .then(([s, risk, top]) => {
        setSummary(s);
        setAtRisk(risk);
        setHealthy(top);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load data")
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="p-8">
        <LoadingSpinner message="Loading dashboard..." />
      </div>
    );
  if (error)
    return (
      <div className="p-8 text-red-600 text-sm">
        Error: {error}
      </div>
    );

  return (
    <div className="p-8 max-w-6xl">
      <h1 className="text-2xl font-bold mb-1">Executive Summary</h1>
      <p className="text-gray-500 text-sm mb-6">
        Real-time health monitoring across {summary?.total_projects ?? "—"} open-source
        dependencies.
      </p>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard label="Projects Monitored" value={summary?.total_projects ?? "—"} />
        <StatCard
          label="Critical Risks"
          value={summary?.critical_count ?? "—"}
          sub={`${summary?.warning_count ?? "—"} warnings`}
        />
        <StatCard
          label="Avg Health Score"
          value={summary?.avg_health_score?.toFixed(1) ?? "—"}
          sub={`${summary?.projects_assessed_count ?? 0} AI assessed`}
        />
      </div>

      {/* Timestamps */}
      {(summary?.last_pipeline_run || summary?.last_agent_run) && (
        <div className="flex gap-6 text-xs text-gray-400 mb-8">
          {summary.last_pipeline_run && (
            <span>Pipeline last run: {summary.last_pipeline_run}</span>
          )}
          {summary.last_agent_run && (
            <span>Agent last run: {summary.last_agent_run}</span>
          )}
        </div>
      )}

      {/* At-risk / healthy */}
      <div className="grid grid-cols-2 gap-6">
        <div>
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
            Top 5 At-Risk
          </h2>
          <div className="space-y-2">
            {atRisk.map((p) => (
              <Link
                key={p.repo_full_name}
                href={`/projects/${p.repo_full_name}`}
                className="flex items-center justify-between px-4 py-3 border border-red-100 rounded-lg hover:bg-red-50"
              >
                <span className="text-sm font-medium text-gray-800">
                  {p.repo_full_name}
                </span>
                <HealthBadge score={p.health_score} size="sm" />
              </Link>
            ))}
            {atRisk.length === 0 && (
              <p className="text-sm text-gray-400">No projects in critical range.</p>
            )}
          </div>
        </div>

        <div>
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
            Top 5 Healthy
          </h2>
          <div className="space-y-2">
            {healthy.map((p) => (
              <Link
                key={p.repo_full_name}
                href={`/projects/${p.repo_full_name}`}
                className="flex items-center justify-between px-4 py-3 border border-green-100 rounded-lg hover:bg-green-50"
              >
                <span className="text-sm font-medium text-gray-800">
                  {p.repo_full_name}
                </span>
                <HealthBadge score={p.health_score} size="sm" />
              </Link>
            ))}
            {healthy.length === 0 && (
              <p className="text-sm text-gray-400">No data yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
