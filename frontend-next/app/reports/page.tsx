"use client";

import { useEffect, useState } from "react";
import { getReports, getReport } from "@/lib/api";
import type { ReportMeta } from "@/types/api";
import LoadingSpinner from "@/components/LoadingSpinner";

const BORDER  = "rgba(255,255,255,0.08)";
const SURFACE = "rgba(22,27,34,0.7)";
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/* ── Markdown renderer (dark-themed) ────────────────────────────────────────── */

function renderMarkdown(text: string): string {
  function esc(s: string): string {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function fmtIso(iso: string): string {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const date = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    const time = d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
    return `${date} ${time}`;
  }

  function inline(s: string): string {
    return esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong style='color:#F0F6FC'>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, `<code style='background:rgba(139,92,246,0.1);color:#8B5CF6;padding:1px 4px;border-radius:3px;font-family:JetBrains Mono,monospace;font-size:11px'>$1</code>`)
      .replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\s<]*/g, (m) => fmtIso(m));
  }

  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let inCode = false;

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) { out.push("</code></pre>"); inCode = false; }
      else { out.push(`<pre style='background:#060A0F;border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:12px;font-size:11px;overflow-x:auto;margin:8px 0'><code style='color:#8B9BB4;font-family:JetBrains Mono,monospace'>`); inCode = true; }
      continue;
    }
    if (inCode) { out.push(esc(line)); continue; }

    if (line.startsWith("# "))
      out.push(`<h1 style='font-size:1.5rem;font-weight:700;margin:24px 0 12px;color:#F0F6FC'>${inline(line.slice(2))}</h1>`);
    else if (line.startsWith("## "))
      out.push(`<h2 style='font-size:1.1rem;font-weight:600;margin:20px 0 8px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.08);color:#F0F6FC'>${inline(line.slice(3))}</h2>`);
    else if (line.startsWith("### "))
      out.push(`<h3 style='font-size:0.95rem;font-weight:600;margin:16px 0 6px;color:#8B5CF6'>${inline(line.slice(4))}</h3>`);
    else if (line.startsWith("#### "))
      out.push(`<h4 style='font-weight:500;margin:12px 0 4px;color:#F0F6FC'>${inline(line.slice(5))}</h4>`);
    else if (line.startsWith("- ") || line.startsWith("* "))
      out.push(`<li style='margin-left:20px;list-style:disc;font-size:13px;color:#8B9BB4;line-height:1.6'>${inline(line.slice(2))}</li>`);
    else if (line.trim() === "---")
      out.push(`<hr style='border-color:rgba(255,255,255,0.08);margin:16px 0'/>`);
    else if (line.trim() === "")
      out.push("<br/>");
    else
      out.push(`<p style='font-size:13px;line-height:1.7;color:#8B9BB4;margin-bottom:4px'>${inline(line)}</p>`);
  }
  return out.join("\n");
}

/* ── Parse recommendation distribution from report text ─────────────────────── */

function parseDistribution(text: string): { replace: number; upgrade: number; monitor: number } {
  // Primary: parse the canonical summary line written by the agent:
  //   **Summary:** N REPLACE  |  N UPGRADE  |  N MONITOR
  const m = text.match(
    /\*\*Summary:\*\*\s+(\d+)\s+REPLACE\s+\|[^|]*(\d+)\s+UPGRADE\s+\|[^|]*(\d+)\s+MONITOR/i
  );
  if (m) {
    return {
      replace: parseInt(m[1], 10),
      upgrade: parseInt(m[2], 10),
      monitor: parseInt(m[3], 10),
    };
  }
  // Fallback: count ### project headers under each section heading
  const recs = { replace: 0, upgrade: 0, monitor: 0 };
  let current: "replace" | "upgrade" | "monitor" | null = null;
  for (const line of text.split("\n")) {
    if (/^##\s/.test(line)) {
      const lower = line.toLowerCase();
      current = lower.includes("replace") ? "replace" : lower.includes("upgrade") ? "upgrade" : lower.includes("monitor") ? "monitor" : null;
    } else if (/^###\s/.test(line) && current) {
      recs[current]++;
    }
  }
  return recs;
}

