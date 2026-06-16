from typing import TypedDict, List, Optional, Literal, Annotated
import operator


class FileContext(TypedDict):
    """A chunk of retrieved codebase context, from the RAG pipeline."""
    file_path: str
    content: str
    relevance_score: float


class FileChange(TypedDict):
    """A proposed file change (used for code diffs and generated tests)."""
    file_path: str
    content: str


class AgentLog(TypedDict):
    """A single log entry, streamed to the frontend in real time."""
    agent: str
    message: str
    timestamp: str


class AgentState(TypedDict):
    # --- Issue details (input) ---
    issue_number: int
    issue_title: str
    issue_body: str
    repo_owner: str
    repo_name: str

    # --- Severity Classifier output ---
    severity: Literal["attempt", "skip"]
    severity_reason: str

    # --- Context Agent output (RAG) ---
    retrieved_context: List[FileContext]

    # --- Code Agent output ---
    proposed_changes: List[FileChange]

    # --- Review Agent output ---
    review_passed: bool
    review_notes: str
    retry_count: int

    # --- Test Agent output ---
    test_files: List[FileChange]

    # --- Final pipeline status ---
    status: Literal["queued", "in_progress", "pr_opened", "needs_human", "skipped", "failed"]
    pr_url: Optional[str]

    # --- Streaming logs ---
    logs: Annotated[List[AgentLog], operator.add]