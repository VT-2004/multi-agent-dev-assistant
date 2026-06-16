import hmac
import hashlib

from app.core.config import settings


def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Verify that a webhook payload came from GitHub using the shared secret."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def parse_issue_event(payload: dict) -> dict | None:
    """
    Parse a GitHub issue webhook payload.
    Returns a dict with issue details if this is a new/labeled issue, else None.
    """
    action = payload.get("action")
    if action not in ("opened", "labeled"):
        return None

    issue = payload.get("issue", {})
    repo = payload.get("repository", {})

    return {
        "issue_number": issue.get("number"),
        "issue_title": issue.get("title", ""),
        "issue_body": issue.get("body", ""),
        "repo_owner": repo.get("owner", {}).get("login", ""),
        "repo_name": repo.get("name", ""),
    }