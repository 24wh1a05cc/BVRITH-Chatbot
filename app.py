"""
Phase 4 & 6: Streamlit Chat UI + Evaluation Dashboard
Main application entry point.
"""

import streamlit as st
import time
import json
import sys
import os
from typing import List, Dict, Any

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from ingest import run_ingestion, load_document, split_documents, create_embeddings, create_vector_store, get_chunk_count
from retriever import retrieve_chunks, get_vector_store, get_embeddings
from generator import generate_answer_with_sources
from evaluation import (
    generate_test_cases, run_test_suite, run_ragas_evaluation, 
    generate_report, print_report
)
from gallery import is_image_query, get_images_for_query, get_all_categories

# Memory and personalisation imports (Day 5 Session 2)
from memory import (
    UserMemory,
    load_user_memory,
    save_user_memory,
    delete_user_memory,
    extract_memory_from_message,
    check_forget_request,
    build_memory_context,
    manage_history_length,
)

# College name constants
COLLEGE_NAME = "BVRIT Hyderabad College of Engineering for Women"
COLLEGE_SHORT = "BVRIT"
CONTACT_EMAIL = "info@bvrit.ac.in"
CONTACT_WEBSITE = "www.bvrithyderabad.edu.in"
CONTACT_PHONE = "08455-221100"

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "index_ready" not in st.session_state:
    st.session_state.index_ready = False
if "chunk_count" not in st.session_state:
    st.session_state.chunk_count = 0
if "doc_name" not in st.session_state:
    st.session_state.doc_name = config.DOCUMENT_PATH
if "eval_report" not in st.session_state:
    st.session_state.eval_report = None
if "eval_running" not in st.session_state:
    st.session_state.eval_running = False
# Function calling debug state
if "last_route_result" not in st.session_state:
    st.session_state.last_route_result = None
if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = False

# ── Memory session state (Day 5 Session 2) ──────────────────────────────
if "user_memory" not in st.session_state:
    # Load persistent memory from disk on first run
    st.session_state.user_memory = load_user_memory()
if "session_summary" not in st.session_state:
    st.session_state.session_summary = None
if "memory_loaded" not in st.session_state:
    st.session_state.memory_loaded = st.session_state.user_memory.user_name is not None

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def initialize_index():
    """Initialize or load the vector store."""
    try:
        # Check if vector store exists
        if os.path.exists(os.path.join(config.PERSIST_DIRECTORY, "chroma.sqlite3")):
            count = get_chunk_count()
            st.session_state.chunk_count = count
            st.session_state.index_ready = True
            return True
        else:
            # Run ingestion
            with st.spinner("Loading and indexing the document... This may take a minute."):
                count = run_ingestion()
                st.session_state.chunk_count = count
                st.session_state.index_ready = True
            return True
    except Exception as e:
        st.error(f"Error initializing index: {e}")
        return False