/* ── Chronicle card (sidebar) ───────────────────────────────────────────────── */

function ChronicleCard({
  report,
  active,
  dist,
  onClick,
}: {
  report: ReportMeta;
  active: boolean;
  dist: { replace: number; upgrade: number; monitor: number } | null;
  onClick: () => void;
}) {
  const total = dist ? dist.replace + dist.upgrade + dist.monitor : 0;
  const rPct  = total > 0 ? (dist!.replace / total) * 100 : 0;
  const uPct  = total > 0 ? (dist!.upgrade / total) * 100 : 0;
  const mPct  = total > 0 ? (dist!.monitor / total) * 100 : 100;

  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-3 rounded-lg transition-all mb-1.5"
      style={{
        background: active ? "rgba(139,92,246,0.1)" : SURFACE,
        border: active ? "1px solid rgba(139,92,246,0.4)" : `1px solid ${BORDER}`,
        boxShadow: active ? "0 0 12px rgba(139,92,246,0.1)" : "none",
      }}
    >
      <div className="text-xs font-mono mb-1" style={{ color: "#F0F6FC" }}>
        {report.timestamp}
      </div>
      <div className="text-xs mb-2" style={{ color: "#8B9BB4" }}>
        {report.project_count} projects assessed
        {dist && dist.replace > 0 && (
          <span style={{ color: "#FF4C4C" }}> · {dist.replace} critical</span>
        )}
      </div>
      {/* Risk distribution bar */}
      {dist && total > 0 && (
        <div className="flex h-1 rounded-full overflow-hidden gap-px">
          {rPct > 0 && <div style={{ width: `${rPct}%`, background: "#FF4C4C" }} />}
          {uPct > 0 && <div style={{ width: `${uPct}%`, background: "#FBBF24" }} />}
          {mPct > 0 && <div style={{ width: `${mPct}%`, background: "#00E676" }} />}
        </div>
      )}
    </button>
  );
}

/* ── Executive briefing bar ─────────────────────────────────────────────────── */

function ExecutiveBriefing({
  dist,
  report,
}: {
  dist: { replace: number; upgrade: number; monitor: number };
  report: ReportMeta;
}) {
  const total = dist.replace + dist.upgrade + dist.monitor;
  const rPct  = total > 0 ? (dist.replace / total) * 100 : 0;
  const uPct  = total > 0 ? (dist.upgrade / total) * 100 : 0;
  const mPct  = total > 0 ? (dist.monitor / total) * 100 : 100;

  return (
    <div
      className="rounded-xl p-5 mb-6"
      style={{ background: SURFACE, border: BORDER }}
    >
      {/* Bottom line counts */}
      <div className="flex items-center gap-6 mb-4">
        {[
          { label: "REPLACE", count: dist.replace, color: "#FF4C4C" },
          { label: "UPGRADE", count: dist.upgrade, color: "#FBBF24" },
          { label: "MONITOR", count: dist.monitor, color: "#00E676" },
        ].map(({ label, count, color }) => (
          <div key={label} className="flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono" style={{ color }}>{count}</span>
            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "#8B9BB4" }}>
              {label}
            </span>
          </div>
        ))}
        <div className="ml-auto">
          <a
            href={`${API_BASE}/api/reports/${encodeURIComponent(report.filename)}`}
            download={report.filename}
            className="text-xs px-4 py-2 rounded-lg"
            style={{
              color: "#8B5CF6",
              border: "1px solid rgba(139,92,246,0.3)",
              background: "rgba(139,92,246,0.07)",
            }}
          >
            ↓ Download
          </a>
        </div>
      </div>
      {/* Multi-colored distribution bar */}
      {total > 0 && (
        <div className="flex h-2 rounded-full overflow-hidden gap-px">
          {rPct > 0 && <div style={{ width: `${rPct}%`, background: "#FF4C4C", opacity: 0.85 }} />}
          {uPct > 0 && <div style={{ width: `${uPct}%`, background: "#FBBF24", opacity: 0.85 }} />}
          {mPct > 0 && <div style={{ width: `${mPct}%`, background: "#00E676", opacity: 0.85 }} />}
        </div>
      )}
    </div>
  );
}

