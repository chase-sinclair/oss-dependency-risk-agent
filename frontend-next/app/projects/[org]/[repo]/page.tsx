"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getProject, getReports, getReport } from "@/lib/api";
import type { HealthScore } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";
import LoadingSpinner from "@/components/LoadingSpinner";

const BORDER  = "rgba(255,255,255,0.08)";
const SURFACE = "rgba(22,27,34,0.7)";

interface Metric {
  label: string;
  value: number | null;
}

function MetricCard({ label, value }: Metric) {
  const score = value ?? 0;
  const barColor =
    score >= 7 ? "#00E676" :
    score >= 5 ? "#FBBF24" :
    "#FF4C4C";

  return (
    <div
      className="rounded-xl p-4"
      style={{ background: SURFACE, border: BORDER }}
    >
      <p className="text-xs uppercase tracking-wider mb-2" style={{ color: "#8B9BB4" }}>
        {label}
      </p>
      <div className="flex items-center gap-2 mb-3">
        <span
          className="text-2xl font-bold font-mono"
          style={{ color: value !== null ? barColor : "#374151" }}
        >
          {value !== null ? value.toFixed(1) : "—"}
        </span>
        {value !== null && <HealthBadge score={value} size="sm" />}
      </div>
      {value !== null && (
        <div
          className="h-1 rounded-full overflow-hidden"
          style={{ background: "rgba(255,255,255,0.06)" }}
        >
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${Math.min(100, (score / 10) * 100)}%`,
              background: barColor,
              boxShadow: `0 0 6px ${barColor}`,
            }}
          />
        </div>
      )}
    </div>
  );
}

function extractAssessment(markdown: string, repoName: string): string | null {
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

export default function ProjectDetailPage() {
  const params   = useParams();
  const org      = params.org as string;
  const repo     = params.repo as string;
  const repoName = `${org}/${repo}`;

  const [project, setProject]       = useState<HealthScore | null>(null);
  const [assessment, setAssessment] = useState<string | null>(null);
  const [assessedAt, setAssessedAt] = useState<string | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const p = await getProject(org, repo);
        setProject(p);
        const reports = await getReports();
        if (reports.length > 0) {
          const content = await getReport(reports[0].filename);
          const found = extractAssessment(content, repoName);
          if (found) { setAssessment(found); setAssessedAt(reports[0].timestamp); }
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load project");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [org, repo, repoName]);

  if (loading) return <div className="p-8"><LoadingSpinner message={`Loading ${repoName}...`} /></div>;
  if (error)   return <div className="p-8 text-sm" style={{ color: "#FF4C4C" }}>Error: {error}</div>;
  if (!project) return <div className="p-8 text-sm" style={{ color: "#8B9BB4" }}>Project not found.</div>;

  const metrics: Metric[] = [
    { label: "Commit Frequency",   value: project.commit_score },
    { label: "Issue Resolution",   value: project.issue_score },
    { label: "PR Merge Rate",      value: project.pr_score },
    { label: "Contributor Diversity", value: project.contributor_score },
    { label: "Bus Factor",         value: project.bus_factor_score },
    { label: "Overall Health",     value: project.health_score },
  ];

  return (
    <div className="p-8 max-w-4xl" style={{ color: "#F0F6FC" }}>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`https://github.com/${org}.png?size=48`}
            alt={org}
            width={40}
            height={40}
            className="rounded-full"
            style={{ border: "1px solid rgba(255,255,255,0.1)" }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
          <div>
            <h1 className="text-2xl font-bold">{repoName}</h1>
            {project.computed_at && (
              <p className="text-xs mt-0.5" style={{ color: "#8B9BB4" }}>
                Scored: {project.computed_at}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <HealthBadge score={project.health_score} size="lg" />
          <a
            href={`https://github.com/${repoName}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs px-4 py-2 rounded-lg transition-colors"
            style={{
              color: "#8B5CF6",
              border: "1px solid rgba(139,92,246,0.3)",
              background: "rgba(139,92,246,0.07)",
            }}
          >
            GitHub ↗
          </a>
        </div>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {metrics.map((m) => (
          <MetricCard key={m.label} {...m} />
        ))}
      </div>

      {/* AI Assessment */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#8B5CF6" }}>
            AI Risk Assessment
          </h2>
          {assessedAt && (
            <span className="text-xs" style={{ color: "#4B5563" }}>
              Last assessed: {assessedAt}
            </span>
          )}
        </div>

        {assessment ? (
          <div
            className="rounded-xl overflow-hidden"
            style={{ border: "1px solid rgba(139,92,246,0.2)" }}
          >
            {/* Mac chrome */}
            <div
              className="flex items-center gap-1.5 px-4 py-2.5"
              style={{ background: "#0B0E14", borderBottom: "1px solid rgba(255,255,255,0.06)" }}
            >
              <span className="w-3 h-3 rounded-full" style={{ background: "#FF5F57" }} />
              <span className="w-3 h-3 rounded-full" style={{ background: "#FEBC2E" }} />
              <span className="w-3 h-3 rounded-full" style={{ background: "#28C840" }} />
              <span className="ml-3 text-xs font-mono" style={{ color: "#4B5563" }}>
                {repoName}.assessment
              </span>
            </div>
            <pre
              className="p-5 text-sm leading-relaxed whitespace-pre-wrap overflow-x-auto scrollbar-dark"
              style={{
                background: "#060A0F",
                color: "#8B9BB4",
                fontFamily: "'JetBrains Mono', 'Courier New', monospace",
              }}
            >
              {assessment}
            </pre>
          </div>
        ) : (
          <div
            className="rounded-xl p-8 text-center"
            style={{ background: SURFACE, border: BORDER }}
          >
            <p className="text-sm mb-4" style={{ color: "#4B5563" }}>
              No assessment available. Run the agent to analyze this project.
            </p>
            <Link
              href="/agent"
              className="text-sm px-5 py-2.5 rounded-lg inline-block"
              style={{
                color: "#8B5CF6",
                border: "1px solid rgba(139,92,246,0.3)",
                background: "rgba(139,92,246,0.07)",
              }}
            >
              Open Agent Control Room →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
