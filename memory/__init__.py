"""
memory/__init__.py
------------------
Public API for the memory module.
"""
from memory.memory_manager import (
    UserMemory,
    load_user_memory,
    save_user_memory,
    delete_user_memory,
    extract_memory_from_message,
    check_forget_request,
    summarize_conversation,
    build_memory_context,
    manage_history_length,
    MAX_TURNS,
    MEMORY_FILE,
)

__all__ = [
    "UserMemory",
    "load_user_memory",
    "save_user_memory",
    "delete_user_memory",
    "extract_memory_from_message",
    "check_forget_request",
    "summarize_conversation",
    "build_memory_context",
    "manage_history_length",
    "MAX_TURNS",
    "MEMORY_FILE",
]
