import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")

    TARGET_REPO_OWNER: str = os.getenv("TARGET_REPO_OWNER", "")
    TARGET_REPO_NAME: str = os.getenv("TARGET_REPO_NAME", "")

    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
    REPO_CLONE_PATH: str = os.getenv("REPO_CLONE_PATH", "./data/repos")


settings = Settings()