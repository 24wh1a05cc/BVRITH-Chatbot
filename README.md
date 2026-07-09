# 🎓 BVRIT Hyderabad College of Engineering — FAQ RAG Chatbot

An intelligent, memory-aware FAQ chatbot for **BVRIT Hyderabad College of Engineering for Women**,
built with LangChain, ChromaDB, OpenRouter LLM, Streamlit, and a three-tier memory architecture.

---

## ✨ Features

| Feature | Description |
|---|---|
| **RAG Pipeline** | ChromaDB vector store + LangChain retrieval + OpenRouter LLM grounding |
| **Function Calling** | Fee Calculator · Date Checker · Percentage Calculator |
| **Three-Tier Memory** | Short-term · Medium-term · Long-term persistent memory |
| **Personalisation** | Language · Detail level · Branch interest auto-adaptation |
| **Privacy** | Forget Me — wipe all stored data on request |
| **Evaluation** | RAGAS + custom test suite (20 test cases) |
| **Photo Gallery** | Image search from bvrithyderabad.edu.in |

---

## 🗂️ Project Structure

```
BVRITH/
├── app.py                  # Streamlit UI — main entry point
├── config.py               # Constants, env vars, model names
├── generator.py            # generate_answer_with_sources() → Router
├── retriever.py            # ChromaDB similarity search
├── ingest.py               # Document → chunks → embeddings → ChromaDB
│
├── memory/                 # ← NEW: Three-tier memory module
│   ├── __init__.py         # Public API exports
│   └── memory_manager.py   # UserMemory, load/save/extract/summarize
│
├── routing/
│   ├── __init__.py
│   └── router.py           # CONVERSATION / RAG / TOOL_CALL routing
│
├── tools/
│   ├── __init__.py
│   ├── schemas.py          # Tool JSON schemas
│   └── executors.py        # Tool execution logic
│
├── validators/
│   ├── __init__.py
│   └── models.py           # Input validation (Pydantic)
│
├── evaluation.py           # RAGAS + LLM-judge evaluation pipeline
├── gallery.py              # Photo gallery helpers
├── user_memory.json        # ← Auto-created: persistent user preferences
└── chroma_db/              # Vector store (ChromaDB)
```

---

## 🧠 Memory Architecture

The chatbot implements **three tiers of memory**, each with a distinct scope and lifecycle.

### Tier 1 — Short-Term Memory (In-Session)

| Attribute | Value |
|---|---|
| **Storage** | `st.session_state.messages` (Streamlit) |
| **Scope** | Current browser session only |
| **Max Size** | `MAX_TURNS = 20` messages before summarisation |
| **Format** | `[{"role": "user"/"assistant", "content": "..."}]` |

Every user message and every assistant response is appended to `st.session_state.messages`.
The full history is passed to the LLM on every turn, so follow-up questions like
*"Tell me more about the first one"* resolve correctly.

```
User types → process_chat_message() →
  history = st.session_state.messages[:-1]  (all prior turns)
  → generate_answer_with_sources(question, chunks, history, memory_context)
  → Router.route(question, chunks, history, memory_context)
  → LLM receives: CONTEXT + HISTORY + USER PREFERENCES + QUESTION
```

---

### Tier 2 — Medium-Term Memory (Auto Summarisation)

| Attribute | Value |
|---|---|
| **Trigger** | `len(history) > MAX_TURNS` (>20 messages) |
| **Storage** | `UserMemory.previous_session_summary` (in-memory + persisted) |
| **Function** | `manage_history_length(history, memory)` |

When the conversation grows beyond 20 messages, the oldest messages are compressed:

```
history (21+ messages)
  ↓
manage_history_length()
  ├── old_messages = history[:-10]          # everything except last 10
  ├── summarize_conversation(old_messages)  # LLM summarises → string
  ├── memory.previous_session_summary = summary
  └── return history[-10:], memory          # keep only last 10 messages
```

The summary preserves: user name, branch interest, language, important Q&A pairs, unresolved topics.
On next conversation restart, the summary is loaded from disk and injected into every prompt.

---

