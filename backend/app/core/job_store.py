from typing import Dict, Any
import uuid
from datetime import datetime


class JobStore:
    """
    In-memory store for pipeline job state.
    In production this would be Redis, but in-memory is fine for MVP.
    """

    def __init__(self):
        self.jobs: Dict[str, dict] = {}

    def create_job(self, issue_number: int, issue_title: str, repo_owner: str, repo_name: str) -> str:
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "job_id": job_id,
            "issue_number": issue_number,
            "issue_title": issue_title,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "status": "queued",
            "pr_url": None,
            "severity": None,
            "review_passed": None,
            "retry_count": 0,
            "logs": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def get_all_jobs(self) -> list:
        return sorted(self.jobs.values(), key=lambda j: j["created_at"], reverse=True)

    def update_job(self, job_id: str, **kwargs):
        if job_id in self.jobs:
            self.jobs[job_id].update(kwargs)
            self.jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

    def append_log(self, job_id: str, log: dict):
        if job_id in self.jobs:
            self.jobs[job_id]["logs"].append(log)
            self.jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()


# Single shared instance
job_store = JobStore()