from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect, HTTPException, Request
from pydantic import BaseModel

from app.core.job_store import job_store
from app.core.pipeline_runner import run_pipeline
from app.core.config import settings
from app.websocket.manager import manager
from app.github_integration.webhook import verify_webhook_signature, parse_issue_event

import os

router = APIRouter()


class TriggerRequest(BaseModel):
    issue_number: int
    issue_title: str
    issue_body: str
    repo_owner: str
    repo_name: str


@router.post("/trigger", status_code=202)
async def trigger_pipeline(request: TriggerRequest, background_tasks: BackgroundTasks):
    """Trigger the multi-agent pipeline for a GitHub issue."""
    job_id = job_store.create_job(
        issue_number=request.issue_number,
        issue_title=request.issue_title,
        repo_owner=request.repo_owner,
        repo_name=request.repo_name,
    )

    background_tasks.add_task(
        run_pipeline,
        job_id=job_id,
        issue_number=request.issue_number,
        issue_title=request.issue_title,
        issue_body=request.issue_body,
        repo_owner=request.repo_owner,
        repo_name=request.repo_name,
    )

    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs")
async def list_jobs():
    """List all pipeline jobs."""
    return {"jobs": job_store.get_all_jobs()}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get status and logs for a specific job."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job log streaming."""
    await manager.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Receive GitHub webhook events and trigger pipeline automatically."""
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event_type = request.headers.get("X-GitHub-Event", "")

    # Handle GitHub's ping event immediately (sent when webhook is first created)
    if event_type == "ping":
        return {"message": "pong"}

    # Verify signature for all other events
    if not verify_webhook_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if event_type != "issues":
        return {"message": f"Ignored event type: {event_type}"}

    import json
    payload = json.loads(payload_bytes)
    issue_data = parse_issue_event(payload)

    if not issue_data:
        return {"message": "Ignored — not an opened/labeled issue"}

    repo_path = os.path.join(
        settings.REPO_CLONE_PATH,
        issue_data["repo_name"]
    )
    if not os.path.exists(repo_path):
        return {
            "message": f"Repo '{issue_data['repo_name']}' not indexed. Run ingest first."
        }

    job_id = job_store.create_job(
        issue_number=issue_data["issue_number"],
        issue_title=issue_data["issue_title"],
        repo_owner=issue_data["repo_owner"],
        repo_name=issue_data["repo_name"],
    )

    background_tasks.add_task(
        run_pipeline,
        job_id=job_id,
        issue_number=issue_data["issue_number"],
        issue_title=issue_data["issue_title"],
        issue_body=issue_data["issue_body"],
        repo_owner=issue_data["repo_owner"],
        repo_name=issue_data["repo_name"],
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "issue": issue_data["issue_number"]
    }