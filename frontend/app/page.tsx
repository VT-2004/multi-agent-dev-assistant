"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { fetchJobs, fetchJob, triggerPipeline, createWebSocket, Job, AgentLog } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  queued: "#64748b",
  in_progress: "#f59e0b",
  pr_opened: "#10b981",
  needs_human: "#ef4444",
  skipped: "#3b82f6",
  failed: "#ef4444",
};

const STATUS_LABELS: Record<string, string> = {
  queued: "Queued",
  in_progress: "Running",
  pr_opened: "PR Opened",
  needs_human: "Needs Human",
  skipped: "Skipped",
  failed: "Failed",
};

const AGENT_COLORS: Record<string, string> = {
  severity_classifier: "#a78bfa",
  context_agent: "#38bdf8",
  code_agent: "#34d399",
  review_agent: "#fb923c",
  orchestrator: "#94a3b8",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: "2px 8px",
        borderRadius: "9999px",
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        background: STATUS_COLORS[status] + "22",
        color: STATUS_COLORS[status],
        border: `1px solid ${STATUS_COLORS[status]}44`,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: STATUS_COLORS[status],
          boxShadow:
            status === "in_progress"
              ? `0 0 6px ${STATUS_COLORS[status]}`
              : "none",
        }}
      />
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function LogLine({ log }: { log: AgentLog }) {
  const color = AGENT_COLORS[log.agent] || "#94a3b8";
  const time = new Date(log.timestamp).toLocaleTimeString();
  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "3px 0",
        fontFamily: "var(--mono)",
        fontSize: 12,
      }}
    >
      <span style={{ color: "#475569", flexShrink: 0 }}>{time}</span>
      <span style={{ color, flexShrink: 0, fontWeight: 600 }}>
        [{log.agent}]
      </span>
      <span style={{ color: "#cbd5e1", wordBreak: "break-word" }}>
        {log.message}
      </span>
    </div>
  );
}

