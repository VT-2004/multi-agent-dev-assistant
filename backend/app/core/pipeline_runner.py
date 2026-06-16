import asyncio
from datetime import datetime

from app.agents.orchestrator import build_graph, make_initial_state
from app.core.job_store import job_store
from app.websocket.manager import manager


async def stream_log(job_id: str, agent: str, message: str):
    """Push a log entry to the job store and all connected WebSocket clients."""
    log = {
        "agent": agent,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    job_store.append_log(job_id, log)
    await manager.broadcast(job_id, {
        "type": "log",
        "job_id": job_id,
        "log": log,
    })


async def run_pipeline(
    job_id: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    repo_owner: str,
    repo_name: str,
):
    """Run the full multi-agent pipeline as a background task, streaming logs."""

    job_store.update_job(job_id, status="in_progress")
    await manager.broadcast(job_id, {
        "type": "status",
        "job_id": job_id,
        "status": "in_progress",
    })

    await stream_log(job_id, "orchestrator", "Pipeline started.")

    try:
        # LangGraph is synchronous — run it in a thread pool so it doesn't
        # block the FastAPI event loop
        loop = asyncio.get_event_loop()
        graph = build_graph()

        initial_state = make_initial_state(
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
            repo_owner=repo_owner,
            repo_name=repo_name,
        )

        final_state = await loop.run_in_executor(
            None,
            lambda: graph.invoke(initial_state)
        )

        # Push all agent logs from the final state to WebSocket clients
        for log in final_state.get("logs", []):
            job_store.append_log(job_id, log)
            await manager.broadcast(job_id, {
                "type": "log",
                "job_id": job_id,
                "log": log,
            })
            await asyncio.sleep(0.05)  # small delay so frontend renders each log visibly

        # Update final job status
        final_status = final_state.get("status", "failed")
        job_store.update_job(
            job_id,
            status=final_status,
            pr_url=final_state.get("pr_url"),
            severity=final_state.get("severity"),
            review_passed=final_state.get("review_passed"),
            retry_count=final_state.get("retry_count", 0),
        )

        await manager.broadcast(job_id, {
            "type": "complete",
            "job_id": job_id,
            "status": final_status,
            "pr_url": final_state.get("pr_url"),
        })

    except Exception as e:
        error_msg = f"Pipeline error: {str(e)}"
        await stream_log(job_id, "orchestrator", error_msg)
        job_store.update_job(job_id, status="failed")
        await manager.broadcast(job_id, {
            "type": "complete",
            "job_id": job_id,
            "status": "failed",
            "pr_url": None,
        })