def process_chat_message(user_input: str, section_filter: str = None):
    """Process a user message and generate a response."""
    # ── PHASE 7: Forget Me / Privacy feature ────────────────────────────────
    if check_forget_request(user_input):
        delete_user_memory()
        st.session_state.user_memory = UserMemory()
        st.session_state.session_summary = None
        st.session_state.memory_loaded = False
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("assistant"):
            forget_response = (
                "✅ **Memory cleared.** I've deleted all your stored preferences — "
                "your name, language setting, branch interest, and session history "
                "have been permanently removed. This session has also been cleared. "
                "You're starting fresh! 🌟"
            )
            st.markdown(forget_response)
        st.session_state.messages.append({"role": "assistant", "content": forget_response})
        return
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            start_time = time.time()
            
            # Check if the user is asking for images/photos
            is_image_request = is_image_query(user_input)
            
            if is_image_request:
                # Get images matching the query
                image_data = get_images_for_query(user_input, max_images=12)
                
                # Generate a text response about the images
                response = f"📸 **Here are {image_data['title']}**\n\nShowing {image_data['showing']} of {image_data['total']} available images."
                
                # Display the response text
                st.markdown(response)
                
                # Display images in a grid
                images = image_data["images"]
                if images:
                    # Create rows of 3 columns each
                    cols_per_row = 3
                    for i in range(0, len(images), cols_per_row):
                        row_images = images[i:i + cols_per_row]
                        cols = st.columns(cols_per_row)
                        for j, img in enumerate(row_images):
                            with cols[j]:
                                st.image(
                                    img["url"],
                                    caption=img["caption"],
                                    width='stretch',
                                )
                
                latency = time.time() - start_time
                st.caption(f"⏱️ Response time: {latency:.2f}s | 📸 {image_data['showing']} images displayed")
                
                # Add a note about asking for more specific images
                st.info("💡 **Tip:** Try asking for specific images like 'campus photos', 'placement photos', 'event photos', or 'award photos' to see more focused results.")
                
            else:
                # Determine section filter
                filter_val = None if section_filter == "All Sections" else section_filter
                
                # Retrieve relevant chunks
                chunks = retrieve_chunks(
                    user_input,
                    top_k=st.session_state.get("top_k", config.TOP_K),
                    section_filter=filter_val,
                )
                
                if not chunks:
                    response = f"I'm sorry, I don't have information about that in my knowledge base. Please contact the {COLLEGE_NAME} administration directly at {CONTACT_EMAIL} or visit {CONTACT_WEBSITE} for more details."
                    sources = []
                    result = {}
                else:
                    # Generate answer with sources (now includes routing metadata)
                    # ── SHORT-TERM MEMORY: build complete conversation history ──
                    # Include ALL prior messages (not just [:-1] which was incomplete)
                    history = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages[:-1]
                    ]

                    # ── MEDIUM-TERM MEMORY: auto-summarise when history is too long ──
                    history, st.session_state.user_memory = manage_history_length(
                        history, st.session_state.user_memory
                    )

                    # ── LONG-TERM + PERSONALISATION: build memory context string ──
                    mem_ctx = build_memory_context(st.session_state.user_memory)

                    result = generate_answer_with_sources(
                        user_input, chunks, history, memory_context=mem_ctx
                    )
                    response = result["answer"]
                    sources = result["sources"]
                    # Store routing result for sidebar display
                    st.session_state.last_route_result = result
                
                latency = time.time() - start_time
                
                # ── Route badge ──────────────────────────────────────────────
                route = result.get("route", "RAG") if result else "RAG"
                route_colors = {
                    "CONVERSATION": "🗣️",
                    "RAG": "📚",
                    "TOOL_CALL": "🔧",
                }
                route_icon = route_colors.get(route, "💬")
                st.caption(f"{route_icon} **Route: {route}**")
                
                # Display response
                st.markdown(response)
                
                # ── Tool call details ─────────────────────────────────────────
                if result.get("tool_name"):
                    with st.expander(f"🔧 Tool Call: `{result['tool_name']}`", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Arguments passed to tool:**")
                            st.json(result.get("tool_args", {}))
                        with col2:
                            st.markdown("**Tool execution result:**")
                            tool_res = result.get("tool_result", {})
                            if tool_res:
                                st.code(tool_res.get("summary", str(tool_res)), language=None)
                        if result.get("tool_error"):
                            st.error(f"⚠️ Tool error: {result['tool_error']}")
                
                # ── Sources expander ──────────────────────────────────────────
                if chunks:
                    with st.expander("📚 Sources", expanded=False):
                        for i, chunk in enumerate(chunks):
                            section = chunk["metadata"].get("section", "General")
                            score = chunk.get("score", 0)
                            st.markdown(f"**Source {i+1}** — Section: `{section}` (Relevance: {score:.2f})")
                            st.caption(chunk["content"][:200] + "...")
                            st.divider()
                
                # ── Debug log expander ────────────────────────────────────────
                if st.session_state.debug_mode and result.get("debug_log"):
                    with st.expander("🐛 Debug Log", expanded=False):
                        for line in result["debug_log"]:
                            st.code(line, language=None)
                
                # ── Latency caption ───────────────────────────────────────────
                latency_ms = result.get("latency_ms", latency * 1000)
                st.caption(f"⏱️ {latency_ms:.0f} ms | Retrieved {len(chunks)} chunks")
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response})

    # ── PHASE 6: Memory extraction — detect & save user preferences ──────────
    # Extract from user message
    st.session_state.user_memory = extract_memory_from_message(
        role="user",
        content=user_input,
        memory=st.session_state.user_memory,
    )
    # Persist any updated preferences to disk immediately
    save_user_memory(st.session_state.user_memory)
    # Update memory_loaded flag
    st.session_state.memory_loaded = st.session_state.user_memory.user_name is not None

