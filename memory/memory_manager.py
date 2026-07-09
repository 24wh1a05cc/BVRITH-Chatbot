"""
memory/memory_manager.py
------------------------
Complete memory management module for the BVRIT FAQ RAG Chatbot.

Responsibilities
────────────────
• Short-term  : conversation history passed per-turn (handled by app.py)
• Medium-term : automatic summarisation when history exceeds MAX_TURNS
• Long-term   : persistent user preferences stored in MEMORY_FILE (JSON)

Public API (imported via memory/__init__.py)
────────────────────────────────────────────
  UserMemory                  – dataclass for user preferences
  load_user_memory()          – read preferences from disk
  save_user_memory()          – write preferences to disk (sanitised)
  delete_user_memory()        – wipe the on-disk file
  extract_memory_from_message()  – parse a single message for preferences
  check_forget_request()      – detect "forget me / clear data" intent
  summarize_conversation()    – LLM-based conversation summarisation
  build_memory_context()      – build prompt-injection string from memory
  manage_history_length()     – trim + summarise history when it grows too long
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

# langchain_openai is already a project dependency (used by router.py / generator.py)
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

logger = logging.getLogger("bvrit.memory")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Number of conversation turns that triggers medium-term summarisation.
# A "turn" = one user message + one assistant message, but here we count
# individual messages in the flat history list.
MAX_TURNS: int = 20

# Path of the JSON file used for long-term (cross-session) memory.
MEMORY_FILE: str = "user_memory.json"

# Regex patterns for data that must NEVER be stored in memory.
# Each pattern is compiled case-insensitively at import time.
SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b\d{10}\b",                        # 10-digit phone numbers
        r"\b\d{12}\b",                        # Aadhaar / 12-digit IDs
        r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",# Aadhaar with separators
        r"password\s*[=:]\s*\S+",             # password=xxx / password: xxx
        r"\bpass(?:word)?\b.{0,10}\d{4,}",    # password near digits
        r"\b[A-Z]{2}\d{2}[A-Z]{2}\d{4}\b",    # PAN card format
        r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d[Z][A-Z\d]\b",  # GSTIN
        r"\b(?:\d[ -]*?){13,16}\b",           # Credit/debit card numbers
        r"\b\d{9,18}\b",                      # Generic long numeric IDs (bank acc)
        r"cvv\s*[=:]\s*\d{3,4}",             # CVV codes
        r"pin\s*[=:]\s*\d{4,6}",             # PIN codes
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",  # Email addresses
    ]
]


# ─────────────────────────────────────────────────────────────────────────────
# UserMemory dataclass
# ─────────────────────────────────────────────────────────────────────────────

class UserMemory:
    """
    Stores persistent user preferences across sessions.

    Fields
    ------
    user_name              : Display name the user provided (e.g. "Bhavya")
    preferred_language     : Language for bot responses (default "English")
    branch_interest        : Engineering branch the user is interested in
    answer_detail_level    : "Brief" or "Detailed" (default "Detailed")
    previous_session_summary : LLM-generated summary of a prior session
    """

    def __init__(
        self,
        user_name: Optional[str] = None,
        preferred_language: Optional[str] = "English",
        branch_interest: Optional[str] = None,
        answer_detail_level: Optional[str] = "Detailed",
        previous_session_summary: Optional[str] = None,
    ) -> None:
        self.user_name = user_name
        self.preferred_language = preferred_language
        self.branch_interest = branch_interest
        self.answer_detail_level = answer_detail_level
        self.previous_session_summary = previous_session_summary

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for JSON storage."""
        return {
            "user_name": self.user_name,
            "preferred_language": self.preferred_language,
            "branch_interest": self.branch_interest,
            "answer_detail_level": self.answer_detail_level,
            "previous_session_summary": self.previous_session_summary,
        }

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict) -> "UserMemory":
        """
        Reconstruct a UserMemory from a dict (e.g. loaded from JSON).

        Unknown keys are silently ignored so that old files remain
        forward-compatible when new fields are added.
        """
        return cls(
            user_name=d.get("user_name"),
            preferred_language=d.get("preferred_language", "English"),
            branch_interest=d.get("branch_interest"),
            answer_detail_level=d.get("answer_detail_level", "Detailed"),
            previous_session_summary=d.get("previous_session_summary"),
        )

    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"UserMemory(name={self.user_name!r}, lang={self.preferred_language!r}, "
            f"branch={self.branch_interest!r}, detail={self.answer_detail_level!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _contains_sensitive_data(text: str) -> bool:
    """
    Return True if *text* matches any pattern in SENSITIVE_PATTERNS.

    Used as a guard before writing any string to persistent storage.
    """
    if not text:
        return False
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "Sensitive data pattern matched — value will not be stored."
            )
            return True
    return False


