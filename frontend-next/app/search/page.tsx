"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { searchProjects } from "@/lib/api";
import type { SearchResult } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";

const BORDER  = "rgba(255,255,255,0.08)";
const SURFACE = "rgba(22,27,34,0.7)";

const PLACEHOLDERS = [
  "Which projects have high bus-factor risk?",
  "Find ML frameworks with declining maintenance...",
  "Projects at risk of abandonment?",
  "Which dependencies should be replaced urgently?",
  "Safe frameworks to build on long term?",
];

const EXAMPLES = [
  { label: "Bus factor risk",        query: "projects with high bus factor risk" },
  { label: "ML maintenance",         query: "which ML frameworks are well maintained" },
  { label: "Stalled PRs",            query: "projects with stalled PR pipelines" },
  { label: "Safe long-term builds",  query: "safe frameworks to build on long term" },
  { label: "Abandonment signals",    query: "projects showing signs of abandonment" },
  { label: "Critical replacements",  query: "which projects should be replaced immediately" },
];

type Filter = "All" | "REPLACE" | "UPGRADE" | "MONITOR";

const THOUGHT_STEPS = [
  "> Initializing vector search engine...",
  "> Embedding query with llama-text-embed-v2...",
  "> Querying Pinecone oss-health index...",
  "> Filtering by health thresholds...",
  "> Synthesizing results via Claude Sonnet...",
  "> Ranking by semantic relevance...",
];

function RecBadge({ rec }: { rec: string | null }) {
  if (!rec) return null;
  const style: React.CSSProperties =
    rec === "REPLACE" ? { color: "#FF4C4C", background: "rgba(255,76,76,0.1)",  border: "1px solid rgba(255,76,76,0.25)"  } :
    rec === "UPGRADE" ? { color: "#FBBF24", background: "rgba(251,191,36,0.1)", border: "1px solid rgba(251,191,36,0.25)" } :
                        { color: "#00E676", background: "rgba(0,230,118,0.1)",  border: "1px solid rgba(0,230,118,0.25)"  };
  return (
    <span className="text-xs font-semibold px-2 py-0.5 rounded font-mono" style={style}>
      {rec}
    </span>
  );
}

