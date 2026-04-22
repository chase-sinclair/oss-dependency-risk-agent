"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { runAgent, getAgentStatus } from "@/lib/api";
import type { AgentStatus } from "@/types/api";

const BORDER  = "rgba(255,255,255,0.08)";
const SURFACE = "rgba(22,27,34,0.7)";

const PIPELINE_STEPS = [
  { name: "Monitor",     desc: "Query gold table for projects below health thresholds.",       icon: "◉" },
  { name: "Investigate", desc: "Fetch recent GitHub activity for each flagged project.",       icon: "◎" },
  { name: "Synthesize",  desc: "Claude analyzes signals and writes a risk assessment.",        icon: "◈" },
  { name: "Recommend",   desc: "Assign REPLACE / UPGRADE / MONITOR action per project.",      icon: "◆" },
  { name: "Deliver",     desc: "Compile assessments into a dated markdown report on disk.",   icon: "◻" },
];

const LOG_TEMPLATES = [
  (limit: number) => `[INFO]  Initializing LangGraph workflow (limit=${limit})...`,
  () => `[INFO]  Connecting to Databricks SQL warehouse...`,
  () => `[INFO]  ✓ Warehouse connection established`,
  (limit: number) => `[AGENT] Monitor node: querying gold_health_scores (limit=${limit})...`,
  (n: number) => `[AGENT] ${n} projects flagged for investigation`,
  () => `[AGENT] Investigate node: fetching GitHub activity signals...`,
  () => `[INFO]  Fetching commit frequency, issue resolution, PR metrics...`,
  () => `[AGENT] Synthesize node: Claude Sonnet analyzing signals...`,
  () => `[INFO]  Running risk assessment for batch 1...`,
  () => `[AGENT] Recommend node: assigning action labels...`,
  () => `[AGENT] Deliver node: compiling intelligence report...`,
  () => `[SUCCESS] Report written to docs/reports/`,
];

