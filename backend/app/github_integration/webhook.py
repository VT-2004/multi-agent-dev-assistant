import hmac
import hashlib
from app.core.config import settings


def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Verify GitHub webhook signature. If no secret configured, allow all."""
    if not settings.GITHUB_WEBHOOK_SECRET:
        return True  # no secret configured — allow everything

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def parse_issue_event(payload: dict) -> dict | None:
    action = payload.get("action")
    if action not in ("opened", "labeled"):
        return None

    issue = payload.get("issue", {})
    repo = payload.get("repository", {})

    return {
        "issue_number": issue.get("number"),
        "issue_title": issue.get("title", ""),
        "issue_body": issue.get("body", "") or "",
        "repo_owner": repo.get("owner", {}).get("login", ""),
        "repo_name": repo.get("name", ""),
    }