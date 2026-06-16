from app.rag.vectorstore import get_vectorstore


def retrieve_context(query: str, collection_name: str, k: int = 5):
    """
    Given a query (e.g. an issue title/body), return the top-k most relevant
    code chunks from the indexed repo, formatted to match the FileContext schema.
    """
    vectorstore = get_vectorstore(collection_name)

    # With cosine space, distance ranges 0 (identical) to 2 (opposite).
    results = vectorstore.similarity_search_with_score(query, k=k)

    context = []
    for doc, distance in results:
        similarity = 1 - distance  # roughly -1 (opposite) to 1 (identical)
        context.append({
            "file_path": doc.metadata.get("file_path", "unknown"),
            "content": doc.page_content,
            "relevance_score": round(similarity, 4),
        })

    return context


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m app.rag.retriever <collection_name> <query>")
        sys.exit(1)

    collection_name = sys.argv[1]
    query = " ".join(sys.argv[2:])

    results = retrieve_context(query, collection_name, k=5)

    print(f"Query: {query}\n")
    for i, r in enumerate(results, 1):
        print(f"--- Result {i} (score: {r['relevance_score']:.4f}) ---")
        print(f"File: {r['file_path']}")
        print(r['content'][:300])
        print()