"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { runAgent, getAgentStatus } from "@/lib/api";
import type { AgentStatus } from "@/types/api";
import LoadingSpinner from "@/components/LoadingSpinner";

const PIPELINE_STEPS = [
  {
    name: "Monitor",
    desc: "Query Databricks gold table for projects below health thresholds.",
  },
  {
    name: "Investigate",
    desc: "Fetch recent GitHub activity signals for each flagged project.",
  },
  {
    name: "Synthesize",
    desc: "Claude analyzes signals and writes a risk assessment per project.",
  },
  {
    name: "Recommend",
    desc: "Assign REPLACE / UPGRADE / MONITOR action for each project.",
  },
  {
    name: "Deliver",
    desc: "Compile all assessments into a dated markdown report on disk.",
  },
];

export default function AgentPage() {
  const [dryRun, setDryRun] = useState(false);
  const [limit, setLimit] = useState<number | "">(10);
  const [minScore, setMinScore] = useState(0);
  const [maxScore, setMaxScore] = useState(10);
  const [runId, setRunId] = useState<string | null>(null);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => {
    return stopPolling;
  }, []);

  async function handleRun() {
    setRunning(true);
    setError(null);
    setAgentStatus(null);
    setRunId(null);
    stopPolling();

    try {
      const res = await runAgent({
        dry_run: dryRun,
        limit: limit === "" ? null : Number(limit),
        min_score: minScore > 0 ? minScore : null,
        max_score: maxScore < 10 ? maxScore : null,
      });

      setRunId(res.run_id);

      pollRef.current = setInterval(async () => {
        try {
          const status = await getAgentStatus(res.run_id);
          setAgentStatus(status);
          if (status.status !== "running") {
            stopPolling();
            setRunning(false);
          }
        } catch {
          stopPolling();
          setRunning(false);
          setError("Lost connection to agent. Check the terminal for output.");
        }
      }, 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start agent");
      setRunning(false);
    }
  }

  const isDone = agentStatus?.status === "complete";
  const isFailed = agentStatus?.status === "failed";

  return (
    <div className="p-8 max-w-4xl">
      <h1 className="text-2xl font-bold mb-1">Agent Control Room</h1>
      <p className="text-sm text-gray-500 mb-8">
        Run the LangGraph risk assessment agent against your monitored projects.
      </p>

      <div className="grid grid-cols-3 gap-8">
        {/* Options panel */}
        <div className="col-span-1 border border-gray-200 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">
            Options
          </h2>

          <label className="flex items-center gap-2 mb-4 cursor-pointer">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-gray-700">Dry run</span>
          </label>

          <div className="mb-4">
            <label className="text-xs text-gray-500 block mb-1">
              Project limit
            </label>
            <input
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(e) =>
                setLimit(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="border border-gray-300 rounded px-3 py-1.5 text-sm w-full"
            />
          </div>

          <div className="mb-4">
            <label className="text-xs text-gray-500 block mb-1">
              Min score: {minScore.toFixed(1)}
            </label>
            <input
              type="range"
              min={0}
              max={10}
              step={0.5}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-full"
            />
          </div>

          <div>
            <label className="text-xs text-gray-500 block mb-1">
              Max score: {maxScore.toFixed(1)}
            </label>
            <input
              type="range"
              min={0}
              max={10}
              step={0.5}
              value={maxScore}
              onChange={(e) => setMaxScore(Number(e.target.value))}
              className="w-full"
            />
          </div>
        </div>

        {/* Center panel */}
        <div className="col-span-2">
          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={running}
            className="w-full py-4 bg-blue-600 text-white text-base font-semibold rounded-lg disabled:opacity-50 hover:bg-blue-700 mb-6"
          >
            {running ? "Running..." : "Run Agent"}
          </button>

          {error && (
            <div className="mb-4 text-sm text-red-600 border border-red-200 rounded p-3">
              {error}
            </div>
          )}

          {running && (
            <div className="flex items-center gap-3 mb-6">
              <LoadingSpinner />
              <span className="text-sm text-gray-600">Agent running...</span>
            </div>
          )}

          {isDone && agentStatus.summary && (
            <div className="mb-6 border border-green-200 rounded-lg p-4 bg-green-50">
              <p className="text-sm font-semibold text-green-800 mb-2">
                Run complete
              </p>
              <div className="grid grid-cols-4 gap-3 text-center text-sm">
                <div>
                  <p className="text-2xl font-bold">{agentStatus.summary.assessed}</p>
                  <p className="text-xs text-gray-500">Assessed</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-600">
                    {agentStatus.summary.replace_count}
                  </p>
                  <p className="text-xs text-gray-500">REPLACE</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-yellow-600">
                    {agentStatus.summary.upgrade_count}
                  </p>
                  <p className="text-xs text-gray-500">UPGRADE</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-green-600">
                    {agentStatus.summary.monitor_count}
                  </p>
                  <p className="text-xs text-gray-500">MONITOR</p>
                </div>
              </div>
              {agentStatus.report_filename && (
                <div className="mt-3 pt-3 border-t border-green-200">
                  <Link
                    href="/reports"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    View report →
                  </Link>
                </div>
              )}
            </div>
          )}

          {isFailed && (
            <div className="mb-6 border border-red-200 rounded-lg p-4 bg-red-50">
              <p className="text-sm text-red-700">
                Agent run failed. Check the terminal for error output.
              </p>
            </div>
          )}

          {/* Pipeline steps */}
          <div>
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Pipeline
            </h2>
            <div className="space-y-3">
              {PIPELINE_STEPS.map((step, i) => (
                <div key={step.name} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs flex items-center justify-center shrink-0 font-mono">
                    {i + 1}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-800">{step.name}</p>
                    <p className="text-xs text-gray-500">{step.desc}</p>
                  </div>
                  {i < PIPELINE_STEPS.length - 1 && (
                    <div className="text-gray-300 text-sm self-center ml-auto">→</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