export default function SearchPage() {
  const [query, setQuery]         = useState("");
  const [filter, setFilter]       = useState<Filter>("All");
  const [topK, setTopK]           = useState(5);
  const [results, setResults]     = useState<SearchResult[]>([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [searched, setSearched]   = useState(false);
  const [focused, setFocused]     = useState(false);
  const [placeholder, setPlaceholder] = useState(PLACEHOLDERS[0]);
  const [thoughtLines, setThoughtLines] = useState<string[]>([]);
  const thoughtTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let i = 0;
    const t = setInterval(() => {
      i = (i + 1) % PLACEHOLDERS.length;
      setPlaceholder(PLACEHOLDERS[i]);
    }, 3500);
    return () => clearInterval(t);
  }, []);

  function stopThought() {
    if (thoughtTimer.current) { clearInterval(thoughtTimer.current); thoughtTimer.current = null; }
  }

  async function doSearch(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    setThoughtLines([]);
    let step = 0;
    thoughtTimer.current = setInterval(() => {
      if (step < THOUGHT_STEPS.length) {
        setThoughtLines(prev => [...prev, THOUGHT_STEPS[step]]);
        step++;
      } else { stopThought(); }
    }, 280);
    try {
      const hits = await searchProjects({ query: q, filter: filter === "All" ? null : filter, top_k: topK });
      setResults(hits);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      stopThought();
      setLoading(false);
    }
  }

  const isLanding = !searched && !loading;

  /* ── Shared: omni-bar ───────────────────────────────────────────────────────── */
  const OmniBar = () => (
    <div
      className="flex rounded-xl overflow-hidden transition-all w-full"
      style={{
        border: focused ? "1px solid rgba(139,92,246,0.6)" : "1px solid rgba(139,92,246,0.2)",
        boxShadow: focused ? "0 0 24px rgba(139,92,246,0.2)" : "none",
        background: SURFACE,
      }}
    >
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && doSearch(query)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        className="flex-1 bg-transparent px-5 py-3.5 text-sm"
        style={{ color: "#F0F6FC" }}
      />
      <button
        onClick={() => doSearch(query)}
        disabled={loading}
        className="px-6 py-3.5 text-sm font-semibold transition-colors disabled:opacity-50"
        style={{ background: "rgba(139,92,246,0.2)", color: "#8B5CF6", borderLeft: "1px solid rgba(139,92,246,0.2)" }}
      >
        {loading ? "..." : "Investigate"}
      </button>
    </div>
  );

  /* ── Shared: filter row ─────────────────────────────────────────────────────── */
  const FilterRow = ({ centered = false }: { centered?: boolean }) => (
    <div className={`flex items-center gap-4 flex-wrap ${centered ? "justify-center" : ""}`}>
      <div className="flex items-center gap-1">
        {(["All", "REPLACE", "UPGRADE", "MONITOR"] as Filter[]).map((f) => {
          const active = filter === f;
          const color = f === "REPLACE" ? "#FF4C4C" : f === "UPGRADE" ? "#FBBF24" : f === "MONITOR" ? "#00E676" : "#8B9BB4";
          return (
            <button key={f} onClick={() => setFilter(f)}
              className="px-3 py-1 rounded-full text-xs font-medium transition-colors"
              style={{ background: active ? `${color}18` : "transparent", color: active ? color : "#8B9BB4", border: `1px solid ${active ? color + "40" : BORDER}` }}
            >{f}</button>
          );
        })}
      </div>
      <div className="flex items-center gap-2 text-xs" style={{ color: "#8B9BB4" }}>
        <span>Top</span>
        <input type="range" min={1} max={20} value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          className="w-20 accent-violet-500"
        />
        <span className="font-mono w-4" style={{ color: "#8B5CF6" }}>{topK}</span>
      </div>
    </div>
  );

  /* ── Landing state: vertically centered hero ────────────────────────────────── */
  if (isLanding) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full px-8 text-center"
        style={{ color: "#F0F6FC" }}
      >
        {/* Icon */}
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6"
          style={{
            background: "rgba(139,92,246,0.12)",
            border: "1px solid rgba(139,92,246,0.3)",
            boxShadow: "0 0 40px rgba(139,92,246,0.12)",
          }}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
        </div>

        <h1 className="text-3xl font-bold mb-3">AI Investigator</h1>
        <p className="text-sm mb-10 max-w-md" style={{ color: "#8B9BB4" }}>
          Natural-language queries over all indexed OSS risk assessments,
          powered by Pinecone vector search and Claude Sonnet.
        </p>

        {/* Search bar */}
        <div className="w-full max-w-2xl mb-4">
          <OmniBar />
        </div>

        {/* Filters */}
        <div className="mb-8">
          <FilterRow centered />
        </div>

        {/* Example chips */}
        <div className="flex flex-wrap gap-2 justify-center max-w-2xl">
          {EXAMPLES.map(({ label, query: q }) => (
            <button
              key={label}
              onClick={() => { setQuery(q); doSearch(q); }}
              className="text-xs px-3 py-1.5 rounded-lg transition-colors"
              style={{ background: "rgba(139,92,246,0.07)", color: "#8B9BB4", border: "1px solid rgba(139,92,246,0.2)" }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = "#8B5CF6"; (e.currentTarget as HTMLElement).style.borderColor = "rgba(139,92,246,0.4)"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = "#8B9BB4"; (e.currentTarget as HTMLElement).style.borderColor = "rgba(139,92,246,0.2)"; }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  /* ── Post-search layout ─────────────────────────────────────────────────────── */
  return (
    <div className="p-8 max-w-4xl mx-auto" style={{ color: "#F0F6FC" }}>
      {/* Compact header */}
      <div className="flex items-center gap-3 mb-5">
        <h1 className="text-lg font-bold">AI Investigator</h1>
        {!loading && (
          <span
            className="text-xs px-2 py-0.5 rounded"
            style={{ background: "rgba(139,92,246,0.1)", color: "#8B5CF6", border: "1px solid rgba(139,92,246,0.2)" }}
          >
            {results.length} result{results.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Search bar */}
      <div className="mb-4"><OmniBar /></div>

      {/* Filters */}
      <div className="mb-6"><FilterRow /></div>

      {/* Thought process terminal */}
      {loading && thoughtLines.length > 0 && (
        <div className="rounded-xl mb-6 overflow-hidden" style={{ background: "#060A0F", border: "1px solid rgba(139,92,246,0.2)" }}>
          <div className="flex items-center gap-1.5 px-4 py-2" style={{ borderBottom: "1px solid rgba(139,92,246,0.1)", background: "#0B0E14" }}>
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#FF4C4C" }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#FBBF24" }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#00E676" }} />
            <span className="ml-3 text-xs font-mono" style={{ color: "#4B5563" }}>agent.reasoning</span>
          </div>
          <div className="px-4 py-3 space-y-1">
            {thoughtLines.map((line, i) => (
              <p key={i} className="text-xs font-mono animate-fade-up"
                style={{ color: i === thoughtLines.length - 1 ? "#8B5CF6" : "#4B5563" }}>
                {line}
              </p>
            ))}
            <p className="text-xs font-mono terminal-cursor" style={{ color: "#8B5CF6" }} />
          </div>
        </div>
      )}

      {error && <p className="text-sm mb-4" style={{ color: "#FF4C4C" }}>{error}</p>}

      {!loading && results.length === 0 && !error && (
        <p className="text-sm" style={{ color: "#4B5563" }}>
          No results found. Try a different query or check that the agent has been run.
        </p>
      )}

      {/* Insight cards */}
      <div className="space-y-4">
        {results.map((r, i) => {
          const confidence = (r.similarity_score * 100).toFixed(1);
          const isHighMatch = r.similarity_score > 0.8;
          return (
            <div
              key={`${r.repo_full_name}-${i}`}
              className="rounded-xl p-4 transition-all animate-fade-up"
              style={{ background: SURFACE, border: BORDER, animationDelay: `${i * 60}ms` }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "rgba(139,92,246,0.25)"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = BORDER; }}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 flex-wrap">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`https://github.com/${r.repo_full_name.split("/")[0]}.png?size=24`}
                    alt="" width={20} height={20} className="rounded-full"
                    style={{ border: "1px solid rgba(255,255,255,0.1)" }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                  <Link href={`/projects/${r.repo_full_name}`} className="font-semibold text-sm hover:underline" style={{ color: "#8B5CF6" }}>
                    {r.repo_full_name}
                  </Link>
                  <RecBadge rec={r.recommendation} />
                  {r.health_score !== null && <HealthBadge score={r.health_score} size="sm" />}
                </div>
                <span
                  className="text-xs font-mono px-2 py-0.5 rounded shrink-0"
                  style={{
                    color: isHighMatch ? "#00E676" : "#FBBF24",
                    background: isHighMatch ? "rgba(0,230,118,0.08)" : "rgba(251,191,36,0.08)",
                    border: `1px solid ${isHighMatch ? "rgba(0,230,118,0.2)" : "rgba(251,191,36,0.2)"}`,
                  }}
                >
                  {confidence}% match
                </span>
              </div>

              {r.excerpt && (
                <p className="text-xs leading-relaxed pl-3 mb-3"
                  style={{ color: "#8B9BB4", borderLeft: "2px solid rgba(139,92,246,0.4)" }}>
                  {r.excerpt}
                </p>
              )}

              <div className="flex items-center justify-between">
                {r.report_date && (
                  <span className="text-xs" style={{ color: "#4B5563" }}>{r.report_date}</span>
                )}
                <Link href={`/projects/${r.repo_full_name}`} className="text-xs ml-auto" style={{ color: "#8B5CF6" }}>
                  View Detail →
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