def _sanitise_memory(memory: UserMemory) -> UserMemory:
    """
    Return a copy of *memory* with sensitive field values cleared.

    This is a last-resort safety net applied just before writing to disk.
    String fields are checked individually; the session summary (which can
    be long) is also checked.
    """
    d = memory.to_dict()
    for key, value in d.items():
        if isinstance(value, str) and _contains_sensitive_data(value):
            logger.warning("Clearing sensitive field before save: %s", key)
            d[key] = None
    return UserMemory.from_dict(d)


# ─────────────────────────────────────────────────────────────────────────────
# Persistence — load / save / delete
# ─────────────────────────────────────────────────────────────────────────────

def load_user_memory() -> UserMemory:
    """
    Load user preferences from MEMORY_FILE.

    Returns a default UserMemory() if the file does not exist, cannot be
    parsed, or any other error occurs.  Errors are logged but never raised
    so that a missing or corrupt file never crashes the chatbot.

    Returns
    -------
    UserMemory
        Populated from disk, or default instance on any failure.
    """
    if not os.path.exists(MEMORY_FILE):
        logger.debug("Memory file not found (%s) — returning defaults.", MEMORY_FILE)
        return UserMemory()

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        memory = UserMemory.from_dict(data)
        logger.info("User memory loaded from %s: %r", MEMORY_FILE, memory)
        return memory
    except json.JSONDecodeError as exc:
        logger.error("Memory file is corrupt (%s) — resetting. Error: %s", MEMORY_FILE, exc)
        return UserMemory()
    except OSError as exc:
        logger.error("Could not read memory file (%s): %s", MEMORY_FILE, exc)
        return UserMemory()


def save_user_memory(memory: UserMemory) -> None:
    """
    Write user preferences to MEMORY_FILE as JSON.

    Sensitive data is stripped before writing.  Any OS-level errors are
    logged but not raised so the chatbot continues functioning even if
    the disk is read-only or full.

    Parameters
    ----------
    memory : UserMemory
        The preferences object to persist.
    """
    safe_memory = _sanitise_memory(memory)
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(safe_memory.to_dict(), fh, ensure_ascii=False, indent=2)
        logger.info("User memory saved to %s.", MEMORY_FILE)
    except OSError as exc:
        logger.error("Could not write memory file (%s): %s", MEMORY_FILE, exc)


def delete_user_memory() -> None:
    """
    Delete MEMORY_FILE from disk.

    Safe to call even if the file does not exist — no exception is raised
    in that case.  Logs the outcome either way.
    """
    if os.path.exists(MEMORY_FILE):
        try:
            os.remove(MEMORY_FILE)
            logger.info("User memory file deleted: %s", MEMORY_FILE)
        except OSError as exc:
            logger.error("Could not delete memory file (%s): %s", MEMORY_FILE, exc)
    else:
        logger.debug("delete_user_memory called but file does not exist: %s", MEMORY_FILE)


# ─────────────────────────────────────────────────────────────────────────────
# Message-level preference extraction
# ─────────────────────────────────────────────────────────────────────────────

# Pre-compiled patterns used by extract_memory_from_message.
# "i am" pattern uses a negative lookahead to avoid capturing non-name words
# (e.g. "I am interested in CSE" should NOT capture "interested" as a name)
_NAME_STOPWORDS = (
    "interested|looking|studying|a|an|the|from|in|at|going|planning|"
    "here|ready|good|bad|new|happy|sad|ok|okay|fine|well|sorry|not|"
    "asking|trying|checking|wondering|hoping|considering|applying"
)
_NAME_PATTERNS: list[re.Pattern] = [
    re.compile(r"my name is\s+([A-Za-z][a-zA-Z'-]{1,})", re.IGNORECASE),
    re.compile(
        r"i am\s+(?!(?:" + _NAME_STOPWORDS + r")\b)([A-Z][a-z]{1,})",
        re.IGNORECASE,
    ),
    re.compile(r"call me\s+([A-Za-z][a-zA-Z'-]{1,})", re.IGNORECASE),
]

_BRANCH_PATTERN: re.Pattern = re.compile(
    r"interested in\s+(CSE|ECE|EEE|MECH|CIVIL|IT|AIDS|AIML)\b",
    re.IGNORECASE,
)

