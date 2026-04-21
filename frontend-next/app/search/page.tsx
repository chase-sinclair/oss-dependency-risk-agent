"use client";

import { useState } from "react";
import Link from "next/link";
import { searchProjects } from "@/lib/api";
import type { SearchResult } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";
import LoadingSpinner from "@/components/LoadingSpinner";

const EXAMPLES = [
  "safe frameworks to build on long term",
  "projects with high bus factor risk",
  "which ML frameworks are well maintained",
  "projects with stalled PR pipelines",
];

type Filter = "All" | "REPLACE" | "UPGRADE" | "MONITOR";

function RecBadge({ rec }: { rec: string | null }) {
  if (!rec) return null;
  const colors: Record<string, string> = {
    REPLACE: "bg-red-100 text-red-700",
    UPGRADE: "bg-yellow-100 text-yellow-700",
    MONITOR: "bg-green-100 text-green-700",
  };
  return (
    <span
      className={`text-xs font-semibold px-2 py-0.5 rounded ${colors[rec] ?? "bg-gray-100 text-gray-600"}`}
    >
      {rec}
    </span>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("All");
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  async function doSearch(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      const hits = await searchProjects({
        query: q,
        filter: filter === "All" ? null : filter,
        top_k: topK,
      });
      setResults(hits);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-2">Semantic Search</h1>
      <p className="text-sm text-gray-500 mb-6">
        Ask natural-language questions about dependency health.
      </p>

      {/* Search bar */}
      <div className="flex gap-2 mb-4">
        <div className="flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch(query)}
            placeholder="e.g. which projects are showing declining maintenance?"
            className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
          />
        </div>
        <button
          onClick={() => doSearch(query)}
          disabled={loading}
          className="bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-blue-700"
        >
          Search
        </button>
      </div>

      {/* Example pills */}
      {!searched && (
        <div className="flex flex-wrap gap-2 mb-6">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQuery(ex);
                doSearch(ex);
              }}
              className="text-xs border border-gray-300 rounded-full px-3 py-1.5 text-gray-600 hover:bg-gray-50"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {/* Sidebar filters in-line */}
      <div className="flex items-center gap-4 mb-6 text-sm text-gray-600">
        <div className="flex items-center gap-2">
          <label>Recommendation:</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as Filter)}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          >
            {(["All", "REPLACE", "UPGRADE", "MONITOR"] as Filter[]).map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label>Max results:</label>
          <input
            type="range"
            min={1}
            max={20}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="w-24"
          />
          <span className="font-mono w-4">{topK}</span>
        </div>
      </div>

      {/* Results */}
      {loading && <LoadingSpinner message="Searching..." />}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {!loading && searched && results.length === 0 && !error && (
        <p className="text-gray-400 text-sm">No results found. Try a different query.</p>
      )}

      <div className="space-y-4">
        {results.map((r, i) => (
          <div
            key={`${r.repo_full_name}-${i}`}
            className="border border-gray-200 rounded-lg p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Link
                  href={`/projects/${r.repo_full_name}`}
                  className="font-semibold text-blue-600 hover:underline"
                >
                  {r.repo_full_name}
                </Link>
                <RecBadge rec={r.recommendation} />
                {r.health_score !== null && (
                  <HealthBadge score={r.health_score} size="sm" />
                )}
              </div>
              <span className="text-xs text-gray-400 font-mono">
                {(r.similarity_score * 100).toFixed(1)}% match
              </span>
            </div>
            {r.excerpt && (
              <p className="text-sm text-gray-600 leading-relaxed border-l-2 border-blue-200 pl-3">
                {r.excerpt}
              </p>
            )}
            <div className="flex items-center justify-between mt-3">
              {r.report_date && (
                <span className="text-xs text-gray-400">{r.report_date}</span>
              )}
              <Link
                href={`/projects/${r.repo_full_name}`}
                className="text-xs text-blue-600 hover:underline ml-auto"
              >
                View Detail →
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
