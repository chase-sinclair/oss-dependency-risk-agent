"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { onboardManifest } from "@/lib/api";
import type { AddedProject, OnboardResponse, ReadyProject, UnresolvedPackage } from "@/types/api";
import HealthBadge from "@/components/HealthBadge";

const BORDER  = "rgba(255,255,255,0.08)";
const SURFACE = "rgba(22,27,34,0.7)";

const ACCEPTED = ["requirements.txt", "package.json", "go.mod", "Cargo.toml", "pom.xml"];

const ECOSYSTEM_META: Record<string, { label: string; color: string; bg: string }> = {
  python: { label: "Python", color: "#60A5FA", bg: "rgba(96,165,250,0.1)"  },
  node:   { label: "Node",   color: "#22C55E", bg: "rgba(34,197,94,0.1)"   },
  go:     { label: "Go",     color: "#06B6D4", bg: "rgba(6,182,212,0.1)"   },
  rust:   { label: "Rust",   color: "#F97316", bg: "rgba(249,115,22,0.1)"  },
  java:   { label: "Java",   color: "#FBBF24", bg: "rgba(251,191,36,0.1)"  },
};

function EcoBadge({ eco }: { eco: string }) {
  const m = ECOSYSTEM_META[eco] ?? { label: eco, color: "#8B9BB4", bg: "rgba(139,155,180,0.1)" };
  return (
    <span
      className="text-xs font-semibold px-2 py-0.5 rounded font-mono"
      style={{ color: m.color, background: m.bg, border: `1px solid ${m.color}30` }}
    >
      {m.label}
    </span>
  );
}

/* ── Section header ─────────────────────────────────────────────────────────── */

function SectionHeader({
  label, count, color, borderColor, bg,
}: {
  label: string; count: number; color: string; borderColor: string; bg: string;
}) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 rounded-t-xl"
      style={{ background: bg, borderBottom: `1px solid ${borderColor}` }}
    >
      <span
        className="text-xs font-bold uppercase tracking-widest"
        style={{ color }}
      >
        {label}
      </span>
      <span
        className="text-xs font-mono px-2 py-0.5 rounded-full"
        style={{ color, background: `${color}20`, border: `1px solid ${color}40` }}
      >
        {count}
      </span>
    </div>
  );
}

/* ── READY card ─────────────────────────────────────────────────────────────── */

function ReadyCard({ p }: { p: ReadyProject }) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 transition-all"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`https://github.com/${p.org}.png?size=32`}
        alt={p.org} width={24} height={24}
        className="rounded-full shrink-0"
        style={{ border: "1px solid rgba(255,255,255,0.1)" }}
        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate" style={{ color: "#F0F6FC" }}>
            {p.org}/{p.repo}
          </span>
          <EcoBadge eco={p.ecosystem} />
        </div>
        <p className="text-xs mt-0.5" style={{ color: "#8B9BB4" }}>
          from <span className="font-mono">{p.package_name}</span>
          <span className="mx-2" style={{ color: "#374151" }}>·</span>
          <span style={{ color: "#00E676" }}>Health data available — view now</span>
        </p>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {p.health_score !== null ? (
          <HealthBadge score={p.health_score} size="sm" />
        ) : (
          <span className="text-xs font-mono" style={{ color: "#4B5563" }}>
            awaiting pipeline
          </span>
        )}
        <Link
          href={`/projects/${p.org}/${p.repo}?from=onboard`}
          className="text-xs px-3 py-1 rounded transition-colors"
          style={{ color: "#00E676", border: "1px solid rgba(0,230,118,0.25)", background: "rgba(0,230,118,0.06)" }}
        >
          View →
        </Link>
      </div>
    </div>
  );
}

/* ── ADDED card ─────────────────────────────────────────────────────────────── */

function AddedCard({ p }: { p: AddedProject }) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 transition-all"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`https://github.com/${p.org}.png?size=32`}
        alt={p.org} width={24} height={24}
        className="rounded-full shrink-0"
        style={{ border: "1px solid rgba(255,255,255,0.1)" }}
        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate" style={{ color: "#F0F6FC" }}>
            {p.org}/{p.repo}
          </span>
          <EcoBadge eco={p.ecosystem} />
          {p.confidence === "low" && (
            <span
              className="text-xs px-1.5 py-0.5 rounded font-mono"
              style={{ color: "#FBBF24", background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.2)" }}
            >
              low confidence
            </span>
          )}
        </div>
        <p className="text-xs mt-0.5" style={{ color: "#8B9BB4" }}>
          from <span className="font-mono">{p.package_name}</span>
          <span className="mx-2" style={{ color: "#374151" }}>·</span>
          <span style={{ color: "#FBBF24" }}>Added to pipeline — scores available after next run</span>
        </p>
      </div>
      <Link
        href="/agent"
        className="text-xs px-3 py-1 rounded transition-colors shrink-0"
        style={{ color: "#FBBF24", border: "1px solid rgba(251,191,36,0.25)", background: "rgba(251,191,36,0.06)" }}
      >
        Run Pipeline →
      </Link>
    </div>
  );
}