def run_evaluation():
    """Run the full evaluation pipeline."""
    st.session_state.eval_running = True
    
    progress_bar = st.progress(0, text="Starting evaluation...")
    
    try:
        # Step A: Generate test cases
        progress_bar.progress(10, text="Generating test cases with LLM...")
        test_cases = generate_test_cases()
        
        # Step B: Run test suite
        progress_bar.progress(30, text="Running test cases against chatbot...")
        results = run_test_suite(test_cases)
        
        # Step C: Run RAGAS
        progress_bar.progress(60, text="Running RAGAS evaluation...")
        ragas_scores = run_ragas_evaluation(results)
        
        # Step D: Generate report
        progress_bar.progress(80, text="Generating evaluation report...")
        report = generate_report(results, ragas_scores)
        
        progress_bar.progress(100, text="Evaluation complete!")
        st.session_state.eval_report = report
        
    except Exception as e:
        st.error(f"Evaluation failed: {e}")
        st.session_state.eval_report = {"error": str(e)}
    
    st.session_state.eval_running = False

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title(f"🎓 {COLLEGE_SHORT} FAQ Chatbot")
    st.markdown("---")
    
    # Knowledge Base Status
    st.subheader("📊 Knowledge Base")
    if st.session_state.index_ready:
        st.success(f"✅ **Index Live**")
        st.metric("Chunks Indexed", st.session_state.chunk_count)
        st.caption(f"Document: {st.session_state.doc_name}")
    else:
        st.warning("⚠️ Index not initialized")
        if st.button("Initialize Index"):
            initialize_index()
    
    st.markdown("---")
    
    # Retrieval Settings
    st.subheader("⚙️ Retrieval Settings")
    
    top_k = st.slider(
        "Top-K chunks",
        min_value=1,
        max_value=10,
        value=config.TOP_K,
        help="Number of chunks to retrieve per query",
    )
    st.session_state.top_k = top_k
    
    chunk_size = st.number_input(
        "Chunk Size",
        min_value=100,
        max_value=2000,
        value=config.CHUNK_SIZE,
        step=50,
        help="Size of each text chunk",
    )
    
    # Section Filter
    section_filter = st.selectbox(
        "Section Filter",
        options=config.SECTIONS,
        index=0,
        help="Filter retrieval to a specific section",
    )
    
    # Persist settings to config
    config.TOP_K = top_k
    config.CHUNK_SIZE = chunk_size
    
    st.markdown("---")
    
    # Evaluation Section
    st.subheader("🧪 Evaluation")
    if st.button("Run Full Evaluation (20 test cases)", 
                 disabled=st.session_state.eval_running or not st.session_state.index_ready,
                 type="primary"):
        run_evaluation()
    
    if st.session_state.eval_running:
        st.warning("Evaluation in progress... This may take several minutes.")
    
    st.markdown("---")

    # ── Function Calling Panel ────────────────────────────────────────────
    st.subheader("🔧 Function Calling")

    # Registered tools
    from tools import BVRIT_TOOLS
    st.markdown("**Registered Tools:**")
    tool_icons = {"fee_calculator": "💰", "date_checker": "📅", "percentage_calculator": "📊"}
    for t in BVRIT_TOOLS:
        name = t["function"]["name"]
        icon = tool_icons.get(name, "🔧")
        st.success(f"{icon} `{name}` — ✅ Active")

    st.markdown("---")

    # Debug mode toggle
    st.session_state.debug_mode = st.toggle(
        "🐛 Debug Mode",
        value=st.session_state.debug_mode,
        help="Show routing decisions and debug log in chat",
    )

    # Last tool call info
    lr = st.session_state.last_route_result
    if lr:
        st.markdown("**Last Routing Decision:**")
        route = lr.get("route", "—")
        route_badge = {"CONVERSATION": "🗣️", "RAG": "📚", "TOOL_CALL": "🔧"}.get(route, "💬")
        st.info(f"{route_badge} **{route}**")

        if lr.get("tool_name"):
            st.markdown(f"**Last Tool Called:** `{lr['tool_name']}`")
            with st.expander("Arguments", expanded=False):
                st.json(lr.get("tool_args", {}))

        latency = lr.get("latency_ms", 0)
        st.caption(f"⏱️ Latency: {latency:.0f} ms")
    else:
        st.caption("No tool calls yet — ask a calculation question.")

    st.markdown("---")
    # ── PHASE 8: Memory & Personalisation Sidebar Panel ──────────────────────
    st.subheader("🧠 Memory & Personalisation")
    
    mem = st.session_state.get("user_memory", UserMemory())
    
    # Memory status indicators
    turn_count = len(st.session_state.get("messages", [])) // 2
    st.metric("Conversation Turns", turn_count)
    
    session_summary_status = (
        "✅ Summary Active" 
        if st.session_state.get("session_summary") or mem.previous_session_summary 
        else "—"
    )
    st.caption(f"📋 Session Summary: {session_summary_status}")
    
    memory_loaded_status = "✅ Loaded" if st.session_state.get("memory_loaded") else "— Not set"
    st.caption(f"💾 Memory: {memory_loaded_status}")
    
    st.markdown("---")
    
    # User preference display
    st.markdown("**User Preferences:**")
    st.caption(f"👤 Name: {mem.user_name or '—'}")
    st.caption(f"🌐 Language: {mem.preferred_language or 'English'}")
    st.caption(f"🎓 Branch: {mem.branch_interest or '—'}")
    st.caption(f"📝 Detail Level: {mem.answer_detail_level or 'Detailed'}")
    
    st.markdown("---")
    
    # Memory action buttons
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🗑️ Clear Session", help="Clear chat history for this session"):
            st.session_state.messages = []
            st.session_state.session_summary = None
            st.rerun()
    with col_b:
        if st.button("🧹 Clear Memory", help="Delete all stored preferences"):
            delete_user_memory()
            st.session_state.user_memory = UserMemory()
            st.session_state.memory_loaded = False
            st.success("✅ Memory cleared!")
            st.rerun()
    
    if st.button("👁️ Show Memory", help="Display current stored memory"):
        with st.expander("📂 Stored Memory", expanded=True):
            st.json(mem.to_dict())
    
    st.markdown("---")
    st.caption("Built with LangChain + ChromaDB + Streamlit")
    st.caption("Powered by OpenRouter AI")

