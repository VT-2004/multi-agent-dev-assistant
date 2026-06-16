import re
import difflib
from datetime import datetime

from langchain_groq import ChatGroq
from app.core.state import AgentState
from app.agents.code_agent import read_file_full

MODEL_NAME = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are a code reviewer for an autonomous AI coding agent. You will be given a GitHub issue and a proposed code change in unified diff format.

Review the change for CRITICAL issues only:
- Bugs or logic errors that would break functionality
- Security issues (hardcoded secrets, injection vulnerabilities, etc.)
- Whether the change actually addresses the issue at all
- Obvious syntax errors that would prevent the code from running

Do NOT fail for:
- Code style preferences (quote style, spacing, trailing commas)
- Minor formatting differences
- Things that are subjective improvements but not bugs

Respond using EXACTLY this format, with no other text:

REVIEW: pass
NOTES: <brief explanation>

or

REVIEW: fail
NOTES: <brief explanation of the critical problem(s) found>"""


def get_llm():
    return ChatGroq(model=MODEL_NAME, temperature=0.1, max_tokens=500)


def build_diff(repo_name: str, file_path: str, new_content: str) -> str:
    original = read_file_full(repo_name, file_path)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    return "".join(diff)


def parse_response(text: str):
    review_match = re.search(r"REVIEW:\s*(pass|fail)", text, re.IGNORECASE)
    notes_match = re.search(r"NOTES:\s*(.*)", text, re.DOTALL)

    review_passed = review_match.group(1).lower() == "pass" if review_match else False
    notes = notes_match.group(1).strip() if notes_match else "Could not parse review response."

    return review_passed, notes


def review_agent_node(state: AgentState) -> dict:
    if not state.get("proposed_changes"):
        log = {
            "agent": "review_agent",
            "message": "No proposed changes to review — Code Agent did not produce any edits.",
            "timestamp": datetime.utcnow().isoformat(),
        }
        return {
            "review_passed": False,
            "review_notes": "No changes were proposed by the Code Agent.",
            "status": "failed",
            "logs": [log],
        }

    diffs = [
        build_diff(state["repo_name"], change["file_path"], change["content"])
        for change in state["proposed_changes"]
    ]

    user_prompt = (
        f"ISSUE TITLE: {state['issue_title']}\n"
        f"ISSUE BODY: {state['issue_body']}\n\n"
        f"PROPOSED CHANGES (diff format):\n\n" + "\n".join(diffs)
    )

    llm = get_llm()
    response = llm.invoke([
        ("system", SYSTEM_PROMPT),
        ("user", user_prompt),
    ])

    review_passed, notes = parse_response(response.content)

    log = {
        "agent": "review_agent",
        "message": f"Review {'passed' if review_passed else 'failed'}: {notes}",
        "timestamp": datetime.utcnow().isoformat(),
    }

    return {
        "review_passed": review_passed,
        "review_notes": notes,
        "status": "in_progress" if review_passed else "needs_human",
        "logs": [log],
    }