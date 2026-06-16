from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import settings

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_embedding_function():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def get_vectorstore(collection_name: str):
    """Get (or create) a Chroma collection persisted at CHROMA_DB_PATH, using cosine similarity."""
    embeddings = get_embedding_function()
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=settings.CHROMA_DB_PATH,
        collection_metadata={"hnsw:space": "cosine"},
    )


def index_chunks(chunks, collection_name: str):
    """Embed and store a list of {file_path, content} chunks into Chroma."""
    vectorstore = get_vectorstore(collection_name)

    # Prepend the file path before embedding — gives the model extra semantic
    # signal (e.g. "Settings.tsx" hints at what the chunk relates to), which
    # plain code chunks often lack on their own.
    texts = [f"File: {c['file_path']}\n\n{c['content']}" for c in chunks]
    metadatas = [{"file_path": c["file_path"]} for c in chunks]

    vectorstore.add_texts(texts=texts, metadatas=metadatas)
    return vectorstore


if __name__ == "__main__":
    import sys
    from app.rag.chunker import chunk_repo

    if len(sys.argv) < 3:
        print("Usage: python -m app.rag.vectorstore <repo_path> <collection_name>")
        sys.exit(1)

    repo_path = sys.argv[1]
    collection_name = sys.argv[2]

    print("Chunking repo...")
    chunks = chunk_repo(repo_path)
    print(f"Got {len(chunks)} chunks. Embedding and storing (this may take a minute)...")

    index_chunks(chunks, collection_name)
    print(f"Done. Indexed into Chroma collection '{collection_name}' at {settings.CHROMA_DB_PATH}")