_LANGUAGE_PATTERNS: list[re.Pattern] = [
    re.compile(r"answer in\s+(Telugu|Hindi|English)\b", re.IGNORECASE),
    re.compile(r"respond in\s+(Telugu|Hindi|English)\b", re.IGNORECASE),
    re.compile(r"reply in\s+(Telugu|Hindi|English)\b", re.IGNORECASE),
]

_DETAIL_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Brief: matches "brief answer", "short answer", "concise answer", "be brief", "keep it short"
    (re.compile(
        r"\b(brief\s+answer|short\s+answer|concise\s+answer|be\s+brief|keep\s+it\s+short|give.*short)\b",
        re.IGNORECASE,
    ), "Brief"),
    # Detailed: matches "detailed answer", "explain in detail", "prefer detailed", "detailed explanation", "detailed response"
    (re.compile(
        r"\b(detailed\s+(?:answer|explanation|response|explanations)|"
        r"explain\s+in\s+detail|prefer\s+detailed|"
        r"give.*detailed|elaborate|in\s+detail)\b",
        re.IGNORECASE,
    ), "Detailed"),
]


def extract_memory_from_message(
    role: str,
    content: str,
    memory: UserMemory,
) -> UserMemory:
    """
    Parse a single conversation message for explicit user preferences and
    update *memory* accordingly.

    Only updates a field when the user explicitly states something NEW —
    existing values are not overwritten with identical ones.  Uses compiled
    regex patterns (no LLM calls) so it is fast and free.

    Parameters
    ----------
    role : str
        Message role — only "user" messages are scanned for preferences.
    content : str
        Raw message text.
    memory : UserMemory
        Current memory state to update in-place and return.

    Returns
    -------
    UserMemory
        The same *memory* object, possibly with updated fields.
    """
    if role != "user" or not content:
        return memory

    # ── Name detection ────────────────────────────────────────────────────
    for pattern in _NAME_PATTERNS:
        match = pattern.search(content)
        if match:
            name = match.group(1).strip().capitalize()
            if name and not _contains_sensitive_data(name) and name != memory.user_name:
                logger.debug("Detected user name: %r", name)
                memory.user_name = name
            break  # first pattern that matches wins

    # ── Branch interest ───────────────────────────────────────────────────
    match = _BRANCH_PATTERN.search(content)
    if match:
        branch = match.group(1).upper()
        if branch != memory.branch_interest:
            logger.debug("Detected branch interest: %r", branch)
            memory.branch_interest = branch

    # ── Language preference ───────────────────────────────────────────────
    for pattern in _LANGUAGE_PATTERNS:
        match = pattern.search(content)
        if match:
            lang = match.group(1).capitalize()
            if lang != memory.preferred_language:
                logger.debug("Detected language preference: %r", lang)
                memory.preferred_language = lang
            break

    # ── Detail level ──────────────────────────────────────────────────────
    for pattern, level in _DETAIL_PATTERNS:
        if pattern.search(content):
            if level != memory.answer_detail_level:
                logger.debug("Detected detail level: %r", level)
                memory.answer_detail_level = level
            break

    return memory


# ─────────────────────────────────────────────────────────────────────────────
# Forget / clear intent detection
# ─────────────────────────────────────────────────────────────────────────────

_FORGET_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"forget everything",
        r"forget me",
        r"delete my memory",
        r"clear my data",
        r"reset my preferences",
        r"clear my memory",
        r"delete everything about me",
    ]
]


def check_forget_request(user_message: str) -> bool:
    """
    Return True if *user_message* expresses an intent to erase stored memory.

    Matching is case-insensitive.  Any single pattern match is sufficient.

    Parameters
    ----------
    user_message : str
        The raw text typed by the user.

    Returns
    -------
    bool
        True when a forget/clear/delete intent is detected.
    """
    if not user_message:
        return False
    for pattern in _FORGET_PATTERNS:
        if pattern.search(user_message):
            logger.info("Forget request detected in message.")
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# LLM-based conversation summarisation
# ─────────────────────────────────────────────────────────────────────────────

