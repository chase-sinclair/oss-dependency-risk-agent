"use client";

import { useEffect, useState } from "react";
import { getReports, getReport } from "@/lib/api";
import type { ReportMeta } from "@/types/api";
import LoadingSpinner from "@/components/LoadingSpinner";

function renderMarkdown(text: string): string {
  function escHtml(s: string): string {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function inline(s: string): string {
    return escHtml(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1 rounded text-xs">$1</code>');
  }

  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let inCode = false;

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) {
        out.push("</code></pre>");
        inCode = false;
      } else {
        out.push('<pre class="bg-gray-100 rounded p-3 text-xs overflow-x-auto my-2"><code>');
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      out.push(escHtml(line));
      continue;
    }
    if (line.startsWith("# ")) {
      out.push(`<h1 class="text-2xl font-bold mt-6 mb-3">${inline(line.slice(2))}</h1>`);
    } else if (line.startsWith("## ")) {
      out.push(
        `<h2 class="text-xl font-semibold mt-5 mb-2 border-b pb-1">${inline(line.slice(3))}</h2>`
      );
    } else if (line.startsWith("### ")) {
      out.push(
        `<h3 class="text-base font-semibold mt-4 mb-1 text-blue-700">${inline(line.slice(4))}</h3>`
      );
    } else if (line.startsWith("#### ")) {
      out.push(`<h4 class="font-medium mt-3 mb-1">${inline(line.slice(5))}</h4>`);
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      out.push(`<li class="ml-5 list-disc text-sm">${inline(line.slice(2))}</li>`);
    } else if (line.trim() === "---") {
      out.push('<hr class="border-gray-200 my-4"/>');
    } else if (line.trim() === "") {
      out.push("<br/>");
    } else {
      out.push(`<p class="text-sm leading-relaxed mb-1">${inline(line)}</p>`);
    }
  }

  return out.join("\n");
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportMeta[]>([]);
  const [selected, setSelected] = useState<ReportMeta | null>(null);
  const [content, setContent] = useState<string>("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingContent, setLoadingContent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReports()
      .then((rs) => {
        setReports(rs);
        if (rs.length > 0) selectReport(rs[0]);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load reports")
      )
      .finally(() => setLoadingList(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectReport(r: ReportMeta) {
    setSelected(r);
    setLoadingContent(true);
    setContent("");
    getReport(r.filename)
      .then(setContent)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load report")
      )
      .finally(() => setLoadingContent(false));
  }

  if (loadingList)
    return (
      <div className="p-8">
        <LoadingSpinner message="Loading reports..." />
      </div>
    );
  if (error)
    return <div className="p-8 text-red-600 text-sm">Error: {error}</div>;

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-200 p-4 overflow-y-auto shrink-0">
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
          Reports
        </h2>
        {reports.length === 0 && (
          <p className="text-xs text-gray-400">No reports found.</p>
        )}
        <div className="space-y-1">
          {reports.map((r) => (
            <button
              key={r.filename}
              onClick={() => selectReport(r)}
              className={`w-full text-left px-3 py-2 rounded text-xs ${
                selected?.filename === r.filename
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              <div className="font-mono">{r.timestamp}</div>
              <div className="text-gray-400 mt-0.5">
                {r.project_count} projects · {r.file_size_kb} KB
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 p-6 overflow-y-auto">
        {selected && (
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-lg font-semibold">{selected.timestamp}</h1>
            <div className="flex gap-2">
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/reports/${encodeURIComponent(selected.filename)}`}
                download={selected.filename}
                className="text-sm text-blue-600 border border-blue-200 rounded px-3 py-1.5 hover:bg-blue-50"
              >
                Download
              </a>
            </div>
          </div>
        )}

        {loadingContent && <LoadingSpinner message="Loading report..." />}

        {!loadingContent && content && (
          <article
            className="prose max-w-none"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
          />
        )}

        {!loadingContent && !content && !selected && (
          <p className="text-gray-400 text-sm">Select a report from the sidebar.</p>
        )}
      </div>
    </div>
  );
}
