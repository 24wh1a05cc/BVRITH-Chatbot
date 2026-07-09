"""
routing/router.py
-----------------
Full function-calling routing engine for the BVRIT chatbot.

ROUTING PATHS
─────────────
1. CONVERSATION  — short/greeting input, no chunks needed, plain LLM.
2. RAG_ONLY      — question answered purely from retrieved context.
3. TOOL_CALL     — LLM signals a tool; executor runs; LLM gets result; final answer.

Every decision is logged via Python's standard logging module so the UI can
display it in debug mode and the evaluation table can record it.

The router does NOT modify the retrieval pipeline, embeddings, or citations.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

import config
from tools import BVRIT_TOOLS, dispatch, ToolExecutionError
from validators import validate_tool_args

logger = logging.getLogger("bvrit.router")

# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

ROUTE_CONVERSATION = "CONVERSATION"
ROUTE_RAG          = "RAG"
ROUTE_TOOL         = "TOOL_CALL"


@dataclass
class RouteResult:
    """Everything produced during one routing cycle."""
    route: str                          # CONVERSATION | RAG | TOOL_CALL
    question: str
    answer: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    tool_error: Optional[str] = None
    chunks_used: int = 0
    latency_ms: float = 0.0
    debug_log: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

_GROUNDING_PROMPT = """\
You are BVRIT Bot, a helpful assistant for BVRIT Hyderabad College of Engineering for Women.

## RULES
1. Answer ONLY from the provided context. Never invent BVRIT-specific facts.
2. Cite every factual claim: [Section Name].
3. If the answer is not in context, say so and direct the user to info@bvrit.ac.in.
4. When tool results are present, use them directly in your answer.
5. Keep answers clear and concise.
6. If the user has specified a preferred language, respond in that language.
7. If the user has specified a branch interest and asks about fees without specifying branch, assume their branch.
8. If detail level is 'Brief', give concise answers. If 'Detailed', give thorough answers.

{memory_context}
## CONTEXT
{context}

## CONVERSATION HISTORY
{history}

## USER QUESTION
{question}

## ANSWER
"""

_CONVERSATION_PROMPT = """\
You are BVRIT Bot, a helpful assistant for BVRIT Hyderabad College of Engineering for Women.
Respond warmly and briefly to greetings and general conversation.
If the user asks anything specific about BVRIT (fees, admissions, departments, etc.),
tell them to ask a specific question so you can look it up.
{memory_context}
USER: {question}
BOT:"""

_TOOL_FOLLOWUP_PROMPT = """\
You are BVRIT Bot. A calculation tool has just produced the result below.
Incorporate the tool result naturally into a helpful, well-formatted answer.
Add any relevant context from the BVRIT document if available.
Always cite sources with [Section Name] format.
{memory_context}
## TOOL RESULT
{tool_result}

## DOCUMENT CONTEXT
{context}

## USER QUESTION
{question}

## ANSWER
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_GREETING_KEYWORDS = {
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "bye", "goodbye", "ok", "okay", "sure",
}


def _is_conversational(question: str) -> bool:
    """Return True for short greetings / chit-chat that need no RAG."""
    q = question.strip().lower().rstrip("!.,?")
    tokens = set(q.split())
    # Pure greeting: very short AND only greeting words
    if len(tokens) <= 4 and tokens & _GREETING_KEYWORDS:
        return True
    return False


def _format_context(chunks: List[Dict[str, Any]]) -> str:
    parts = []
    for i, c in enumerate(chunks):
        section = c["metadata"].get("section", "General")
        parts.append(f"[Source {i+1}] Section: {section}\n{c['content']}\n")
    return "\n".join(parts) if parts else "No context retrieved."


def _format_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return "No previous conversation."
    lines = []
    for m in history[-6:]:
        lines.append(f"{m.get('role','user').upper()}: {m.get('content','')}")
    return "\n".join(lines)


def _get_llm(tools: bool = True) -> ChatOpenAI:
    llm = ChatOpenAI(
        model=config.LLM_MODEL,
        openai_api_key=config.OPENROUTER_API_KEY,
        openai_api_base=config.OPENROUTER_BASE_URL,
        temperature=0.1,
        max_tokens=1024,
    )
    if tools:
        llm = llm.bind_tools(BVRIT_TOOLS)
    return llm


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

