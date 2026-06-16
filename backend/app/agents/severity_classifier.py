import re
from datetime import datetime

from langchain_groq import ChatGroq
from app.core.state import AgentState

MODEL_NAME = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are a triage assistant for an autonomous AI coding agent that resolves GitHub issues by making small, targeted code changes.

Given a GitHub issue, decide whether this issue is a good candidate for the autonomous agent to ATTEMPT, or whether it should be SKIPPED for a human developer to handle instead.

ATTEMPT issues typically:
- Have a clear, specific, well-scoped request (e.g. adding an item to a list, fixing a specific small bug, a small UI text/label change)
- Can likely be resolved with a small, localized change to one or two files
- Do not require new dependencies, architectural decisions, or design choices

SKIP issues typically:
- Are vague, broad, or open-ended (e.g. "improve performance", "refactor X", "redesign Y")
- Require large-scale changes across many files or a new feature with multiple components
- Involve security-sensitive areas (authentication, payments, secrets) without a precise specification
- Require new external dependencies, infrastructure changes, or technology migrations

Respond using EXACTLY this format, with no other text:

SEVERITY: attempt
REASON: <one or two sentences explaining your decision>

or

SEVERITY: skip
REASON: <one or two sentences explaining your decision>"""


def get_llm():
    return ChatGroq(model=MODEL_NAME, temperature=0.1, max_tokens=200)


def parse_response(text: str):
    severity_match = re.search(r"SEVERITY:\s*(attempt|skip)", text, re.IGNORECASE)
    reason_match = re.search(r"REASON:\s*(.*)", text, re.DOTALL)

    severity = severity_match.group(1).lower() if severity_match else "skip"
    reason = reason_match.group(1).strip() if reason_match else "Could not parse classifier response; defaulting to skip."

    return severity, reason


def severity_classifier_node(state: AgentState) -> dict:
    user_prompt = f"ISSUE TITLE: {state['issue_title']}\nISSUE BODY: {state['issue_body']}"

    llm = get_llm()
    response = llm.invoke([
        ("system", SYSTEM_PROMPT),
        ("user", user_prompt),
    ])

    severity, reason = parse_response(response.content)

    log = {
        "agent": "severity_classifier",
        "message": f"Classified as '{severity}': {reason}",
        "timestamp": datetime.utcnow().isoformat(),
    }

    return {
        "severity": severity,
        "severity_reason": reason,
        "status": "skipped" if severity == "skip" else "in_progress",
        "logs": [log],
    }