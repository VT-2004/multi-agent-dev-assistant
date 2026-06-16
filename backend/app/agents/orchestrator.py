import os
from datetime import datetime

from langgraph.graph import StateGraph, END
from app.core.state import AgentState
from app.core.config import settings
from app.rag.retriever import retrieve_context
from app.agents.severity_classifier import severity_classifier_node
from app.agents.code_agent import code_agent_node
from app.agents.review_agent import review_agent_node

MAX_RETRIES = 2


def context_agent_node(state: AgentState) -> dict:
    query = f"{state['issue_title']}\n{state['issue_body']}"
    results = retrieve_context(query, state["repo_name"], k=5)
    log = {
        "agent": "context_agent",
        "message": f"Retrieved {len(results)} relevant code chunks.",
        "timestamp": datetime.utcnow().isoformat(),
    }
    return {"retrieved_context": results, "logs": [log]}


def increment_retry_node(state: AgentState) -> dict:
    """Increments retry count and logs it. Runs only when we are actually retrying."""
    new_count = state.get("retry_count", 0) + 1
    log = {
        "agent": "orchestrator",
        "message": f"Review failed. Starting retry {new_count} of {MAX_RETRIES}. Feedback: {state.get('review_notes', '')}",
        "timestamp": datetime.utcnow().isoformat(),
    }
    return {"retry_count": new_count, "logs": [log]}


def mark_needs_human_node(state: AgentState) -> dict:
    log = {
        "agent": "orchestrator",
        "message": f"Max retries ({MAX_RETRIES}) reached without passing review. Marking as needs_human.",
        "timestamp": datetime.utcnow().isoformat(),
    }
    return {"status": "needs_human", "logs": [log]}


def mark_complete_node(state: AgentState) -> dict:
    """Terminal node when review passes — creates the GitHub PR."""
    from app.github_integration.pr_manager import create_pr_from_state

    try:
        pr_url = create_pr_from_state(state)
        log = {
            "agent": "orchestrator",
            "message": f"Review passed. PR created: {pr_url}",
            "timestamp": datetime.utcnow().isoformat(),
        }
        return {
            "status": "pr_opened",
            "pr_url": pr_url,
            "logs": [log],
        }
    except Exception as e:
        log = {
            "agent": "orchestrator",
            "message": f"Review passed but PR creation failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
        }
        return {
            "status": "needs_human",
            "logs": [log],
        }


def route_after_severity(state: AgentState) -> str:
    return "attempt" if state["severity"] == "attempt" else "skip"


def route_after_review(state: AgentState) -> str:
    if state["review_passed"]:
        return "pass"
    if state.get("retry_count", 0) < MAX_RETRIES:
        return "retry"
    return "exhausted"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("severity_classifier", severity_classifier_node)
    graph.add_node("context_agent", context_agent_node)
    graph.add_node("code_agent", code_agent_node)
    graph.add_node("review_agent", review_agent_node)
    graph.add_node("increment_retry", increment_retry_node)
    graph.add_node("mark_needs_human", mark_needs_human_node)
    graph.add_node("mark_complete", mark_complete_node)

    graph.set_entry_point("severity_classifier")

    graph.add_conditional_edges(
        "severity_classifier",
        route_after_severity,
        {"attempt": "context_agent", "skip": END},
    )

    graph.add_edge("context_agent", "code_agent")
    graph.add_edge("code_agent", "review_agent")

    graph.add_conditional_edges(
        "review_agent",
        route_after_review,
        {
            "pass": "mark_complete",
            "retry": "increment_retry",
            "exhausted": "mark_needs_human",
        },
    )

    graph.add_edge("increment_retry", "code_agent")
    graph.add_edge("mark_complete", END)
    graph.add_edge("mark_needs_human", END)

    return graph.compile()


def make_initial_state(issue_number, issue_title, issue_body, repo_owner, repo_name) -> AgentState:
    return {
        "issue_number": issue_number,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "severity": "attempt",
        "severity_reason": "",
        "retrieved_context": [],
        "proposed_changes": [],
        "review_passed": False,
        "review_notes": "",
        "retry_count": 0,
        "test_files": [],
        "status": "queued",
        "pr_url": None,
        "logs": [],
    }


if __name__ == "__main__":
    app = build_graph()

    TEST_ISSUES = [
        {
            "issue_number": 2,
            "issue_title": "Add Pinterest as a supported platform",
            "issue_body": 'Add Pinterest to the platforms array in Growth.tsx. The exact current line is: const platforms = ["All Platforms", "Instagram", "Twitter", "Facebook", "LinkedIn"]; Add Pinterest keeping the same format and double quotes.',
        },
        {
            "issue_number": 3,
            "issue_title": "Migrate the entire app from React to Vue and add a GraphQL backend",
            "issue_body": "Rewrite the frontend in Vue 3 and replace the data layer with GraphQL.",
        },
    ]

    for issue in TEST_ISSUES:
        print("\n" + "=" * 60)
        print(f"ISSUE #{issue['issue_number']}: {issue['issue_title']}")
        print("=" * 60)

        final_state = app.invoke(make_initial_state(
            issue_number=issue["issue_number"],
            issue_title=issue["issue_title"],
            issue_body=issue["issue_body"],
            repo_owner="VT-2004",
            repo_name="social-dash",
        ))

        print(f"\nSeverity:      {final_state['severity']}")
        print(f"Status:        {final_state['status']}")
        print(f"Retry count:   {final_state['retry_count']}")
        print(f"Review passed: {final_state['review_passed']}")
        print(f"Review notes:  {final_state['review_notes']}")

        print(f"\nProposed changes ({len(final_state['proposed_changes'])} file(s)):")
        for c in final_state["proposed_changes"]:
            print(f"  - {c['file_path']}")

        print("\n--- LOGS ---")
        for log in final_state["logs"]:
            print(f"[{log['agent']}] {log['message']}")

        if final_state["proposed_changes"] and final_state["review_passed"]:
            print("\n--- WRITING CHANGES TO DISK ---")
            for change in final_state["proposed_changes"]:
                full_path = os.path.join(
                    settings.REPO_CLONE_PATH,
                    final_state["repo_name"],
                    change["file_path"],
                )
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(change["content"])
                print(f"Wrote: {change['file_path']}")