function TriggerForm({ onTriggered }: { onTriggered: (jobId: string) => void }) {
  const [form, setForm] = useState({
    issue_number: "",
    issue_title: "",
    issue_body: "",
    repo_owner: "VT-2004",
    repo_name: "social-dash",
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!form.issue_title || !form.issue_number) return;
    setLoading(true);
    try {
      const result = await triggerPipeline({
        ...form,
        issue_number: parseInt(form.issue_number),
      });
      onTriggered(result.job_id);
      setForm((f) => ({ ...f, issue_number: "", issue_title: "", issue_body: "" }));
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    width: "100%",
    background: "#0a0a0f",
    border: "1px solid #1e1e2e",
    borderRadius: 6,
    padding: "8px 10px",
    color: "#e2e8f0",
    fontSize: 13,
    outline: "none",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column" as const, gap: 10 }}>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          placeholder="Issue #"
          value={form.issue_number}
          onChange={(e) => setForm((f) => ({ ...f, issue_number: e.target.value }))}
          style={{ ...inputStyle, width: 80 }}
        />
        <input
          placeholder="Issue title"
          value={form.issue_title}
          onChange={(e) => setForm((f) => ({ ...f, issue_title: e.target.value }))}
          style={{ ...inputStyle, flex: 1 }}
        />
      </div>
      <textarea
        placeholder="Issue body (describe the change needed)"
        value={form.issue_body}
        onChange={(e) => setForm((f) => ({ ...f, issue_body: e.target.value }))}
        rows={3}
        style={{ ...inputStyle, resize: "vertical" as const, fontFamily: "inherit" }}
      />
      <div style={{ display: "flex", gap: 8 }}>
        <input
          placeholder="Repo owner"
          value={form.repo_owner}
          onChange={(e) => setForm((f) => ({ ...f, repo_owner: e.target.value }))}
          style={{ ...inputStyle, flex: 1 }}
        />
        <input
          placeholder="Repo name"
          value={form.repo_name}
          onChange={(e) => setForm((f) => ({ ...f, repo_name: e.target.value }))}
          style={{ ...inputStyle, flex: 1 }}
        />
      </div>
      <button
        onClick={handleSubmit}
        disabled={loading || !form.issue_title || !form.issue_number}
        style={{
          background: loading ? "#4c1d95" : "#7c3aed",
          color: "white",
          border: "none",
          borderRadius: 6,
          padding: "9px 16px",
          fontSize: 13,
          fontWeight: 600,
          cursor: loading ? "not-allowed" : "pointer",
          transition: "background 0.15s",
        }}
      >
        {loading ? "Triggering..." : "▶ Run Pipeline"}
      </button>
    </div>
  );
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [liveLogs, setLiveLogs] = useState<AgentLog[]>([]);
  const [wsStatus, setWsStatus] = useState<"disconnected" | "connected" | "done">("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadJobs = async () => {
      const j = await fetchJobs();
      setJobs(j);
    };
    loadJobs();
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveLogs]);

  const selectJob = useCallback(async (jobId: string) => {
    setSelectedJobId(jobId);
    setLiveLogs([]);

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const job = await fetchJob(jobId);
    setSelectedJob(job);
    setLiveLogs(job.logs || []);

    if (job.status === "queued" || job.status === "in_progress") {
      const ws = createWebSocket(jobId);
      wsRef.current = ws;
      setWsStatus("connected");

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "log") {
          setLiveLogs((prev) => {
            const exists = prev.some(
              (l) => l.timestamp === msg.log.timestamp && l.agent === msg.log.agent
            );
            return exists ? prev : [...prev, msg.log];
          });
        }
        if (msg.type === "status") {
          setSelectedJob((prev) => (prev ? { ...prev, status: msg.status } : prev));
          setJobs((prev) =>
            prev.map((j) => (j.job_id === jobId ? { ...j, status: msg.status } : j))
          );
        }
        if (msg.type === "complete") {
          setWsStatus("done");
          setSelectedJob((prev) =>
            prev ? { ...prev, status: msg.status, pr_url: msg.pr_url } : prev
          );
          setJobs((prev) =>
            prev.map((j) =>
              j.job_id === jobId ? { ...j, status: msg.status, pr_url: msg.pr_url } : j
            )
          );
          ws.close();
        }
      };

      ws.onerror = () => setWsStatus("disconnected");
      ws.onclose = () => setWsStatus("done");
    } else {
      setWsStatus("done");
    }
  }, []);

  const handleTriggered = async (jobId: string) => {
    const j = await fetchJobs();
    setJobs(j);
    selectJob(jobId);
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* LEFT SIDEBAR */}
      <div
        style={{
          width: 320,
          flexShrink: 0,
          borderRight: "1px solid #1e1e2e",
          display: "flex",
          flexDirection: "column" as const,
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "18px 16px 14px",
            borderBottom: "1px solid #1e1e2e",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 2,
            }}
          >
            <span style={{ fontSize: 18 }}>⚡</span>
            <span
              style={{
                fontWeight: 700,
                fontSize: 15,
                letterSpacing: "-0.02em",
              }}
            >
              Agent Dev Assistant
            </span>
          </div>
          <div style={{ color: "#475569", fontSize: 11 }}>
            Multi-agent GitHub automation
          </div>
        </div>

        {/* Trigger form */}
        <div
          style={{ padding: 14, borderBottom: "1px solid #1e1e2e" }}
        >
          <div
            style={{
              color: "#64748b",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase" as const,
              marginBottom: 10,
            }}
          >
            New Issue
          </div>
          <TriggerForm onTriggered={handleTriggered} />
        </div>

        {/* Job list */}
        <div style={{ flex: 1, overflowY: "auto" as const, padding: "8px 0" }}>
          <div
            style={{
              color: "#64748b",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase" as const,
              padding: "6px 16px 8px",
            }}
          >
            Pipeline Runs ({jobs.length})
          </div>
          {jobs.length === 0 && (
            <div
              style={{
                padding: "20px 16px",
                color: "#475569",
                fontSize: 12,
                textAlign: "center" as const,
              }}
            >
              No pipeline runs yet. Trigger one above.
            </div>
          )}
          {jobs.map((job) => (
            <div
              key={job.job_id}
              onClick={() => selectJob(job.job_id)}
              style={{
                padding: "10px 16px",
                cursor: "pointer",
                background:
                  selectedJobId === job.job_id ? "#12121a" : "transparent",
                borderLeft:
                  selectedJobId === job.job_id
                    ? "2px solid #7c3aed"
                    : "2px solid transparent",
                transition: "background 0.1s",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 8,
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#e2e8f0",
                    lineHeight: 1.4,
                    flex: 1,
                  }}
                >
                  #{job.issue_number} {job.issue_title}
                </div>
                <StatusBadge status={job.status} />
              </div>
              <div style={{ color: "#475569", fontSize: 11, marginTop: 4 }}>
                {job.repo_owner}/{job.repo_name} &middot;{" "}
                {new Date(job.created_at).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column" as const,
          overflow: "hidden",
        }}
      >
        {!selectedJob ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#334155",
            }}
          >
            <div style={{ textAlign: "center" as const }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🤖</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>
                Select a pipeline run to view details
              </div>
              <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>
                or trigger a new one from the left panel
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Job header */}
            <div
              style={{
                padding: "16px 20px",
                borderBottom: "1px solid #1e1e2e",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div
                  style={{ display: "flex", alignItems: "center", gap: 10 }}
                >
                  <span style={{ fontWeight: 600, fontSize: 15 }}>
                    #{selectedJob.issue_number} {selectedJob.issue_title}
                  </span>
                  <StatusBadge status={selectedJob.status} />
                </div>
                <div
                  style={{ color: "#475569", fontSize: 12, marginTop: 3 }}
                >
                  {selectedJob.repo_owner}/{selectedJob.repo_name}
                  {selectedJob.severity && ` · severity: ${selectedJob.severity}`}
                  {selectedJob.retry_count > 0 &&
                    ` · ${selectedJob.retry_count} retries`}
                  {wsStatus === "connected" && (
                    <span style={{ color: "#10b981", marginLeft: 8 }}>
                      ● live
                    </span>
                  )}
                </div>
              </div>
              {selectedJob.pr_url && (
                <a
                  href={selectedJob.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "7px 14px",
                    background: "#10b98122",
                    border: "1px solid #10b98144",
                    borderRadius: 6,
                    color: "#10b981",
                    fontSize: 12,
                    fontWeight: 600,
                    textDecoration: "none",
                    flexShrink: 0,
                  }}
                >
                  ↗ View PR
                </a>
              )}
            </div>

            {/* Agent pipeline visual */}
            <div
              style={{
                padding: "12px 20px",
                borderBottom: "1px solid #1e1e2e",
                display: "flex",
                alignItems: "center",
                gap: 6,
                flexWrap: "wrap" as const,
              }}
            >
              {[
                "severity_classifier",
                "context_agent",
                "code_agent",
                "review_agent",
                "orchestrator",
              ].map((agent, i, arr) => {
                const hasLog = liveLogs.some((l) => l.agent === agent);
                const color = AGENT_COLORS[agent];
                return (
                  <div
                    key={agent}
                    style={{ display: "flex", alignItems: "center", gap: 6 }}
                  >
                    <div
                      style={{
                        padding: "3px 10px",
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        background: hasLog ? color + "22" : "#1e1e2e",
                        color: hasLog ? color : "#475569",
                        border: `1px solid ${hasLog ? color + "44" : "#1e1e2e"}`,
                        transition: "all 0.3s",
                      }}
                    >
                      {agent.replace(/_/g, " ")}
                    </div>
                    {i < arr.length - 1 && (
                      <span style={{ color: "#334155", fontSize: 10 }}>→</span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Live log stream */}
            <div
              style={{
                flex: 1,
                overflowY: "auto" as const,
                padding: "14px 20px",
                background: "#080810",
              }}
            >
              <div
                style={{
                  color: "#334155",
                  fontSize: 11,
                  fontFamily: "var(--mono)",
                  marginBottom: 10,
                }}
              >
                ── agent reasoning log
                ──────────────────────────────
              </div>
              {liveLogs.length === 0 && (
                <div
                  style={{
                    color: "#334155",
                    fontSize: 12,
                    fontFamily: "var(--mono)",
                  }}
                >
                  Waiting for agent output...
                </div>
              )}
              {liveLogs.map((log, i) => (
                <LogLine key={i} log={log} />
              ))}
              {wsStatus === "connected" && (
                <div
                  style={{
                    color: "#334155",
                    fontSize: 12,
                    fontFamily: "var(--mono)",
                    marginTop: 4,
                  }}
                >
                  ▋
                </div>
              )}
              <div ref={logsEndRef} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