### Tier 3 — Long-Term Memory (Persistent)

| Attribute | Value |
|---|---|
| **Storage** | `user_memory.json` (JSON file on disk) |
| **Loaded** | On every Streamlit app start via `load_user_memory()` |
| **Saved** | After every user message via `save_user_memory()` |
| **Fields** | `user_name`, `preferred_language`, `branch_interest`, `answer_detail_level`, `previous_session_summary` |

```json
{
  "user_name": "Bhavya",
  "preferred_language": "Telugu",
  "branch_interest": "CSE",
  "answer_detail_level": "Detailed",
  "previous_session_summary": "User is interested in CSE fees and placements."
}
```

Memory is automatically injected into LLM prompts via `build_memory_context()`:

```
## USER PREFERENCES
- Name: Bhavya
- Language: Telugu
- Branch Interest: CSE
- Answer Detail Level: Detailed

## PREVIOUS SESSION CONTEXT
User asked about CSE fees and placement statistics in last session.
```

---

## 🔄 Data Flow Diagram

```
USER TYPES A MESSAGE
         │
         ▼
┌─────────────────────────────────────────────┐
│  check_forget_request(user_input)           │
│  → if True: wipe memory, confirm, return    │
└─────────────────────────────────────────────┘
         │ (not a forget request)
         ▼
┌─────────────────────────────────────────────┐
│  RETRIEVAL (retriever.py)                   │
│  retrieve_chunks(user_input, top_k=5)       │
│  → ChromaDB similarity search               │
│  → returns top-K document chunks            │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  SHORT-TERM MEMORY (session_state.messages) │
│  history = all prior messages               │
│                                             │
│  MEDIUM-TERM: manage_history_length()       │
│  → summarise if > MAX_TURNS messages        │
│                                             │
│  LONG-TERM: build_memory_context(memory)   │
│  → load preferences from user_memory.json  │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  ROUTING ENGINE (routing/router.py)         │
│                                             │
│  Route A: CONVERSATION                      │
│    short greeting → plain LLM              │
│                                             │
│  Route B: RAG                               │
│    question + context + history             │
│    + memory_context → LLM → answer         │
│                                             │
│  Route C: TOOL_CALL                         │
│    LLM signals tool → executor runs        │
│    → result fed back to LLM → answer       │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  RESPONSE DISPLAYED IN CHAT UI              │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  MEMORY EXTRACTION (memory_manager.py)      │
│  extract_memory_from_message(user_input)    │
│  → detect name, branch, language, detail    │
│  → update session_state.user_memory         │
│  save_user_memory() → user_memory.json      │
└─────────────────────────────────────────────┘
```

---

## 🔍 How the Three Memory Tiers Work Together

```
Session Start
    │
    ▼
[LONG-TERM] load_user_memory()
    │  reads user_memory.json → UserMemory object
    │  injected into every LLM prompt as ## USER PREFERENCES
    │
    ▼
User asks Q1 → [SHORT-TERM] history = [] → LLM answers
User asks Q2 → [SHORT-TERM] history = [Q1, A1] → LLM answers with context
User asks Q3 → [SHORT-TERM] history = [Q1,A1,Q2,A2] → LLM answers with full context
...
User asks Q11 (history > MAX_TURNS=20)
    │
    ▼
[MEDIUM-TERM] manage_history_length()
    │  summarises Q1..Q10 → stored in UserMemory.previous_session_summary
    │  saved to disk immediately
    │  keeps only Q11..Q20 in active history
    │
    ▼
[SHORT-TERM] history = [Q11..Q20]
[MEDIUM-TERM] summary injected in ## PREVIOUS SESSION CONTEXT
[LONG-TERM] preferences injected in ## USER PREFERENCES
    → LLM has full continuity despite trimmed history

Session End / Restart
    │
    ▼
[LONG-TERM] user_memory.json persists across sessions
    → next session loads name, language, branch, summary automatically
```

---

## 🛡️ Privacy & Security

### What is stored
| Field | Purpose |
|---|---|
| `user_name` | Personalised greeting |
| `preferred_language` | Response language adaptation |
| `branch_interest` | Branch-aware fee lookups |
| `answer_detail_level` | Response verbosity |
| `previous_session_summary` | Continuity across sessions |

