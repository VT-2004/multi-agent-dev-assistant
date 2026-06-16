const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AgentLog {
  agent: string;
  message: string;
  timestamp: string;
}

export interface Job {
  job_id: string;
  issue_number: number;
  issue_title: string;
  repo_owner: string;
  repo_name: string;
  status: "queued" | "in_progress" | "pr_opened" | "needs_human" | "skipped" | "failed";
  pr_url: string | null;
  severity: string | null;
  review_passed: boolean | null;
  retry_count: number;
  logs: AgentLog[];
  created_at: string;
  updated_at: string;
}

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch(`${API_BASE}/api/jobs`, { cache: "no-store" });
  const data = await res.json();
  return data.jobs || [];
}

export async function fetchJob(jobId: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
  return res.json();
}

export async function triggerPipeline(payload: {
  issue_number: number;
  issue_title: string;
  issue_body: string;
  repo_owner: string;
  repo_name: string;
}): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/trigger`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export function createWebSocket(jobId: string): WebSocket {
  const wsBase = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
  return new WebSocket(`${wsBase}/api/ws/${jobId}`);
}