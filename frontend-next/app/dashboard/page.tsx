"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getHealthScores, getSummary } from "@/lib/api";
import type { HealthScore } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";
import LoadingSpinner from "@/components/LoadingSpinner";

const PAGE_SIZE = 20;

type StatusFilter = "All" | "Critical" | "Warning" | "Healthy";

function statusDot(score: number) {
  if (score >= 7.0) return <span className="text-[#16a34a]">●</span>;
  if (score >= 5.0) return <span className="text-[#ca8a04]">●</span>;
  return <span className="text-[#dc2626]">●</span>;
}

function scoreCell(v: number | null) {
  if (v === null) return <span className="text-gray-300">—</span>;
  return <span className="font-mono text-sm">{v.toFixed(1)}</span>;
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<HealthScore[]>([]);
  const [assessedSet, setAssessedSet] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("All");
  const [minScore, setMinScore] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => {
    Promise.all([getHealthScores(), getSummary()])
      .then(([rows, summary]) => {
        setProjects(rows);
        setAssessedSet(new Set(summary.assessed_repos));
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load")
      )
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return projects.filter((p) => {
      const matchSearch =
        !search || p.repo_full_name.toLowerCase().includes(search.toLowerCase());
      const matchStatus =
        status === "All" ||
        (status === "Critical" && p.health_score < 5) ||
        (status === "Warning" && p.health_score >= 5 && p.health_score < 7) ||
        (status === "Healthy" && p.health_score >= 7);
      const matchMin = p.health_score >= minScore;
      return matchSearch && matchStatus && matchMin;
    });
  }, [projects, search, status, minScore]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading)
    return (
      <div className="p-8">
        <LoadingSpinner message="Loading projects..." />
      </div>
    );
  if (error)
    return <div className="p-8 text-red-600 text-sm">Error: {error}</div>;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Health Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            {projects.length} projects monitored
          </p>
        </div>
        <a
          href={`data:text/csv;charset=utf-8,${encodeURIComponent(
            ["repo,health,commit,issue,pr,contributor,bus_factor"]
              .concat(
                filtered.map((p) =>
                  [
                    p.repo_full_name,
                    p.health_score,
                    p.commit_score ?? "",
                    p.issue_score ?? "",
                    p.pr_score ?? "",
                    p.contributor_score ?? "",
                    p.bus_factor_score ?? "",
                  ].join(",")
                )
              )
              .join("\n")
          )}`}
          download="health_scores.csv"
          className="text-sm text-blue-600 hover:underline"
        >
          Export CSV
        </a>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-5 flex-wrap">
        <input
          type="text"
          placeholder="Search projects..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm w-64"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as StatusFilter);
            setPage(1);
          }}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm"
        >
          {(["All", "Critical", "Warning", "Healthy"] as StatusFilter[]).map(
            (s) => (
              <option key={s}>{s}</option>
            )
          )}
        </select>
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <label>Min score:</label>
          <input
            type="range"
            min={0}
            max={10}
            step={0.5}
            value={minScore}
            onChange={(e) => {
              setMinScore(Number(e.target.value));
              setPage(1);
            }}
            className="w-24"
          />
          <span className="font-mono w-8">{minScore.toFixed(1)}</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-600 w-6"></th>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Project</th>
              <th className="px-3 py-2 text-center font-medium text-gray-600">Health</th>
              <th className="px-3 py-2 text-center font-medium text-gray-600">Commit</th>
              <th className="px-3 py-2 text-center font-medium text-gray-600">Issue</th>
              <th className="px-3 py-2 text-center font-medium text-gray-600">PR</th>
              <th className="px-3 py-2 text-center font-medium text-gray-600">AI</th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((p) => (
              <tr
                key={p.repo_full_name}
                className="border-b border-gray-100 hover:bg-gray-50"
              >
                <td className="px-3 py-2 text-center">
                  {statusDot(p.health_score)}
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={`/projects/${p.repo_full_name}`}
                    className="text-blue-600 hover:underline font-medium"
                  >
                    {p.repo_full_name}
                  </Link>
                </td>
                <td className="px-3 py-2 text-center">
                  <HealthBadge score={p.health_score} size="sm" />
                </td>
                <td className="px-3 py-2 text-center">
                  {scoreCell(p.commit_score)}
                </td>
                <td className="px-3 py-2 text-center">
                  {scoreCell(p.issue_score)}
                </td>
                <td className="px-3 py-2 text-center">
                  {scoreCell(p.pr_score)}
                </td>
                <td className="px-3 py-2 text-center text-gray-400">
                  {assessedSet.has(p.repo_full_name) ? (
                    <span className="text-green-600 font-bold">✓</span>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
            {pageData.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No projects match filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center gap-3 mt-4 text-sm text-gray-600">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-3 py-1 border rounded disabled:opacity-40"
        >
          Previous
        </button>
        <span>
          Page{" "}
          <input
            type="number"
            value={page}
            min={1}
            max={totalPages}
            onChange={(e) =>
              setPage(Math.min(totalPages, Math.max(1, Number(e.target.value))))
            }
            className="border rounded px-1 w-12 text-center"
          />{" "}
          of {totalPages}
        </span>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
          className="px-3 py-1 border rounded disabled:opacity-40"
        >
          Next
        </button>
        <span className="text-gray-400 ml-2">
          {filtered.length} projects
        </span>
      </div>
    </div>
  );
}
