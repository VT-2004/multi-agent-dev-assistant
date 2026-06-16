from github import Github, GithubException
from app.core.config import settings


def get_github_client() -> Github:
    return Github(settings.GITHUB_TOKEN)


def get_repo(owner: str = None, name: str = None):
    g = get_github_client()
    owner = owner or settings.TARGET_REPO_OWNER
    name = name or settings.TARGET_REPO_NAME
    return g.get_repo(f"{owner}/{name}")


def get_issue(issue_number: int, owner: str = None, name: str = None):
    repo = get_repo(owner, name)
    return repo.get_issue(issue_number)