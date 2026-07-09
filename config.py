"""
Configuration and constants for the BVRIT FAQ Chatbot.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Embedding Model
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# LLM for Generation
LLM_MODEL = "gpt-4o-mini"  # Fast, cost-effective for generation

# LLM for Test Generation & Judging (use mini to stay within free-tier credits)
JUDGE_LLM_MODEL = "gpt-4o-mini"  # ~20x cheaper than gpt-4o, sufficient for judging

# Chunking Strategy — larger document, larger chunk size for richer context
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Retrieval
TOP_K = 5

# Vector Store
PERSIST_DIRECTORY = "./chroma_db"

# Document Path
DOCUMENT_PATH = "bvrit_college_info.docx"

# Streamlit Settings
APP_TITLE = "🎓 BVRIT FAQ Chatbot"
APP_ICON = "🎓"

# Section Headings for Metadata Filtering (matching new document)
SECTIONS = [
    "All Sections",
    "1. ABOUT BVRIT",
    "2. DEPARTMENTS & PROGRAMMES",
    "3. FEE STRUCTURE",
    "4. SCHOLARSHIPS & FEE CONCESSIONS",
    "5. ADMISSIONS",
    "6. PLACEMENTS",
    "7. CAMPUS & FACILITIES",
    "8. KEY FACULTY",
    "9. STUDENT SUPPORT SERVICES",
    "10. CONTACT INFORMATION",
]

# Performance SLA (seconds)
PERFORMANCE_SLA = 10.0