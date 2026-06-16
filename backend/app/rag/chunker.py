import os
from langchain.text_splitter import RecursiveCharacterTextSplitter, Language

# Map file extensions to LangChain's Language enum for language-aware splitting
# (this makes the splitter prefer breaking at function/class boundaries)
EXTENSION_LANGUAGE_MAP = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
}

# Directories to skip entirely
IGNORE_DIRS = {
    ".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build",
    ".vscode", ".idea", "coverage", "data",
}

# Specific files to skip — lock files and generated configs have no semantic value for RAG
IGNORE_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "components.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
}

# File extensions worth chunking
INCLUDE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".css"}

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def get_files(repo_path: str):
    """Walk the repo and return a list of file paths worth chunking."""
    files = []
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for filename in filenames:
            if filename in IGNORE_FILES:
                continue
            ext = os.path.splitext(filename)[1]
            if ext in INCLUDE_EXTENSIONS:
                files.append(os.path.join(root, filename))
    return files


def chunk_file(file_path: str, repo_path: str):
    """Read a file and split it into chunks, using language-aware splitting if available."""
    ext = os.path.splitext(file_path)[1]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, IOError):
        return []

    if not content.strip():
        return []

    if ext in EXTENSION_LANGUAGE_MAP:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=EXTENSION_LANGUAGE_MAP[ext],
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

    chunks = splitter.split_text(content)
    rel_path = os.path.relpath(file_path, repo_path)

    return [{"file_path": rel_path, "content": chunk} for chunk in chunks]


def chunk_repo(repo_path: str):
    """Chunk an entire repo, returning a flat list of {file_path, content} dicts."""
    all_chunks = []
    for file_path in get_files(repo_path):
        all_chunks.extend(chunk_file(file_path, repo_path))
    return all_chunks


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.rag.chunker <repo_path>")
        sys.exit(1)

    repo_path = sys.argv[1]
    chunks = chunk_repo(repo_path)

    print(f"Total chunks: {len(chunks)}")
    print(f"Files processed: {len(set(c['file_path'] for c in chunks))}")
    print("\nSample chunks:")
    for c in chunks[:3]:
        print(f"\n--- {c['file_path']} ---")
        print(c["content"][:300])
        print("...")