class Router:
    """
    Routes a user question to the correct handler and returns a RouteResult.

    Usage
    -----
    router = Router()
    result = router.route(question, chunks, history)
    """

    def route(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        history: Optional[List[Dict[str, str]]] = None,
        memory_context: str = "",
    ) -> RouteResult:
        t0 = time.time()
        history = history or []
        debug: List[str] = []

        # ── Path 1: Conversational ────────────────────────────────────────────
        if _is_conversational(question):
            debug.append(f"[ROUTER] Route selected: {ROUTE_CONVERSATION}")
            logger.info("Route: CONVERSATION | question=%r", question)
            prompt = _CONVERSATION_PROMPT.format(question=question, memory_context=memory_context)
            llm = _get_llm(tools=False)
            response = llm.invoke([HumanMessage(content=prompt)])
            return RouteResult(
                route=ROUTE_CONVERSATION,
                question=question,
                answer=response.content,
                chunks_used=0,
                latency_ms=round((time.time() - t0) * 1000, 1),
                debug_log=debug,
            )

        # ── Path 2 & 3: Build grounding prompt, call LLM with tools ──────────
        context_str = _format_context(chunks)
        history_str = _format_history(history)
        prompt = _GROUNDING_PROMPT.format(
            memory_context=memory_context,
            context=context_str,
            history=history_str,
            question=question,
        )

        debug.append(f"[ROUTER] Calling LLM with {len(BVRIT_TOOLS)} tools bound ...")
        logger.info("Route: evaluating | question=%r | chunks=%d", question, len(chunks))

        llm = _get_llm(tools=True)
        first_response = llm.invoke([HumanMessage(content=prompt)])

        # ── Path 3: Tool call signalled ───────────────────────────────────────
        if first_response.tool_calls:
            tc = first_response.tool_calls[0]
            tool_name = tc["name"]
            tool_args = tc["args"]

            debug.append(f"[ROUTER] Route selected: {ROUTE_TOOL}")
            debug.append(f"[TOOL]   Name={tool_name}")
            debug.append(f"[TOOL]   Args={json.dumps(tool_args, ensure_ascii=False)}")
            logger.info(
                "Route: TOOL_CALL | tool=%s | args=%s", tool_name, tool_args
            )

            # Validate args before execution
            try:
                tool_args = validate_tool_args(tool_name, tool_args)
                debug.append(f"[VALIDATOR] Args validated OK")
            except ValueError as ve:
                debug.append(f"[VALIDATOR] Validation failed: {ve}")
                logger.warning("Validation error | tool=%s | err=%s", tool_name, ve)
                return RouteResult(
                    route=ROUTE_TOOL,
                    question=question,
                    answer=f"⚠️ I couldn't process that request: {ve}",
                    tool_name=tool_name,
                    tool_args=tc["args"],
                    tool_error=str(ve),
                    chunks_used=len(chunks),
                    latency_ms=round((time.time() - t0) * 1000, 1),
                    debug_log=debug,
                )

            # Execute the tool
            try:
                tool_result = dispatch(tool_name, tool_args)
                tool_error = None
                debug.append(f"[TOOL]   Execution OK — {tool_result.get('summary','')[:80]}")
                logger.info("Tool execution success | tool=%s", tool_name)
            except ToolExecutionError as exc:
                tool_result = {"summary": f"Tool error: {exc}"}
                tool_error = str(exc)
                debug.append(f"[TOOL]   Execution ERROR: {exc}")
                logger.warning("Tool execution error | tool=%s | err=%s", tool_name, exc)

            # Feed result back to LLM for final answer
            followup_prompt = _TOOL_FOLLOWUP_PROMPT.format(
                memory_context=memory_context,
                tool_result=tool_result.get("summary", str(tool_result)),
                context=context_str,
                question=question,
            )
            debug.append("[ROUTER] Sending tool result to LLM for final answer ...")
            llm_plain = _get_llm(tools=False)
            final_response = llm_plain.invoke([HumanMessage(content=followup_prompt)])
            answer = final_response.content

            return RouteResult(
                route=ROUTE_TOOL,
                question=question,
                answer=answer,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
                tool_error=tool_error,
                chunks_used=len(chunks),
                latency_ms=round((time.time() - t0) * 1000, 1),
                debug_log=debug,
            )

        # ── Path 2: Plain RAG answer ──────────────────────────────────────────
        debug.append(f"[ROUTER] Route selected: {ROUTE_RAG}")
        logger.info("Route: RAG | question=%r", question)

        return RouteResult(
            route=ROUTE_RAG,
            question=question,
            answer=first_response.content,
            chunks_used=len(chunks),
            latency_ms=round((time.time() - t0) * 1000, 1),
            debug_log=debug,
        )
