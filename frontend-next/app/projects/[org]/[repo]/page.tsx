"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getProject, getReports, getReport } from "@/lib/api";
import type { HealthScore } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";
import LoadingSpinner from "@/components/LoadingSpinner";

interface Metric {
  label: string;
  value: number | null;
}

function MetricCard({ label, value }: Metric) {
  const score = value ?? 0;

  function barColor(s: number) {
    if (s >= 7) return "bg-[#16a34a]";
    if (s >= 5) return "bg-[#ca8a04]";
    return "bg-[#dc2626]";
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl font-bold font-mono">
          {value !== null ? value.toFixed(1) : "—"}
        </span>
        {value !== null && <HealthBadge score={value} size="sm" />}
      </div>
      {value !== null && (
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${barColor(score)}`}
            style={{ width: `${Math.min(100, (score / 10) * 100)}%` }}
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
    if (line.startsWith("### ") && line.includes(repoName)) {
      inSection = true;
      continue;
    }
    if (inSection) {
      if (line.startsWith("### ") || line.startsWith("## ")) break;
      buf.push(line);
    }
  }
  const text = buf.join("\n").trim();
  return text.length > 0 ? text : null;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const org = params.org as string;
  const repo = params.repo as string;
  const repoName = `${org}/${repo}`;

  const [project, setProject] = useState<HealthScore | null>(null);
  const [assessment, setAssessment] = useState<string | null>(null);
  const [assessedAt, setAssessedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const p = await getProject(org, repo);
        setProject(p);

        const reports = await getReports();
        if (reports.length > 0) {
          const content = await getReport(reports[0].filename);
          const found = extractAssessment(content, repoName);
          if (found) {
            setAssessment(found);
            setAssessedAt(reports[0].timestamp);
          }
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load project");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [org, repo, repoName]);

  if (loading)
    return (
      <div className="p-8">
        <LoadingSpinner message={`Loading ${repoName}...`} />
      </div>
    );
  if (error)
    return <div className="p-8 text-red-600 text-sm">Error: {error}</div>;
  if (!project)
    return <div className="p-8 text-gray-500">Project not found.</div>;

  const metrics: Metric[] = [
    { label: "Commit Frequency", value: project.commit_score },
    { label: "Issue Resolution", value: project.issue_score },
    { label: "PR Merge Rate", value: project.pr_score },
    { label: "Contributor Diversity", value: project.contributor_score },
    { label: "Bus Factor", value: project.bus_factor_score },
    { label: "Overall Health", value: project.health_score },
  ];

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{repoName}</h1>
          {project.computed_at && (
            <p className="text-xs text-gray-400 mt-1">
              Scored at: {project.computed_at}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <HealthBadge score={project.health_score} size="lg" />
          <a
            href={`https://github.com/${repoName}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 border border-blue-200 rounded px-3 py-1.5 hover:bg-blue-50"
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
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            AI Risk Assessment
          </h2>
          {assessedAt && (
            <span className="text-xs text-gray-400">
              Last assessed: {assessedAt}
            </span>
          )}
        </div>

        {assessment ? (
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: "#0d1117" }}
          >
            {/* Mac chrome */}
            <div className="flex items-center gap-1.5 px-3 py-2 bg-[#161b22]">
              <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
              <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
              <span className="w-3 h-3 rounded-full bg-[#28c840]" />
              <span className="ml-3 text-xs text-gray-500 font-mono">
                assessment.txt
              </span>
            </div>
            <pre
              className="p-4 text-green-300 text-sm font-mono whitespace-pre-wrap leading-relaxed overflow-x-auto"
              style={{ fontFamily: "'Courier New', monospace" }}
            >
              {assessment}
            </pre>
          </div>
        ) : (
          <div className="border border-gray-200 rounded-lg p-6 text-center">
            <p className="text-gray-500 text-sm mb-3">
              No assessment available for this project.
            </p>
            <Link
              href="/agent"
              className="text-sm text-blue-600 border border-blue-200 rounded px-4 py-2 hover:bg-blue-50"
            >
              Open Agent Control Room →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