/* ── UNRESOLVED card ────────────────────────────────────────────────────────── */

function UnresolvedCard({ p }: { p: UnresolvedPackage }) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-3"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
    >
      <div
        className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-xs"
        style={{ background: "rgba(255,76,76,0.1)", color: "#FF4C4C", border: "1px solid rgba(255,76,76,0.2)" }}
      >
        ?
      </div>
      <div className="flex-1 min-w-0">
        <span className="text-sm font-mono truncate" style={{ color: "#F0F6FC" }}>
          {p.name}
        </span>
        <p className="text-xs mt-0.5" style={{ color: "#FF4C4C" }}>
          Could not resolve to a GitHub repository
          <span className="ml-1.5 font-mono text-xs" style={{ color: "#4B5563" }}>
            — {p.reason}
          </span>
        </p>
      </div>
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────────────────────────── */

const SESSION_KEY = "onboard_result";

export default function OnboardPage() {
  const [file, setFile]         = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState<OnboardResponse | null>(null);
  const [error, setError]       = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Restore results from sessionStorage on mount (back-navigation)
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (saved) setResult(JSON.parse(saved));
    } catch { /* ignore */ }
  }, []);

  const acceptFile = useCallback((f: File) => {
    setFile(f);
    setResult(null);
    setError(null);
    sessionStorage.removeItem(SESSION_KEY);
  }, []);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) acceptFile(f);
  }

  async function submit() {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await onboardManifest(file);
      setResult(res);
      try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(res)); } catch { /* ignore */ }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Discovery failed");
    } finally {
      setLoading(false);
    }
  }

  const hasResults = result && (
    result.ready_projects.length > 0 ||
    result.added_projects.length > 0 ||
    result.unresolved_packages.length > 0
  );

  return (
    <div className="p-8 max-w-3xl" style={{ color: "#F0F6FC" }}>
      {/* Header */}
      <h1 className="text-2xl font-bold mb-1">Onboard Your Dependencies</h1>
      <p className="text-sm mb-8" style={{ color: "#8B9BB4" }}>
        Upload your project&apos;s dependency manifest to add your specific packages to the monitoring pipeline.
      </p>

      {/* Drop zone */}
      <div
        className="rounded-xl mb-4 transition-all cursor-pointer"
        style={{
          border: dragging
            ? "2px dashed rgba(139,92,246,0.7)"
            : file
              ? "2px solid rgba(139,92,246,0.4)"
              : "2px dashed rgba(255,255,255,0.12)",
          background: dragging
            ? "rgba(139,92,246,0.06)"
            : file
              ? "rgba(139,92,246,0.04)"
              : SURFACE,
          boxShadow: dragging ? "0 0 30px rgba(139,92,246,0.1)" : "none",
        }}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !file && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) acceptFile(f); }}
        />

        {file ? (
          <div className="flex items-center justify-between px-6 py-5">
            <div className="flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                style={{ background: "rgba(139,92,246,0.15)", border: "1px solid rgba(139,92,246,0.3)" }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium" style={{ color: "#F0F6FC" }}>{file.name}</p>
                <p className="text-xs mt-0.5" style={{ color: "#8B9BB4" }}>
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
            <button
              onClick={e => { e.stopPropagation(); setFile(null); setResult(null); sessionStorage.removeItem(SESSION_KEY); }}
              className="text-xs px-3 py-1 rounded transition-colors"
              style={{ color: "#8B9BB4", border: "1px solid rgba(255,255,255,0.08)" }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = "#FF4C4C"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = "#8B9BB4"; }}
            >
              Remove
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 px-8 text-center">
            <div
              className="w-14 h-14 rounded-xl flex items-center justify-center mb-4"
              style={{ background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.2)" }}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="16 16 12 12 8 16"/>
                <line x1="12" y1="12" x2="12" y2="21"/>
                <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
              </svg>
            </div>
            <p className="text-sm font-medium mb-1" style={{ color: "#F0F6FC" }}>
              Drop your manifest here, or click to browse
            </p>
            <p className="text-xs mb-4" style={{ color: "#8B9BB4" }}>Accepted formats</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {ACCEPTED.map(name => (
                <span
                  key={name}
                  className="text-xs px-2.5 py-1 rounded font-mono"
                  style={{ background: "rgba(139,92,246,0.08)", color: "#8B9BB4", border: "1px solid rgba(139,92,246,0.15)" }}
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Explanatory note */}
      <div
        className="rounded-lg px-4 py-3 mb-6 text-xs leading-relaxed"
        style={{ background: "rgba(139,92,246,0.05)", border: "1px solid rgba(139,92,246,0.12)", color: "#8B9BB4" }}
      >
        Packages already in our monitored list of 200+ projects will show health scores immediately.
        Newly discovered packages will be added to the monitoring pipeline and scored within 24 hours
        after the next pipeline run.
      </div>

      {/* Submit button */}
      {file && !result && (
        <button
          onClick={submit}
          disabled={loading}
          className="w-full py-3 rounded-xl text-sm font-semibold transition-all mb-6 disabled:opacity-50"
          style={{
            background: loading
              ? "rgba(139,92,246,0.2)"
              : "linear-gradient(135deg, rgba(139,92,246,0.3) 0%, rgba(139,92,246,0.15) 100%)",
            border: "1px solid rgba(139,92,246,0.4)",
            color: "#8B5CF6",
            boxShadow: loading ? "none" : "0 0 20px rgba(139,92,246,0.15)",
          }}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span
                className="inline-block w-4 h-4 rounded-full border-2 border-transparent"
                style={{ borderTopColor: "#8B5CF6", animation: "spin 0.7s linear infinite" }}
              />
              Discovering dependencies...
            </span>
          ) : (
            "⊕  Discover Dependencies"
          )}
        </button>
      )}

      {error && (
        <div
          className="rounded-xl px-4 py-3 mb-6 text-sm"
          style={{ background: "rgba(255,76,76,0.08)", border: "1px solid rgba(255,76,76,0.25)", color: "#FF4C4C" }}
        >
          {error}
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────────────── */}
      {result && (
        <div className="space-y-4">
          {/* Summary line */}
          <p className="text-xs mb-2" style={{ color: "#8B9BB4" }}>
            Parsed <span style={{ color: "#F0F6FC" }}>{result.parsed_count}</span> dependencies ·{" "}
            <span style={{ color: "#00E676" }}>{result.ready_projects.length} ready</span> ·{" "}
            <span style={{ color: "#FBBF24" }}>{result.added_projects.length} added</span> ·{" "}
            <span style={{ color: "#FF4C4C" }}>{result.unresolved_packages.length} unresolved</span>
          </p>

          {/* READY */}
          {result.ready_projects.length > 0 && (
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(0,230,118,0.2)" }}>
              <SectionHeader
                label="Ready"
                count={result.ready_projects.length}
                color="#00E676"
                borderColor="rgba(0,230,118,0.2)"
                bg="rgba(0,230,118,0.05)"
              />
              <div style={{ background: SURFACE }}>
                {result.ready_projects.map(p => (
                  <ReadyCard key={`${p.org}/${p.repo}`} p={p} />
                ))}
              </div>
            </div>
          )}

          {/* ADDED */}
          {result.added_projects.length > 0 && (
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(251,191,36,0.2)" }}>
              <SectionHeader
                label="Added"
                count={result.added_projects.length}
                color="#FBBF24"
                borderColor="rgba(251,191,36,0.2)"
                bg="rgba(251,191,36,0.05)"
              />
              <div style={{ background: SURFACE }}>
                {result.added_projects.map(p => (
                  <AddedCard key={`${p.org}/${p.repo}`} p={p} />
                ))}
              </div>
            </div>
          )}

          {/* UNRESOLVED */}
          {result.unresolved_packages.length > 0 && (
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,76,76,0.2)" }}>
              <SectionHeader
                label="Unresolved"
                count={result.unresolved_packages.length}
                color="#FF4C4C"
                borderColor="rgba(255,76,76,0.2)"
                bg="rgba(255,76,76,0.05)"
              />
              <div style={{ background: SURFACE }}>
                {result.unresolved_packages.map(p => (
                  <UnresolvedCard key={p.name} p={p} />
                ))}
              </div>
            </div>
          )}

          {!hasResults && (
            <div
              className="rounded-xl p-5 text-sm text-center"
              style={{ background: SURFACE, border: BORDER, color: "#4B5563" }}
            >
              No dependencies found in this file.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