# ============================================================
# MAIN CONTENT
# ============================================================

# Initialize index on first load
if not st.session_state.index_ready:
    with st.spinner("🔄 Initializing knowledge base..."):
        initialize_index()

# Check if we should show evaluation report or chat
show_eval = st.session_state.eval_report is not None

if show_eval:
    # ============================================================
    # EVALUATION DASHBOARD TAB
    # ============================================================
    tab1, tab2 = st.tabs(["💬 Chat", "📊 Evaluation Dashboard"])
    
    with tab2:
        report = st.session_state.eval_report
        
        if "error" in report:
            st.error(f"Evaluation error: {report['error']}")
        else:
            # Summary Banner
            s = report["summary"]
            pass_rate = s["pass_rate"]
            
            if pass_rate >= 80:
                color = "green"
                icon = "🟢"
            elif pass_rate >= 60:
                color = "orange"
                icon = "🟡"
            else:
                color = "red"
                icon = "🔴"
            
            st.markdown(f"""
            ## {icon} Evaluation Report Summary
            <div style="background-color: {'#d4edda' if pass_rate >= 80 else '#fff3cd'}; 
                        padding: 20px; border-radius: 10px; margin: 10px 0;">
                <h3 style="color: {'#155724' if pass_rate >= 80 else '#856404'};">
                    {s['passed']} Passed  |  {s['failed']} Failed  |  {s['pending']} Pending  |  Pass Rate: {pass_rate}%
                </h3>
                <p>Total test cases: {s['total_test_cases']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Per-Dimension Cards
            st.subheader("📈 Per-Dimension Breakdown")
            
            cols = st.columns(4)
            dims = sorted(report["per_dimension"].items())
            
            for i, (dim, stats) in enumerate(dims):
                with cols[i % 4]:
                    rate = report["dimension_pass_rates"].get(dim, 0)
                    if rate >= 80:
                        badge = "🟢"
                    elif rate >= 60:
                        badge = "🟡"
                    else:
                        badge = "🔴"
                    
                    st.markdown(f"""
                    <div style="border: 1px solid #ddd; border-radius: 10px; padding: 10px; margin: 5px 0;">
                        <h4>{badge} {dim}</h4>
                        <p style="font-size: 24px; font-weight: bold;">{stats['passed']}/{stats['total']}</p>
                        <p>Pass rate: {rate}%</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Weakest Dimension
            w = report["weakest_dimension"]
            st.markdown(f"""
            <div style="background-color: #f8d7da; padding: 15px; border-radius: 10px; margin: 10px 0;">
                <h4 style="color: #721c24;">⚠️ Weakest Dimension: {w['dimension']} ({w['pass_rate']}%)</h4>
                <p><strong>Recommended Fix:</strong> {w['recommended_fix']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Failed Tests Drill-Down
            if report["failed_tests"]:
                st.subheader("❌ Failed Tests")
                for ft in report["failed_tests"]:
                    with st.expander(f"[{ft['id']}] {ft['dimension']} — {ft['question'][:80]}..."):
                        st.markdown(f"**Question:** {ft['question']}")
                        st.markdown(f"**Expected:** {ft['expected']}")
                        st.markdown(f"**Actual:** {ft['actual']}")
                        st.markdown(f"**Reason:** {ft['reason']}")
                        st.markdown(f"**Fix:** {ft['fix']}")
            
            # RAGAS Scores
            st.subheader("📊 RAGAS Metrics")
            ragas = report["ragas_scores"]
            if ragas and "error" not in ragas:
                cols = st.columns(4)
                for i, (metric, score) in enumerate(ragas.items()):
                    if metric != "error":
                        with cols[i % 4]:
                            # Color based on score
                            if score >= 0.8:
                                color = "green"
                            elif score >= 0.6:
                                color = "orange"
                            else:
                                color = "red"
                            st.markdown(f"""
                            <div style="text-align: center; border: 1px solid #ddd; border-radius: 10px; padding: 10px;">
                                <h4>{metric.replace('_', ' ').title()}</h4>
                                <p style="font-size: 32px; font-weight: bold; color: {color};">{score:.2f}</p>
                            </div>
                            """, unsafe_allow_html=True)
                
                # Diagnosis
                if ragas.get("context_precision", 1.0) < 0.7:
                    st.info("💡 **Diagnosis:** Context Precision is lowest — retrieval returns some irrelevant chunks. Consider reducing chunk_size or adding metadata filters.")
                if ragas.get("context_recall", 1.0) < 0.7:
                    st.info("💡 **Diagnosis:** Context Recall is low — retrieval may be missing relevant chunks. Consider increasing top-k or chunk_size.")
            else:
                st.warning(f"RAGAS scores not available: {ragas.get('error', 'Unknown error')}")
    
    with tab1:
        # Chat Interface
        chat_container = st.container()
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        user_input = st.chat_input(f"Ask about {COLLEGE_SHORT} college...")
        if user_input:
            process_chat_message(user_input, section_filter)
            st.rerun()

else:
    # ============================================================
    # CHAT ONLY (no evaluation yet) - with Gallery tab
    # ============================================================
    tab1, tab2 = st.tabs(["💬 Chat", "📸 Photo Gallery"])
    
    with tab1:
        st.title(f"🎓 {COLLEGE_SHORT} FAQ Chatbot")
        st.markdown(f"Ask questions about {COLLEGE_NAME} — admissions, fees, placements, departments, and more!")
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        user_input = st.chat_input(f"Ask about {COLLEGE_SHORT} college...")
        if user_input:
            process_chat_message(user_input, section_filter)
            st.rerun()
        
        # Welcome message if no messages
        if not st.session_state.messages:
            st.info(f"👋 Ask me anything about {COLLEGE_SHORT}! For example:\n- What is the fee for CSE?\n- Tell me about placements\n- What sports facilities are available?\n- How to apply for admission?\n- Show me campus photos")
    
    with tab2:
        # ============================================================
        # PHOTO GALLERY TAB
        # ============================================================
        st.title(f"📸 {COLLEGE_SHORT} Photo Gallery")
        st.markdown(f"Browse through photos of {COLLEGE_NAME}.")
        
        # Category selector
        categories = [
            ("all", "🖼️ All Photos"),
            ("campus", "🏛️ Campus Views"),
            ("events", "🎉 Events & Celebrations"),
            ("placements", "💼 Placements"),
            ("leadership", "👨‍🏫 Leadership"),
            ("students", "👩‍🎓 Student Life"),
            ("awards", "🏆 Awards & Recognition"),
        ]
        
        gallery_filter = st.radio(
            "Select a category:",
            options=[cat[1] for cat in categories],
            horizontal=True,
            label_visibility="collapsed",
        )
        
        # Map display name back to category key
        cat_map = {cat[1]: cat[0] for cat in categories}
        selected_key = cat_map[gallery_filter]
        
        # Get images for the selected category
        if selected_key == "all":
            image_data = get_images_for_query("photos", max_images=100)
        else:
            # Custom query using the category keywords
            cat_keywords = {
                "campus": "campus building view",
                "events": "event celebration fest annual",
                "placements": "placement company recruiter",
                "leadership": "chairman director principal faculty",
                "students": "student girls women hostel classroom",
                "awards": "award recognition naac nirf nba",
            }
            image_data = get_images_for_query(cat_keywords.get(selected_key, selected_key), max_images=100)
        
        if image_data["images"]:
            st.markdown(f"**Showing {image_data['showing']} images** in this category")
            st.divider()
            
            # Display images in a grid
            images = image_data["images"]
            cols_per_row = 3
            for i in range(0, len(images), cols_per_row):
                row_images = images[i:i + cols_per_row]
                cols = st.columns(cols_per_row)
                for j, img in enumerate(row_images):
                    with cols[j]:
                        st.image(
                            img["url"],
                            caption=img["caption"],
                            width='stretch',
                        )
                        # Add a small caption with the image number
                        st.caption(f"Image {i + j + 1} of {len(images)}")
        else:
            st.warning("No images found in this category.")
        
        st.divider()
        st.caption("📸 Images sourced from bvrithyderabad.edu.in")