def summarize_conversation(
    history: list[dict],
    existing_summary: Optional[str] = None,
) -> str:
    """
    Summarise a conversation history using the configured LLM.

    The summary preserves: user name, branch interest, language preference,
    important questions asked, key answers given, and unresolved topics.
    If *existing_summary* is provided it is incorporated so context from
    earlier sessions is not lost.

    Parameters
    ----------
    history : list[dict]
        List of ``{"role": ..., "content": ...}`` message dicts.
    existing_summary : str | None
        A prior session summary to fold into the new one (optional).

    Returns
    -------
    str
        LLM-generated summary, or ``"Session summary unavailable."`` on
        any error.
    """
    import config  # local import — avoids circular dependency at module load

    if not history:
        return existing_summary or "Session summary unavailable."

    # Build the transcript for the prompt
    transcript_lines: list[str] = []
    for msg in history:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "")
        transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)

    prior_context = (
        f"\n\nPrevious session summary (incorporate this):\n{existing_summary}"
        if existing_summary
        else ""
    )

    prompt = (
        "You are a memory assistant for the BVRIT college chatbot. "
        "Summarise the conversation below concisely but completely. "
        "Your summary MUST preserve:\n"
        "  • User's name (if mentioned)\n"
        "  • Branch interest (if mentioned)\n"
        "  • Preferred language (if mentioned)\n"
        "  • Important questions the user asked\n"
        "  • Key answers or facts provided\n"
        "  • Any unresolved topics or follow-up questions\n"
        f"{prior_context}\n\n"
        f"Conversation transcript:\n{transcript}\n\n"
        "Write the summary now:"
    )

    try:
        llm = ChatOpenAI(
            model=config.LLM_MODEL,
            temperature=0,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        summary = response.content.strip()
        logger.info("Conversation summarised successfully (%d chars).", len(summary))
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.error("summarize_conversation LLM call failed: %s", exc)
        return "Session summary unavailable."


# ─────────────────────────────────────────────────────────────────────────────
# Prompt-injection context builder
# ─────────────────────────────────────────────────────────────────────────────

def build_memory_context(memory: UserMemory) -> str:
    """
    Build a formatted string from *memory* suitable for injection into
    LLM system prompts.

    Returns an empty string if the memory object carries no useful
    information (all fields are None or default placeholder values).

    Parameters
    ----------
    memory : UserMemory
        The user's persistent preferences.

    Returns
    -------
    str
        A markdown-style context block, or ``""`` when nothing is known.
    """
    pref_lines: list[str] = []

    if memory.user_name:
        pref_lines.append(f"- Name: {memory.user_name}")

    if memory.preferred_language and memory.preferred_language != "English":
        # "English" is the default — only surface it if explicitly set
        pref_lines.append(f"- Language: {memory.preferred_language}")
    elif memory.preferred_language == "English":
        # Include English explicitly so the LLM always knows the language
        pref_lines.append(f"- Language: {memory.preferred_language}")

    if memory.branch_interest:
        pref_lines.append(f"- Branch Interest: {memory.branch_interest}")

    if memory.answer_detail_level:
        pref_lines.append(f"- Answer Detail Level: {memory.answer_detail_level}")

    has_prefs = bool(pref_lines)
    has_summary = bool(memory.previous_session_summary)

    if not has_prefs and not has_summary:
        return ""

    sections: list[str] = []

    if has_prefs:
        sections.append("## USER PREFERENCES\n" + "\n".join(pref_lines))

    if has_summary:
        sections.append(
            "## PREVIOUS SESSION CONTEXT\n" + memory.previous_session_summary
        )

    return "\n\n".join(sections)


# ─────────────────────────────────────────────────────────────────────────────
# History length management
# ─────────────────────────────────────────────────────────────────────────────

def manage_history_length(
    history: list[dict],
    memory: UserMemory,
) -> tuple[list, UserMemory]:
    """
    Trim the conversation history and persist older turns as a summary.

    When ``len(history) > MAX_TURNS`` the oldest messages are summarised
    via :func:`summarize_conversation` and the resulting text is stored in
    ``memory.previous_session_summary``.  Only the most recent 10 messages
    are kept in the active history.

    Parameters
    ----------
    history : list[dict]
        Current flat list of ``{"role", "content"}`` message dicts.
    memory : UserMemory
        Current user memory (will be mutated if trimming occurs).

    Returns
    -------
    tuple[list, UserMemory]
        ``(trimmed_history, updated_memory)``  — unchanged when no
        trimming is needed.
    """
    if len(history) <= MAX_TURNS:
        return history, memory

    # Messages to be summarised are everything except the last 10
    old_messages = history[:-10]
    recent_messages = history[-10:]

    logger.info(
        "History length %d exceeds MAX_TURNS=%d — summarising %d old messages.",
        len(history),
        MAX_TURNS,
        len(old_messages),
    )

    new_summary = summarize_conversation(
        old_messages,
        existing_summary=memory.previous_session_summary,
    )
    memory.previous_session_summary = new_summary

    return recent_messages, memory
