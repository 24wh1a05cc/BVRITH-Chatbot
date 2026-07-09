"""
Phase 1: Ingest and Index
Loads the Word document, splits into chunks, embeds them, and stores in ChromaDB.
"""

import os
from typing import List, Dict, Any
# Use docx2txt directly instead of deprecated loader
import docx2txt
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import config

def load_document(file_path: str = config.DOCUMENT_PATH) -> List[Dict[str, Any]]:
    """Load the Word document and return as a document with metadata."""
    print(f"Loading document: {file_path}")
    text = docx2txt.process(file_path)
    
    # Create a document-like structure
    from langchain_core.documents import Document as LangchainDocument
    doc = LangchainDocument(
        page_content=text,
        metadata={
            "source": os.path.basename(file_path),
            "page": 1,
        }
    )
    
    print(f"Loaded document: {len(text)} characters")
    return [doc]

def extract_section_heading(text: str) -> str:
    """Extract the main section heading from text content.
    Matches top-level headings like '1. ABOUT BVRIT', '2. DEPARTMENTS & PROGRAMMES', etc.
    Does NOT match numbered list items within sections.
    """
    lines = text.strip().split('\n')
    # Known main section headings from the new document (uppercase convention)
    main_sections = [
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
    
    for line in lines:
        line = line.strip()
        # Check if line matches a known main section heading exactly (case-insensitive)
        if line.upper() in [s.upper() for s in main_sections]:
            # Return the canonical form
            for ms in main_sections:
                if line.upper() == ms.upper():
                    return ms
    
    # Fallback: check for "SECTION NUMBER. ALL CAPS HEADING" pattern (new doc style)
    for line in lines:
        line = line.strip()
        # Match patterns like "1. ABOUT BVRIT", "2. DEPARTMENTS & PROGRAMMES", etc.
        if line and line[0].isdigit() and '. ' in line[:5]:
            parts = line.split('. ', 1)
            if len(parts) == 2 and parts[0].isdigit():
                heading_text = parts[1].strip()
                # All-caps headings indicate section headers (new doc convention)
                if len(heading_text) < 60 and any(c.isupper() for c in heading_text):
                    return parts[0] + '. ' + heading_text
    
    return "General"

def split_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Split documents into chunks with metadata.
    Uses a two-pass approach: first splits, then assigns each chunk to its correct
    section by checking which section heading precedes it in the original document.
    """
    print(f"Splitting with chunk_size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP}")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    
    chunks = text_splitter.split_documents(documents)
    
    # Track current section as we iterate through chunks (in document order)
    current_section = "General"
    section_headings_lower = [s.lower() for s in [
        "1. About BVRIT",
        "1. ABOUT BVRIT",
        "2. Departments & Programmes",
        "2. DEPARTMENTS & PROGRAMMES",
        "3. Fee Structure",
        "3. FEE STRUCTURE",
        "4. Scholarships & Fee Concessions",
        "4. SCHOLARSHIPS & FEE CONCESSIONS",
        "5. Admissions",
        "5. ADMISSIONS",
        "6. Placements",
        "6. PLACEMENTS",
        "7. Campus & Facilities",
        "7. CAMPUS & FACILITIES",
        "8. Key Faculty",
        "8. KEY FACULTY",
        "9. Student Support Services",
        "9. STUDENT SUPPORT SERVICES",
        "10. Contact Information",
        "10. CONTACT INFORMATION",
    ]]
    
    for chunk in chunks:
        # Check if this chunk's content starts with a known section heading
        content_start = chunk.page_content.strip()[:80].lower()
        for sh in section_headings_lower:
            if content_start.startswith(sh):
                # Extract the canonical section name
                section_text = chunk.page_content.strip().split('\n')[0].strip()
                # Map to canonical form
                current_section = section_text
                break
        
        chunk.metadata["section"] = current_section
    
    print(f"Created {len(chunks)} chunks")
    return chunks

def create_embeddings():
    """Create the embedding model using OpenRouter."""
    return OpenAIEmbeddings(
        model=config.EMBEDDING_MODEL,
        openai_api_key=config.OPENROUTER_API_KEY,
        openai_api_base=config.OPENROUTER_BASE_URL,
    )

def create_vector_store(chunks: List[Dict[str, Any]], embeddings) -> Chroma:
    """Create and persist the vector store."""
    print(f"Creating vector store with {len(chunks)} chunks...")
    
    # Extract texts and metadatas
    texts = [chunk.page_content for chunk in chunks]
    metadatas = [chunk.metadata for chunk in chunks]
    
    # Create persistent vector store
    vector_store = Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        persist_directory=config.PERSIST_DIRECTORY,
    )
    
    print(f"Vector store created and persisted to {config.PERSIST_DIRECTORY}")
    return vector_store

def load_vector_store(embeddings) -> Chroma:
    """Load an existing vector store from disk."""
    print(f"Loading vector store from {config.PERSIST_DIRECTORY}...")
    vector_store = Chroma(
        embedding_function=embeddings,
        persist_directory=config.PERSIST_DIRECTORY,
    )
    print(f"Loaded vector store with {vector_store._collection.count()} chunks")
    return vector_store

def get_chunk_count() -> int:
    """Get the total number of chunks in the vector store."""
    embeddings = create_embeddings()
    vector_store = load_vector_store(embeddings)
    return vector_store._collection.count()

def run_ingestion():
    """Run the full ingestion pipeline."""
    print("=" * 60)
    print("BVRITH FAQ Chatbot - Document Ingestion Pipeline")
    print("=" * 60)
    
    # Step 1: Load document
    documents = load_document()
    
    # Step 2: Split into chunks
    chunks = split_documents(documents)
    
    # Step 3: Create embeddings
    embeddings = create_embeddings()
    
    # Step 4: Create and persist vector store
    vector_store = create_vector_store(chunks, embeddings)
    
    # Step 5: Verify
    count = vector_store._collection.count()
    print(f"\n✅ Ingestion complete! Total chunks in index: {count}")
    
    # Print sample chunks with metadata
    print("\n--- Sample Chunks ---")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\nChunk {i+1}:")
        print(f"  Section: {chunk.metadata.get('section', 'N/A')}")
        print(f"  Source: {chunk.metadata.get('source', 'N/A')}")
        print(f"  Content preview: {chunk.page_content[:100]}...")
    
    return count

if __name__ == "__main__":
    run_ingestion()