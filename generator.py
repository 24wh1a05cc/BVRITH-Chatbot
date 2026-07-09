"""
generator.py  (updated for Day 5 Function Calling)
----------------------------------------------------
Unchanged public API — app.py still calls generate_answer_with_sources().
Internally, the raw llm.invoke() is replaced with Router.route() which
handles CONVERSATION / RAG / TOOL_CALL paths transparently.

The RAG pipeline (retrieval, chunking, embeddings, ChromaDB, citations)
is 100% preserved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI

import config
from routing import Router, RouteResult


def get_llm(model: str = None, temperature: float = 0.1, max_tokens: int = 1024) -> ChatOpenAI:
    """
    Return a plain ChatOpenAI instance (no tools bound).
    Kept here for backward compatibility with evaluation.py.

    max_tokens defaults to 1024 to stay within free-tier OpenRouter credits.
    """
    return ChatOpenAI(
        model=model or config.LLM_MODEL,
        openai_api_key=config.OPENROUTER_API_KEY,
        openai_api_base=config.OPENROUTER_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
    )

# Singleton router — reused across calls to avoid re-creating LLM clients
_router = Router()


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers (still used by evaluation.py and tests)
# ─────────────────────────────────────────────────────────────────────────────

def format_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a context string for the prompt."""
    context_parts = []
    for i, chunk in enumerate(chunks):
        section = chunk["metadata"].get("section", "General")
        content = chunk["content"]
        context_parts.append(f"[Source {i+1}] Section: {section}\n{content}\n")
    return "\n".join(context_parts)


def format_history(messages: List[Dict[str, str]]) -> str:
    """Format conversation history for the prompt."""
    if not messages:
        return "No previous conversation."
    history_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_parts.append(f"{role.upper()}: {content}")
    return "\n".join(history_parts[-6:])


# ─────────────────────────────────────────────────────────────────────────────
# Core generation function — now backed by the routing engine
# ─────────────────────────────────────────────────────────────────────────────

def generate_answer(
    question: str,
    chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    model: str = None,      # kept for API compatibility; router uses config.LLM_MODEL
    memory_context: str = "",
) -> str:
    """
    Generate a grounded answer using the routing engine.

    The router decides:
      CONVERSATION → plain LLM (no RAG needed)
      RAG          → LLM grounded on retrieved chunks
      TOOL_CALL    → executor + LLM final answer

    Returns the answer string (citations included for RAG/TOOL paths).
    """
    result: RouteResult = _router.route(
        question=question,
        chunks=chunks,
        history=conversation_history or [],
        memory_context=memory_context,
    )
    return result.answer


def generate_answer_with_sources(
    question: str,
    chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    memory_context: str = "",
) -> Dict[str, Any]:
    """
    Generate answer and return with source information + routing metadata.

    Returns
    -------
    dict with keys: answer, sources, chunks, route, tool_name,
                    tool_args, tool_result, latency_ms, debug_log
    """
    result: RouteResult = _router.route(
        question=question,
        chunks=chunks,
        history=conversation_history or [],
        memory_context=memory_context,
    )

    # Build sources list (same as before — from chunks metadata)
    sources = []
    seen_sections: set = set()
    for chunk in chunks:
        section = chunk["metadata"].get("section", "General")
        if section not in seen_sections:
            sources.append({
                "section": section,
                "source": chunk["metadata"].get("source", config.DOCUMENT_PATH),
                "page": chunk["metadata"].get("page", 1),
                "relevance_score": chunk.get("score", 0),
            })
            seen_sections.add(section)

    return {
        "answer": result.answer,
        "sources": sources,
        "chunks": chunks,
        # ── new routing metadata for UI and evaluation ──
        "route": result.route,
        "tool_name": result.tool_name,
        "tool_args": result.tool_args,
        "tool_result": result.tool_result,
        "tool_error": result.tool_error,
        "latency_ms": result.latency_ms,
        "debug_log": result.debug_log,
    }