### What is NEVER stored
- Phone numbers, Aadhaar numbers, PAN card numbers
- Passwords or PINs
- Credit/debit card numbers, CVV codes
- Email addresses
- Complete conversation transcripts

### Forget Me
If the user says *"forget everything about me"*, *"delete my memory"*, *"clear my data"*,
or *"reset my preferences"*, the bot:
1. Deletes `user_memory.json` from disk
2. Clears `st.session_state.user_memory` in-session
3. Confirms deletion with a friendly message

---

## 🚀 Quick Start

```bash
# 1. Create environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up API key
echo "OPENROUTER_API_KEY=your_key_here" > .env

# 4. Run the app
streamlit run app.py
```

---

## 🧪 Test Scenarios

### Scenario 1 — Follow-up reference (short-term memory)
```
User:  What branches does BVRIT offer?
User:  Tell me more about the first one.
→ Bot remembers "first one" from previous turn ✓
```

### Scenario 2 — Name recall (long-term memory)
```
User:  My name is Bhavya.
<restart app>
User:  What is my name?
→ Bot: "Your name is Bhavya" ✓  (loaded from user_memory.json)
```

### Scenario 3 — Branch-aware fee query (personalisation)
```
User:  I am interested in CSE.
User:  What is the fee?
→ Bot: "The CSE annual fee is..." (assumes CSE from stored preference) ✓
```

### Scenario 4 — Language personalisation
```
User:  Please answer in Telugu.
User:  What are the placements like?
→ Bot responds in Telugu ✓
```

### Scenario 5 — Forget Me
```
User:  Forget everything about me.
→ Bot: "✅ Memory cleared. All your preferences have been permanently removed." ✓
→ user_memory.json deleted ✓
```

---

## 📁 Files Modified / Created

### New Files
| File | Purpose |
|---|---|
| `memory/__init__.py` | Public API exports for memory module |
| `user_memory.json` | Auto-created: persistent user preferences (JSON) |

### Modified Files
| File | Changes |
|---|---|
| `memory/memory_manager.py` | Added: `extract_memory_from_message`, `check_forget_request`, `summarize_conversation`, `build_memory_context`, `manage_history_length` |
| `routing/router.py` | Added `memory_context` param to `route()`, updated all 3 prompt templates |
| `generator.py` | Added `memory_context` param to `generate_answer()` and `generate_answer_with_sources()` |
| `app.py` | Memory imports, session init, forget-me handler, history management, memory extraction, memory sidebar panel |

---

## 💡 Suggestions for Further Improvements

1. **SQLite backend** — replace `user_memory.json` with SQLite for multi-user support (each user identified by a session token or login)

2. **Semantic memory extraction** — replace regex with an LLM-based preference extractor for more robust detection (e.g., "मेरा नाम भव्या है" in Hindi)

3. **Memory confidence scoring** — track how many times a preference was confirmed before persisting it, to avoid accidental overwrites

4. **User authentication** — add a simple login so multiple users on the same device have separate memory files

5. **Memory diff UI** — show the user exactly what was learned ("I just remembered that you're interested in CSE — is that right?")

6. **Encrypted storage** — encrypt `user_memory.json` at rest using `cryptography.fernet` for stronger privacy

7. **Explicit consent prompt** — on first run, ask the user whether they want memory to be saved, and respect their preference

8. **Auto language detection** — detect the language the user is writing in (via `langdetect`) and respond in the same language automatically, even without an explicit preference

---

## 🧑‍💻 Architecture Credits

Built on top of the BVRIT FAQ RAG system (Day 1–4) with Memory & Personalisation added in Day 5 Session 2.

- **LangChain** — RAG orchestration, LLM bindings, message types
- **ChromaDB** — Vector store for document chunk retrieval
- **OpenRouter** — LLM API gateway (GPT-4o-mini)
- **Streamlit** — Chat UI and session state management
- **Python regex** — Fast, free preference extraction (no extra LLM cost)