export default function AgentPage() {
  const [dryRun,   setDryRun]   = useState(false);
  const [limit,    setLimit]    = useState<number | "">(10);
  const [minScore, setMinScore] = useState(0);
  const [maxScore, setMaxScore] = useState(10);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [running, setRunning]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(-1);
  const [logs, setLogs]         = useState<Array<{ level: string; text: string }>>([]);
  const pollRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const logTimer  = useRef<ReturnType<typeof setInterval> | null>(null);
  const logStepRef = useRef(0);
  const terminalRef = useRef<HTMLDivElement>(null);

  function stopAll() {
    if (pollRef.current)  { clearInterval(pollRef.current);  pollRef.current  = null; }
    if (logTimer.current) { clearInterval(logTimer.current); logTimer.current = null; }
  }

  useEffect(() => () => stopAll(), []);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  function startLogStream(projectLimit: number) {
    logStepRef.current = 0;
    const templates = LOG_TEMPLATES;
    logTimer.current = setInterval(() => {
      const i = logStepRef.current;
      if (i >= templates.length) { clearInterval(logTimer.current!); return; }
      const fn = templates[i] as (arg?: number) => string;
      const text = i === 0 ? fn(projectLimit) : i === 4 ? fn(projectLimit) : fn();
      const level = text.startsWith("[AGENT]") ? "agent" : text.startsWith("[SUCCESS]") ? "success" : "info";
      setLogs(prev => [...prev, { level, text }]);
      // Update active pipeline step based on log position
      if (i === 3) setActiveStep(0);
      else if (i === 5) setActiveStep(1);
      else if (i === 7) setActiveStep(2);
      else if (i === 9) setActiveStep(3);
      else if (i === 10) setActiveStep(4);
      logStepRef.current++;
    }, 800);
  }

  async function handleRun() {
    setRunning(true);
    setError(null);
    setAgentStatus(null);
    setActiveStep(0);
    setLogs([]);
    stopAll();
    startLogStream(limit === "" ? 10 : Number(limit));

    try {
      const res = await runAgent({
        dry_run: dryRun,
        limit:     limit === "" ? null : Number(limit),
        min_score: minScore,
        max_score: maxScore,
      });

      pollRef.current = setInterval(async () => {
        try {
          const status = await getAgentStatus(res.run_id);
          setAgentStatus(status);
          if (status.status !== "running") {
            stopAll();
            setRunning(false);
            setActiveStep(-1);
            if (status.status === "complete") {
              setLogs(prev => [...prev, { level: "success", text: "[SUCCESS] Mission complete. Report generated." }]);
            } else {
              setLogs(prev => [...prev, { level: "error", text: "[ERROR]  Agent run failed. Check backend logs." }]);
            }
          }
        } catch {
          stopAll();
          setRunning(false);
          setError("Lost connection to agent.");
        }
      }, 2000);
    } catch (e: unknown) {
      stopAll();
      setError(e instanceof Error ? e.message : "Failed to start agent");
      setRunning(false);
      setActiveStep(-1);
    }
  }

  function handleStop() {
    stopAll();
    setRunning(false);
    setActiveStep(-1);
    setLogs(prev => [...prev, { level: "error", text: "[WARN]  Agent aborted by operator." }]);
  }

  const isDone   = agentStatus?.status === "complete";
  const isFailed = agentStatus?.status === "failed";

  function logColor(level: string): string {
    if (level === "agent")   return "#8B5CF6";
    if (level === "success") return "#00E676";
    if (level === "error")   return "#FF4C4C";
    return "#4B5563";
  }

  return (
    <div className="p-8 max-w-5xl" style={{ color: "#F0F6FC" }}>
      <h1 className="text-2xl font-bold mb-1">Agent Control Room</h1>
      <p className="text-sm mb-8" style={{ color: "#8B9BB4" }}>
        Mission launchpad for the 5-node LangGraph risk assessment workflow.
      </p>

      <div className="grid grid-cols-3 gap-6">
        {/* ── Instrument panel ───────────────────────────────────────────────── */}
        <div
          className="col-span-1 rounded-xl p-5 flex flex-col gap-4"
          style={{ background: SURFACE, border: BORDER }}
        >
          <h2 className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#8B9BB4" }}>
            Mission Parameters
          </h2>

          {/* Dry run toggle */}
          <div className="flex items-center justify-between">
            <span className="text-sm">Dry Run</span>
            <button
              onClick={() => setDryRun(!dryRun)}
              className="relative w-11 h-6 rounded-full transition-colors"
              style={{
                background: dryRun ? "rgba(139,92,246,0.5)" : "rgba(255,255,255,0.1)",
                border: dryRun ? "1px solid rgba(139,92,246,0.6)" : BORDER,
              }}
            >
              <span
                className="absolute top-0.5 w-5 h-5 rounded-full transition-transform"
                style={{
                  left: "2px",
                  background: dryRun ? "#8B5CF6" : "#4B5563",
                  transform: dryRun ? "translateX(20px)" : "translateX(0)",
                  boxShadow: dryRun ? "0 0 8px rgba(139,92,246,0.6)" : "none",
                }}
              />
            </button>
          </div>

          {/* Project limit */}
          <div>
            <label className="text-xs mb-1 block" style={{ color: "#8B9BB4" }}>Project Limit</label>
            <input
              type="number" min={1} max={200} value={limit}
              onChange={(e) => setLimit(e.target.value === "" ? "" : Number(e.target.value))}
              className="w-full bg-transparent rounded-lg px-3 py-2 text-sm font-mono text-center"
              style={{ border: BORDER, color: "#8B5CF6" }}
            />
          </div>

          {/* Min score */}
          <div>
            <div className="flex justify-between text-xs mb-1" style={{ color: "#8B9BB4" }}>
              <span>Min Score</span>
              <span className="font-mono" style={{ color: "#8B5CF6" }}>{minScore.toFixed(1)}</span>
            </div>
            <input type="range" min={0} max={10} step={0.5} value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-full accent-violet-500" />
          </div>

          {/* Max score */}
          <div>
            <div className="flex justify-between text-xs mb-1" style={{ color: "#8B9BB4" }}>
              <span>Max Score</span>
              <span className="font-mono" style={{ color: "#8B5CF6" }}>{maxScore.toFixed(1)}</span>
            </div>
            <input type="range" min={0} max={10} step={0.5} value={maxScore}
              onChange={(e) => setMaxScore(Number(e.target.value))}
              className="w-full accent-violet-500" />
          </div>
        </div>

        {/* ── Right panel ────────────────────────────────────────────────────── */}
        <div className="col-span-2 flex flex-col gap-5">
          {/* Ignition button */}
          <div className="relative">
            <button
              onClick={running ? handleStop : handleRun}
              className="w-full py-4 rounded-xl text-base font-bold transition-all"
              style={running ? {
                background: "rgba(255,76,76,0.1)",
                border: "1px solid rgba(255,76,76,0.4)",
                color: "#FF4C4C",
                boxShadow: "0 0 20px rgba(255,76,76,0.1)",
              } : {
                background: "linear-gradient(135deg, rgba(139,92,246,0.3) 0%, rgba(139,92,246,0.15) 100%)",
                border: "1px solid rgba(139,92,246,0.5)",
                color: "#8B5CF6",
                boxShadow: "0 0 24px rgba(139,92,246,0.15)",
              }}
            >
              {running ? (
                <span className="flex items-center justify-center gap-3">
                  <span
                    className="w-5 h-5 rounded-full animate-spin-ring"
                    style={{ border: "2px solid rgba(255,76,76,0.3)", borderTopColor: "#FF4C4C" }}
                  />
                  Stop Agent
                </span>
              ) : (
                "⚡ Launch Investigation"
              )}
            </button>
          </div>

          {error && (
            <div
              className="text-sm px-4 py-3 rounded-lg"
              style={{
                color: "#FF4C4C",
                background: "rgba(255,76,76,0.07)",
                border: "1px solid rgba(255,76,76,0.2)",
              }}
            >
              {error}
            </div>
          )}

          {/* Completion summary */}
          {isDone && agentStatus.summary && (
            <div
              className="rounded-xl p-4 animate-fade-up"
              style={{
                background: "rgba(0,230,118,0.05)",
                border: "1px solid rgba(0,230,118,0.2)",
              }}
            >
              <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "#00E676" }}>
                Mission Complete
              </p>
              <div className="grid grid-cols-4 gap-3 text-center">
                {[
                  { label: "Assessed", val: agentStatus.summary.assessed, color: "#F0F6FC" },
                  { label: "REPLACE",  val: agentStatus.summary.replace_count, color: "#FF4C4C" },
                  { label: "UPGRADE",  val: agentStatus.summary.upgrade_count, color: "#FBBF24" },
                  { label: "MONITOR",  val: agentStatus.summary.monitor_count, color: "#00E676" },
                ].map(({ label, val, color }) => (
                  <div key={label}>
                    <p className="text-2xl font-bold font-mono" style={{ color }}>{val}</p>
                    <p className="text-xs mt-0.5" style={{ color: "#8B9BB4" }}>{label}</p>
                  </div>
                ))}
              </div>
              {agentStatus.report_filename && (
                <div className="mt-3 pt-3" style={{ borderTop: "1px solid rgba(0,230,118,0.15)" }}>
                  <Link href="/reports" className="text-xs" style={{ color: "#00E676" }}>
                    View intelligence report →
                  </Link>
                </div>
              )}
            </div>
          )}

          {isFailed && (
            <div
              className="px-4 py-3 rounded-lg text-sm"
              style={{
                color: "#FF4C4C",
                background: "rgba(255,76,76,0.07)",
                border: "1px solid rgba(255,76,76,0.2)",
              }}
            >
              Agent run failed. Review terminal output below.
            </div>
          )}

          {/* Orchestration graph */}
          <div className="rounded-xl p-5" style={{ background: SURFACE, border: BORDER }}>
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "#8B9BB4" }}>
              LangGraph Pipeline
            </h2>
            <div className="flex items-start gap-2">
              {PIPELINE_STEPS.map((step, i) => {
                const isActive    = running && activeStep === i;
                const isComplete  = isDone || (running && activeStep > i);
                const nodeColor   = isComplete ? "#00E676" : isActive ? "#8B5CF6" : "#374151";
                const labelColor  = isComplete ? "#00E676" : isActive ? "#8B5CF6" : "#4B5563";

                return (
                  <div key={step.name} className="flex items-start flex-1 min-w-0">
                    {/* Node */}
                    <div className="flex flex-col items-center flex-1 min-w-0">
                      <div
                        className="w-10 h-10 rounded-full flex items-center justify-center text-base shrink-0 transition-all"
                        style={{
                          background: isActive  ? "rgba(139,92,246,0.15)" :
                                      isComplete ? "rgba(0,230,118,0.1)"   :
                                      "rgba(255,255,255,0.04)",
                          border: `1px solid ${nodeColor}`,
                          boxShadow: isActive ? "0 0 16px rgba(139,92,246,0.4)" :
                                     isComplete ? "0 0 10px rgba(0,230,118,0.2)" : "none",
                          color: nodeColor,
                        }}
                      >
                        {isComplete ? "✓" : step.icon}
                      </div>
                      <p className="text-xs font-medium mt-2 text-center" style={{ color: labelColor }}>
                        {step.name}
                      </p>
                      <p className="text-xs mt-1 text-center leading-tight hidden xl:block" style={{ color: "#374151", fontSize: "9px" }}>
                        {step.desc.slice(0, 40)}…
                      </p>
                    </div>

                    {/* Connector */}
                    {i < PIPELINE_STEPS.length - 1 && (
                      <div
                        className={`mt-5 flex-shrink-0 w-4 h-0.5 ${running && activeStep === i ? "energy-bar" : ""}`}
                        style={{
                          background: isComplete ? "#00E676" : "rgba(255,255,255,0.08)",
                          opacity: isComplete ? 0.5 : 1,
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Live intelligence stream */}
          {logs.length > 0 && (
            <div className="rounded-xl overflow-hidden" style={{ background: "#060A0F", border: "1px solid rgba(139,92,246,0.15)" }}>
              <div
                className="flex items-center gap-1.5 px-4 py-2"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0B0E14" }}
              >
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#FF4C4C" }} />
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#FBBF24" }} />
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#00E676" }} />
                <span className="ml-3 text-xs font-mono" style={{ color: "#4B5563" }}>
                  sentinel.agent.log
                </span>
                {running && (
                  <span
                    className="ml-auto w-1.5 h-1.5 rounded-full animate-agent-pulse"
                    style={{ background: "#8B5CF6" }}
                  />
                )}
              </div>
              <div
                ref={terminalRef}
                className="px-4 py-3 space-y-1 max-h-48 overflow-y-auto scrollbar-dark"
              >
                {logs.map((log, i) => (
                  <p key={i} className="text-xs font-mono leading-relaxed" style={{ color: logColor(log.level) }}>
                    {log.text}
                  </p>
                ))}
                {running && <p className="text-xs font-mono terminal-cursor" style={{ color: "#8B5CF6" }} />}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
