"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getHealthScores, getSummary, getReports, getReport } from "@/lib/api";
import type { HealthScore } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";
import LoadingSpinner from "@/components/LoadingSpinner";

const PAGE_SIZE = 20;
type StatusFilter = "All" | "Critical" | "Warning" | "Healthy";

const SURFACE = "rgba(22,27,34,0.7)";
const BORDER  = "rgba(255,255,255,0.08)";

function statusDot(score: number) {
  const color = score >= 7 ? "#00E676" : score >= 5 ? "#FBBF24" : "#FF4C4C";
  return (
    <span
      className="inline-block w-2 h-2 rounded-full"
      style={{
        background: color,
        boxShadow: `0 0 6px ${color}`,
      }}
    />
  );
}

function GlowScore({ v }: { v: number | null }) {
  if (v === null) return <span style={{ color: "#374151" }}>—</span>;
  const color = v >= 7 ? "#00E676" : v >= 5 ? "#FBBF24" : "#FF4C4C";
  return (
    <span
      className="font-mono text-xs px-1.5 py-0.5 rounded"
      style={{
        color,
        background: `${color}14`,
        border: `1px solid ${color}33`,
      }}
    >
      {v.toFixed(1)}
    </span>
  );
}

function QuickViewDrawer({
  project,
  assessed,
  assessmentText,
  onClose,
}: {
  project: HealthScore;
  assessed: boolean;
  assessmentText: string | null;
  onClose: () => void;
}) {
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.4)" }}
        onClick={onClose}
      />
      {/* Drawer */}
      <div
        className="fixed right-0 top-0 bottom-0 z-50 w-96 flex flex-col animate-slide-right scrollbar-dark overflow-y-auto"
        style={{
          background: "#0B0E14",
          borderLeft: "1px solid rgba(139,92,246,0.3)",
          boxShadow: "-8px 0 40px rgba(0,0,0,0.5)",
        }}
      >
        {/* Drawer header */}
        <div
          className="flex items-center justify-between px-5 py-4 shrink-0"
          style={{ borderBottom: BORDER }}
        >
          <div className="flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`https://github.com/${project.repo_full_name.split("/")[0]}.png?size=32`}
              alt=""
              width={24}
              height={24}
              className="rounded-full"
              style={{ border: "1px solid rgba(255,255,255,0.1)" }}
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
            <span className="text-sm font-semibold" style={{ color: "#F0F6FC" }}>
              {project.repo_full_name}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-lg leading-none"
            style={{ color: "#8B9BB4" }}
          >
            ×
          </button>
        </div>

        {/* Health score + link */}
        <div className="px-5 py-4" style={{ borderBottom: BORDER }}>
          <div className="flex items-center justify-between mb-3">
            <HealthBadge score={project.health_score} size="lg" />
            <a
              href={`https://github.com/${project.repo_full_name}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs px-3 py-1.5 rounded"
              style={{
                color: "#8B5CF6",
                border: "1px solid rgba(139,92,246,0.3)",
              }}
            >
              GitHub ↗
            </a>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[
              ["Commit", project.commit_score],
              ["Issue",  project.issue_score],
              ["PR",     project.pr_score],
            ].map(([label, val]) => (
              <div
                key={label as string}
                className="text-center py-2 rounded"
                style={{ background: SURFACE, border: BORDER }}
              >
                <p className="font-mono text-sm" style={{ color: "#F0F6FC" }}>
                  {val !== null ? (val as number).toFixed(1) : "—"}
                </p>
                <p className="text-xs mt-0.5" style={{ color: "#8B9BB4" }}>{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* AI assessment snippet */}
        <div className="px-5 py-4 flex-1">
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: "#8B5CF6" }}>
            AI Assessment
          </p>
          {assessed && assessmentText ? (
            <pre
              className="text-xs leading-relaxed whitespace-pre-wrap"
              style={{ color: "#8B9BB4", fontFamily: "'JetBrains Mono', monospace" }}
            >
              {assessmentText.slice(0, 500)}{assessmentText.length > 500 ? "…" : ""}
            </pre>
          ) : (
            <p className="text-xs" style={{ color: "#4B5563" }}>
              {assessed ? "Loading assessment…" : "No assessment yet. Run the agent to analyze this project."}
            </p>
          )}
        </div>

        {/* Deep dive button */}
        <div className="px-5 py-4 shrink-0" style={{ borderTop: BORDER }}>
          <Link
            href={`/projects/${project.repo_full_name}`}
            className="block w-full py-2.5 text-sm font-medium text-center rounded-lg transition-colors"
            style={{
              background: "rgba(139,92,246,0.15)",
              border: "1px solid rgba(139,92,246,0.3)",
              color: "#8B5CF6",
            }}
            onClick={onClose}
          >
            Deep Dive →
          </Link>
        </div>
      </div>
    </>
  );
}

function extractSnippet(markdown: string, repoName: string): string | null {
  const lines = markdown.split("\n");
  let inSection = false;
  const buf: string[] = [];
  for (const line of lines) {
    if (line.startsWith("### ") && line.includes(repoName)) { inSection = true; continue; }
    if (inSection) {
      if (line.startsWith("### ") || line.startsWith("## ")) break;
      buf.push(line);
    }
  }
  const text = buf.join("\n").trim();
  return text.length > 0 ? text : null;
}

export default function DashboardPage() {
  const [projects, setProjects]       = useState<HealthScore[]>([]);
  const [assessedSet, setAssessedSet] = useState<Set<string>>(new Set());
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [search, setSearch]           = useState("");
  const [status, setStatus]           = useState<StatusFilter>("All");
  const [minScore, setMinScore]       = useState(0);
  const [page, setPage]               = useState(1);
  const [drawer, setDrawer]           = useState<HealthScore | null>(null);
  const [drawerText, setDrawerText]   = useState<string | null>(null);
  const [latestReport, setLatestReport] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getHealthScores(), getSummary()])
      .then(([rows, summary]) => {
        setProjects(rows);
        setAssessedSet(new Set(summary.assessed_repos));
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));

    // Fetch latest report text for the drawer
    getReports()
      .then((rs) => rs.length > 0 ? getReport(rs[0].filename) : Promise.resolve(null))
      .then((text) => setLatestReport(text))
      .catch(() => {/* non-fatal */});
  }, []);

  function openDrawer(p: HealthScore) {
    setDrawer(p);
    setDrawerText(null);
    if (latestReport) {
      const snippet = extractSnippet(latestReport, p.repo_full_name);
      setDrawerText(snippet);
    }
  }

  const filtered = useMemo(() => projects.filter((p) => {
    const s = p.health_score;
    return (
      (!search || p.repo_full_name.toLowerCase().includes(search.toLowerCase())) &&
      (status === "All" ||
        (status === "Critical" && s < 5) ||
        (status === "Warning"  && s >= 5 && s < 7) ||
        (status === "Healthy"  && s >= 7)) &&
      s >= minScore
    );
  }), [projects, search, status, minScore]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData   = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const csvHref = `data:text/csv;charset=utf-8,${encodeURIComponent(
    ["repo,health,commit,issue,pr,contributor,bus_factor"]
      .concat(filtered.map((p) =>
        [p.repo_full_name, p.health_score, p.commit_score ?? "", p.issue_score ?? "",
          p.pr_score ?? "", p.contributor_score ?? "", p.bus_factor_score ?? ""].join(",")
      ))
      .join("\n")
  )}`;

  if (loading) return <div className="p-8"><LoadingSpinner message="Loading projects..." /></div>;
  if (error)   return <div className="p-8 text-sm" style={{ color: "#FF4C4C" }}>Error: {error}</div>;

  const SEGMENT_FILTERS: StatusFilter[] = ["All", "Critical", "Warning", "Healthy"];
  const segmentColor = (s: StatusFilter) =>
    s === "Critical" ? "#FF4C4C" :
    s === "Warning"  ? "#FBBF24" :
    s === "Healthy"  ? "#00E676" :
    "#F0F6FC";

  return (
    <div className="p-8" style={{ color: "#F0F6FC" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Health Dashboard</h1>
          <p className="text-sm mt-1" style={{ color: "#8B9BB4" }}>
            {projects.length} projects monitored
          </p>
        </div>
        <a
          href={csvHref}
          download="health_scores.csv"
          className="text-xs px-4 py-2 rounded-lg transition-colors"
          style={{
            color: "#8B9BB4",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          ↓ Export CSV
        </a>
      </div>

      {/* Glassmorphism toolbar */}
      <div
        className="flex items-center gap-4 px-4 py-3 rounded-xl mb-5 flex-wrap"
        style={{
          background: "rgba(22,27,34,0.8)",
          backdropFilter: "blur(10px)",
          border: BORDER,
        }}
      >
        {/* Search */}
        <input
          type="text"
          placeholder="Search projects..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="bg-transparent text-sm flex-1 min-w-48"
          style={{
            color: "#F0F6FC",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: "8px",
            padding: "6px 12px",
          }}
        />

        {/* Segmented filter */}
        <div
          className="flex rounded-lg overflow-hidden"
          style={{ border: "1px solid rgba(255,255,255,0.1)" }}
        >
          {SEGMENT_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => { setStatus(s); setPage(1); }}
              className="px-4 py-1.5 text-xs font-medium transition-colors"
              style={{
                background: status === s ? "rgba(139,92,246,0.2)" : "transparent",
                color: status === s ? segmentColor(s) : "#8B9BB4",
                borderRight: s !== "Healthy" ? "1px solid rgba(255,255,255,0.08)" : "none",
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Min score slider */}
        <div className="flex items-center gap-2 text-xs" style={{ color: "#8B9BB4" }}>
          <span>Min:</span>
          <input
            type="range" min={0} max={10} step={0.5} value={minScore}
            onChange={(e) => { setMinScore(Number(e.target.value)); setPage(1); }}
            className="w-20 accent-violet-500"
          />
          <span className="font-mono w-6" style={{ color: "#8B5CF6" }}>{minScore.toFixed(0)}</span>
        </div>
      </div>

      {/* Intelligence grid */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: BORDER }}
      >
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: "rgba(22,27,34,0.9)", borderBottom: BORDER }}>
              {["", "Project", "Health", "Commit", "Issue", "PR", "AI"].map((h, i) => (
                <th
                  key={i}
                  className={`px-3 py-3 font-medium text-xs uppercase tracking-wider ${i > 1 ? "text-center" : "text-left"}`}
                  style={{ color: "#8B9BB4" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.map((p) => {
              const isRisk = p.health_score < 5;
              const isWarn = p.health_score >= 5 && p.health_score < 7;
              const accentColor = isRisk ? "#FF4C4C" : isWarn ? "#FBBF24" : "#00E676";

              return (
                <tr
                  key={p.repo_full_name}
                  className="cursor-pointer transition-colors group"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                  onClick={() => openDrawer(p)}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.background = "rgba(22,27,34,0.8)";
                    const cells = (e.currentTarget as HTMLElement).querySelectorAll("td");
                    if (cells[0]) (cells[0] as HTMLElement).style.borderLeftColor = accentColor;
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = "transparent";
                    const cells = (e.currentTarget as HTMLElement).querySelectorAll("td");
                    if (cells[0]) (cells[0] as HTMLElement).style.borderLeftColor = "transparent";
                  }}
                >
                  <td
                    className="px-3 py-3 text-center transition-colors"
                    style={{ borderLeft: "3px solid transparent" }}
                  >
                    {statusDot(p.health_score)}
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`https://github.com/${p.repo_full_name.split("/")[0]}.png?size=24`}
                        alt=""
                        width={18}
                        height={18}
                        className="rounded-full shrink-0"
                        style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                      <span
                        className="font-medium hover:underline"
                        style={{ color: "#8B5CF6" }}
                        onClick={(e) => { e.stopPropagation(); }}
                      >
                        <Link href={`/projects/${p.repo_full_name}`} onClick={(e) => e.stopPropagation()}>
                          {p.repo_full_name}
                        </Link>
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <HealthBadge score={p.health_score} size="sm" />
                  </td>
                  <td className="px-3 py-3 text-center"><GlowScore v={p.commit_score} /></td>
                  <td className="px-3 py-3 text-center"><GlowScore v={p.issue_score} /></td>
                  <td className="px-3 py-3 text-center"><GlowScore v={p.pr_score} /></td>
                  <td className="px-3 py-3 text-center">
                    {assessedSet.has(p.repo_full_name) ? (
                      <span
                        className="text-xs font-bold px-1.5 py-0.5 rounded"
                        style={{
                          color: "#8B5CF6",
                          background: "rgba(139,92,246,0.1)",
                          border: "1px solid rgba(139,92,246,0.25)",
                        }}
                      >
                        AI
                      </span>
                    ) : (
                      <span style={{ color: "#374151" }}>—</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {pageData.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center" style={{ color: "#4B5563" }}>
                  No projects match filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center gap-3 mt-4 text-sm" style={{ color: "#8B9BB4" }}>
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-3 py-1 rounded transition-colors disabled:opacity-30"
          style={{ border: BORDER }}
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
            onChange={(e) => setPage(Math.min(totalPages, Math.max(1, Number(e.target.value))))}
            className="bg-transparent text-center font-mono w-10"
            style={{ border: BORDER, borderRadius: "4px", color: "#F0F6FC" }}
          />{" "}
          of {totalPages}
        </span>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
          className="px-3 py-1 rounded transition-colors disabled:opacity-30"
          style={{ border: BORDER }}
        >
          Next
        </button>
        <span className="ml-2 text-xs" style={{ color: "#4B5563" }}>{filtered.length} projects</span>
      </div>

      {/* Quick-view drawer */}
      {drawer && (
        <QuickViewDrawer
          project={drawer}
          assessed={assessedSet.has(drawer.repo_full_name)}
          assessmentText={drawerText}
          onClose={() => setDrawer(null)}
        />
      )}
    </div>
  );
}
