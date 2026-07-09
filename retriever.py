"""
Phase 2: Retrieval
Builds a retriever that finds the most relevant chunks for a user query.
Supports metadata filtering by section.
"""

from typing import List, Dict, Any, Optional
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
import config


def get_embeddings():
    """Get the embedding model."""
    return OpenAIEmbeddings(
        model=config.EMBEDDING_MODEL,
        openai_api_key=config.OPENROUTER_API_KEY,
        openai_api_base=config.OPENROUTER_BASE_URL,
    )


def get_vector_store(embeddings=None) -> Chroma:
    """Load the vector store from disk."""
    if embeddings is None:
        embeddings = get_embeddings()
    return Chroma(
        embedding_function=embeddings,
        persist_directory=config.PERSIST_DIRECTORY,
    )


def normalize_score(score: float) -> float:
    """
    Normalize a distance score to a [0, 1] relevance score.
    ChromaDB returns L2 distances which can be negative.
    We invert and clamp so higher = more relevant.
    """
    # L2 distance: lower is more similar
    # Convert to a similarity score in [0, 1]
    # Use sigmoid-like normalization: 1 / (1 + abs(score))
    normalized = 1.0 / (1.0 + abs(score))
    return round(normalized, 4)


def retrieve_chunks(
    query: str,
    top_k: int = config.TOP_K,
    section_filter: Optional[str] = None,
    return_scores: bool = False,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most relevant chunks for a query.

    Args:
        query: The user's question
        top_k: Number of chunks to retrieve
        section_filter: Optional section name to filter by (e.g., "3. ADMISSIONS")
        return_scores: Whether to include similarity scores

    Returns:
        List of dictionaries with 'content', 'metadata', and 'score'
    """
    embeddings = get_embeddings()
    vector_store = get_vector_store(embeddings)

    # Build filter if section specified
    filter_dict = None
    if section_filter and section_filter != "All Sections":
        filter_dict = {"section": {"$eq": section_filter}}

    # Retrieve with optional metadata filtering
    # Use similarity_search_with_score (returns L2 distances, not relevance scores)
    # This avoids the UserWarning from relevance score normalization
    if filter_dict:
        results = vector_store.similarity_search_with_score(
            query,
            k=top_k,
            filter=filter_dict,
        )
    else:
        results = vector_store.similarity_search_with_score(
            query,
            k=top_k,
        )

    # Format results with normalized scores
    chunks = []
    for doc, l2_distance in results:
        chunk = {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": normalize_score(l2_distance),
        }
        chunks.append(chunk)

    return chunks


def test_retrieval():
    """Test retrieval with sample queries."""
    print("=" * 60)
    print("Testing Retrieval Pipeline")
    print("=" * 60)

    test_queries = [
        "What is the fee for CSE branch?",
        "Tell me about placements and top recruiters",
        "What are the admission requirements?",
        "What sports facilities are available?",
    ]

    for query in test_queries:
        print(f"\n{'─' * 60}")
        print(f"Query: {query}")
        print(f"{'─' * 60}")

        chunks = retrieve_chunks(query, top_k=3)

        for i, chunk in enumerate(chunks):
            print(f"\n  Chunk {i+1} (score: {chunk['score']:.4f}):")
            print(f"  Section: {chunk['metadata'].get('section', 'N/A')}")
            print(f"  Content: {chunk['content'][:200]}...")

        print()


if __name__ == "__main__":
    test_retrieval()