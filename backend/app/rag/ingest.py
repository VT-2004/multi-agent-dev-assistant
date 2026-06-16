import os
import shutil
from git import Repo
from app.core.config import settings


def clone_repo(repo_url: str, repo_name: str) -> str:
    """
    Clones a GitHub repo into REPO_CLONE_PATH/<repo_name>.
    If it already exists locally, removes it first for a fresh clone.
    Returns the local filesystem path to the cloned repo.
    """
    dest_path = os.path.join(settings.REPO_CLONE_PATH, repo_name)

    if os.path.exists(dest_path):
        print(f"Removing existing copy at {dest_path} ...")
        shutil.rmtree(dest_path)

    print(f"Cloning {repo_url} into {dest_path} ...")
    Repo.clone_from(repo_url, dest_path)
    print("Clone complete.")

    return dest_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m app.rag.ingest <repo_url> <repo_name>")
        sys.exit(1)

    repo_url = sys.argv[1]
    repo_name = sys.argv[2]
    path = clone_repo(repo_url, repo_name)
    print(f"Repo cloned to: {path}")