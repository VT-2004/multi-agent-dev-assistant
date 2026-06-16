import asyncio
from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.core.job_store import job_store
from app.core.pipeline_runner import run_pipeline
from app.websocket.manager import manager

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
            # Keep connection alive; client sends pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)