export default function ReportsPage() {
  const [reports, setReports]           = useState<ReportMeta[]>([]);
  const [selected, setSelected]         = useState<ReportMeta | null>(null);
  const [content, setContent]           = useState<string>("");
  const [loadingList, setLoadingList]   = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [error, setError]               = useState<string | null>(null);
  const [distMap, setDistMap]           = useState<Map<string, { replace: number; upgrade: number; monitor: number }>>(new Map());

  function loadReportList(autoSelectFirst = false) {
    // Initial load shows full spinner; manual refresh just spins the button
    const isInitial = loadingList || reports.length === 0;
    if (isInitial) setLoadingList(true);
    else setRefreshing(true);

    const prevCount = reports.length;
    getReports()
      .then((rs) => {
        setReports(rs);
        // Auto-select on first load, or when a new report has appeared
        if ((autoSelectFirst || rs.length > prevCount) && rs.length > 0) {
          selectReport(rs[0]);
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load reports"))
      .finally(() => { setLoadingList(false); setRefreshing(false); });
  }

  useEffect(() => {
    loadReportList(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectReport(r: ReportMeta) {
    setSelected(r);
    setLoadingContent(true);
    setContent("");
    getReport(r.filename)
      .then((text) => {
        setContent(text);
        const dist = parseDistribution(text);
        setDistMap((prev) => new Map(prev).set(r.filename, dist));
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load report"))
      .finally(() => setLoadingContent(false));
  }

  if (loadingList)
    return <div className="p-8"><LoadingSpinner message="Loading intelligence library..." /></div>;
  if (error)
    return <div className="p-8 text-sm" style={{ color: "#FF4C4C" }}>Error: {error}</div>;

  const activeDist = selected ? distMap.get(selected.filename) ?? null : null;

  return (
    <div className="flex h-full" style={{ color: "#F0F6FC" }}>
      {/* Chronicle sidebar */}
      <aside
        className="w-64 p-4 overflow-y-auto shrink-0 scrollbar-dark"
        style={{ borderRight: BORDER }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2
            className="text-xs font-semibold uppercase tracking-widest"
            style={{ color: "#8B9BB4" }}
          >
            Intelligence Archive
          </h2>
          <button
            onClick={() => loadReportList(false)}
            disabled={refreshing}
            className="text-xs px-2 py-1 rounded transition-colors disabled:opacity-40"
            style={{ color: "#8B5CF6", border: "1px solid rgba(139,92,246,0.2)" }}
            title="Refresh report list"
          >
            <span className={refreshing ? "inline-block animate-spin" : ""}>↻</span>
          </button>
        </div>
        {reports.length === 0 && (
          <p className="text-xs" style={{ color: "#4B5563" }}>
            No reports found. Run the agent to generate reports.
          </p>
        )}
        {reports.map((r) => (
          <ChronicleCard
            key={r.filename}
            report={r}
            active={selected?.filename === r.filename}
            dist={distMap.get(r.filename) ?? null}
            onClick={() => selectReport(r)}
          />
        ))}
      </aside>

      {/* Main content */}
      <div className="flex-1 p-6 overflow-y-auto scrollbar-dark">
        {selected && activeDist && (
          <ExecutiveBriefing dist={activeDist} report={selected} />
        )}

        {loadingContent && <LoadingSpinner message="Loading report..." />}

        {!loadingContent && content && (
          <article
            dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
          />
        )}

        {!loadingContent && !content && !selected && (
          <p className="text-sm" style={{ color: "#4B5563" }}>
            Select a report from the sidebar.
          </p>
        )}
      </div>
    </div>
  );
}
