# """
# app.py — Streamlit Frontend
# ============================
# Full UI for FSAM Query System.
# Connects to FastAPI backend at http://localhost:8000

# FEATURES:
# ──────────
# 1. Ask any question (SQL + RAG via /ask endpoint)
# 2. Upload your own PDF paper (via /upload endpoint)
# 3. See SQL data table + RAG passages
# 4. Sidebar with database stats and example questions
# """

# import streamlit as st
# import requests
# import pandas as pd

# # ── Configuration ─────────────────────────────────────────────
# API_URL = "http://localhost:8000"

# st.set_page_config(
#     page_title = "FSAM Research Assistant",
#     page_icon  = "🔬",
#     layout     = "wide"
# )

# # ── Header ────────────────────────────────────────────────────
# st.title("🔬 FSAM Research Assistant")
# st.markdown("Query **Friction Stir Additive Manufacturing** "
#             "research papers using natural language.")
# st.divider()

# # ── Sidebar ───────────────────────────────────────────────────
# with st.sidebar:
#     #st.header("📊 Database Info")

#     try:
#         stats = requests.get(f"{API_URL}/stats", timeout=5).json()
#         # st.metric("Total Papers",  stats["total_papers"])
#         # st.metric("Unique Alloys", stats["total_alloys"])
#         # st.metric("Hardness Data", f"{stats['hardness_count']} papers")
#         # st.metric("UTS Data",      f"{stats['uts_count']} papers")

#         # st.subheader("Papers by Process")
#         # for process, count in stats["processes"].items():
#         #     st.write(f"**{process}:** {count} papers")

#     except:
#         st.error("Cannot connect to API. Is the server running?")

#     st.divider()

#     # ── PDF Upload ───────────────────────────────────────────
#     st.subheader("📄 Upload Your Paper")
#     st.caption("Upload a PDF to search it alongside the database")

#     uploaded_file = st.file_uploader(
#         "Choose a PDF file",
#         type = ["pdf"],
#         help = "Your paper will be processed and added to the search index"
#     )

#     if uploaded_file is not None:
#         # Show upload button only when file is selected
#         if st.button("📤 Process & Add to Search",
#                      use_container_width=True,
#                      type="primary"):

#             with st.spinner("Processing PDF..."):
#                 try:
#                     # Send PDF bytes to FastAPI /upload endpoint
#                     response = requests.post(
#                         f"{API_URL}/upload",
#                         files   = {"file": (
#                             uploaded_file.name,
#                             uploaded_file.getvalue(),
#                             "application/pdf"
#                         )},
#                         timeout = 60
#                     )
#                     result = response.json()

#                     if response.status_code == 200:
#                         st.success(
#                             f"✅ Added {result['chunks_added']} "
#                             f"chunks from {result['filename']}"
#                         )
#                         # Remember that user has uploaded a paper
#                         st.session_state.search_user = True
#                         st.session_state.uploaded_paper = result["filename"]
#                     else:
#                         st.error(f"❌ Upload failed: {result.get('detail')}")

#                 except Exception as e:
#                     st.error(f"❌ Error: {str(e)}")

#     # Show if a paper is currently loaded
#     if st.session_state.get("search_user"):
#         st.success(
#             f"📄 Searching: {st.session_state.get('uploaded_paper', 'uploaded paper')}"
#         )
#         if st.button("🗑 Remove uploaded paper"):
#             st.session_state.search_user   = False
#             st.session_state.uploaded_paper = None
#             st.rerun()

#     st.divider()

#     # ── Alloy Selector ───────────────────────────────────────
#     st.subheader("📋 Available Alloys")
#     try:
#         alloys_data = requests.get(f"{API_URL}/alloys", timeout=5).json()
#         alloys      = alloys_data["alloys"]
#         selected    = st.selectbox("Quick select:", [""] + alloys)
#     except:
#         selected = ""
#         st.error("Could not load alloys")

#     st.divider()

#     # ── Example Questions ────────────────────────────────────
#     st.subheader("💡 Example Questions")

#     st.caption("📊 Data questions (SQL):")
#     sql_examples = [
#         "What is the hardness of AA6061?",
#         "Which alloy has the highest UTS?",
#         "Compare grain size of AA6061 and AA7075",
#         "Show papers with rotation speed above 1000 rpm",
#     ]
#     for ex in sql_examples:
#         if st.button(ex, use_container_width=True, key=f"sql_{ex}"):
#             st.session_state.question = ex

#     st.caption("📖 Explanation questions (RAG):")
#     rag_examples = [
#         "Why does grain size decrease in AFSD?",
#         "How does rotation speed affect microstructure?",
#         "Explain the recrystallization mechanism in FSAM",
#         "What happens when traverse velocity increases?",
#     ]
#     for ex in rag_examples:
#         if st.button(ex, use_container_width=True, key=f"rag_{ex}"):
#             st.session_state.question = ex


# # ── Main Query Area ────────────────────────────────────────────
# col1, col2 = st.columns([3, 1])

# with col1:
#     default = st.session_state.get("question", "")
#     if selected:
#         default = f"What are the mechanical properties of {selected}?"

#     question = st.text_input(
#         "Ask a question about FSAM research:",
#         value       = default,
#         placeholder = "e.g. What is the hardness of AA6061? "
#                       "or Why does grain size decrease in AFSD?",
#     )

# with col2:
#     st.write("")
#     st.write("")
#     search = st.button(
#         "🔍 Search",
#         use_container_width = True,
#         type                = "primary"
#     )

# # ── Process Query ──────────────────────────────────────────────
# if search and question.strip():

#     with st.spinner("Searching research papers..."):
#         try:
#             response = requests.post(
#                 f"{API_URL}/ask",
#                 json    = {
#                     "question":    question,
#                     "search_user": st.session_state.get("search_user", False)
#                 },
#                 timeout = 60
#             )
#             data = response.json()

#         except requests.exceptions.ConnectionError:
#             st.error("❌ Cannot connect to API. "
#                      "Make sure the FastAPI server is running.")
#             st.code(".venv/bin/uvicorn backend.api.main:app "
#                     "--reload --port 8000")
#             st.stop()

#         except Exception as e:
#             st.error(f"❌ Error: {str(e)}")
#             st.stop()

#     # ── Show Route Badge ────────────────────────────────────
#     route = data.get("route", "")
#     if route == "sql":
#         st.info("🗄 **Query type: Database Search** (SQL)")
#     elif route == "rag":
#         st.info("📖 **Query type: Research Paper Search** (RAG)")
#     elif route == "both":
#         st.info("🔀 **Query type: Combined** (SQL + RAG)")

#     # ── Display Results ─────────────────────────────────────
#     if data.get("error") and not data.get("final_answer"):
#         st.error(f"❌ {data['error']}")

#     else:
#         st.success("✅ Answer found!")

#         # ── SQL Answer ───────────────────────────────────────
#         if data.get("sql_answer"):
#             st.markdown("### 📊 Data Answer")
#             st.info(data["sql_answer"])

#             # Metrics row
#             m1, m2 = st.columns(2)
#             m1.metric("Papers Found", data.get("rows", 0))
#             m2.metric("Route", route.upper())

#         # ── RAG Answer ───────────────────────────────────────
#         if data.get("rag_answer"):
#             st.markdown("### 📖 Research Explanation")
#             st.success(data["rag_answer"])

#         # ── If only final_answer (no split) ──────────────────
#         if not data.get("sql_answer") and not data.get("rag_answer"):
#             if data.get("final_answer"):
#                 st.markdown("### 💬 Answer")
#                 st.info(data["final_answer"])

#         st.divider()

#         # ── Raw Data Table ───────────────────────────────────
#         if data.get("rows", 0) > 0:
#             st.markdown("### 📋 Raw Data Table")
#             try:
#                 sql_response = requests.post(
#                     f"{API_URL}/sql",
#                     json    = {"question": question},
#                     timeout = 30
#                 ).json()

#                 if sql_response.get("results"):
#                     df = pd.DataFrame(
#                         sql_response["results"],
#                         columns = sql_response["columns"]
#                     )
#                     st.dataframe(df, use_container_width=True)

#             except:
#                 st.write("Could not load raw data table.")

#         # ── RAG Passages ─────────────────────────────────────
#         if data.get("passages"):
#             with st.expander(
#                 f"📚 View Source Passages ({len(data['passages'])} found)"
#             ):
#                 for i, passage in enumerate(data["passages"], 1):
#                     st.markdown(
#                         f"**[{i}] {passage['paper_id']}** "
#                         f"— relevance: {round(1 - passage['distance'], 2)}"
#                     )
#                     st.caption(passage["text"][:400] + "...")
#                     st.divider()

#         # ── SQL Query Used ───────────────────────────────────
#         if data.get("sql"):
#             with st.expander("🔍 View SQL Query"):
#                 st.code(data["sql"], language="sql")

# elif search and not question.strip():
#     st.warning("Please enter a question.")

# """
# app.py — Streamlit Frontend (Redesigned)
# =========================================
# Clean UI with PDF upload on main page.
# Only shows information useful to the user.
# """

# import streamlit as st
# import requests
# import pandas as pd

# API_URL = "http://localhost:8000"

# st.set_page_config(
#     page_title = "FSAM Research Assistant",
#     page_icon  = "🔬",
#     layout     = "wide"
# )

# # ── Sidebar — minimal, only useful info ───────────────────────
# with st.sidebar:
#     st.header("📊 Database")

#     try:
#         stats = requests.get(f"{API_URL}/stats", timeout=5).json()
#         col1, col2 = st.columns(2)
#         col1.metric("Papers", stats["total_papers"])
#         col2.metric("Alloys", stats["total_alloys"])
#     except:
#         st.error("API not running")

#     st.divider()

#     st.subheader("💡 Try These")

#     st.caption("Data questions:")
#     sql_examples = [
#         "What is the hardness of AA6061?",
#         "Which alloy has the highest UTS?",
#         "Compare grain size of AA6061 and AA7075",
#     ]
#     for ex in sql_examples:
#         if st.button(ex, use_container_width=True, key=f"s_{ex}"):
#             st.session_state.question = ex

#     st.caption("Explanation questions:")
#     rag_examples = [
#         "Why does grain size decrease in AFSD?",
#         "How does rotation speed affect microstructure?",
#         "Explain recrystallization in FSAM",
#     ]
#     for ex in rag_examples:
#         if st.button(ex, use_container_width=True, key=f"r_{ex}"):
#             st.session_state.question = ex


# # ── Main Page ─────────────────────────────────────────────────
# st.title("🔬 FSAM Research Assistant")
# st.caption("Ask questions about Friction Stir Additive Manufacturing research papers.")
# st.divider()

# # ── Two Column Layout: Upload + Search ────────────────────────
# left, right = st.columns([1, 2])

# # ── LEFT: PDF Upload ──────────────────────────────────────────
# with left:
#     st.subheader("📄 Upload Paper")
#     st.caption("Add your own PDF to search alongside the database.")

#     uploaded_file = st.file_uploader(
#         "Choose PDF",
#         type             = ["pdf"],
#         label_visibility = "collapsed"
#     )

#     if uploaded_file:
#         if st.button("Add to Search", use_container_width=True, type="primary"):
#             with st.spinner("Processing..."):
#                 try:
#                     response = requests.post(
#                         f"{API_URL}/upload",
#                         files   = {"file": (
#                             uploaded_file.name,
#                             uploaded_file.getvalue(),
#                             "application/pdf"
#                         )},
#                         timeout = 60
#                     )
#                     result = response.json()

#                     if response.status_code == 200:
#                         st.success(f"✅ {result['chunks_added']} sections added")
#                         st.session_state.search_user    = True
#                         st.session_state.uploaded_paper = uploaded_file.name
#                     else:
#                         st.error("Upload failed")

#                 except Exception as e:
#                     st.error(f"Error: {str(e)}")

#     # Show active uploaded paper
#     if st.session_state.get("search_user"):
#         name         = st.session_state.get("uploaded_paper", "")
#         display_name = name[:30] + "..." if len(name) > 30 else name
#         st.info(f"📄 Active: {display_name}")
#         if st.button("Remove", use_container_width=True):
#             st.session_state.search_user    = False
#             st.session_state.uploaded_paper = None
#             st.rerun()


# # ── RIGHT: Question Input ─────────────────────────────────────
# with right:
#     st.subheader("💬 Ask a Question")

#     default  = st.session_state.get("question", "")
#     question = st.text_input(
#         "Question",
#         value            = default,
#         placeholder      = "e.g. What is the hardness of AA6061?",
#         label_visibility = "collapsed"
#     )

#     search = st.button(
#         "🔍 Search",
#         use_container_width = True,
#         type                = "primary"
#     )


# st.divider()

# # ── Results ────────────────────────────────────────────────────
# if search and question.strip():

#     with st.spinner("Searching..."):
#         try:
#             response = requests.post(
#                 f"{API_URL}/ask",
#                 json    = {
#                     "question":    question,
#                     "search_user": st.session_state.get("search_user", False)
#                 },
#                 timeout = 60
#             )
#             data = response.json()

#         except requests.exceptions.ConnectionError:
#             st.error("Cannot connect to API. Is the FastAPI server running?")
#             st.stop()
#         except Exception as e:
#             st.error(f"Error: {str(e)}")
#             st.stop()

#     # ── Route Badge ───────────────────────────────────────────
#     route = data.get("route", "")
#     route_labels = {
#         "sql":  "📊 Database search",
#         "rag":  "📖 Research paper search",
#         "both": "🔀 Database + Research papers"
#     }
#     st.caption(route_labels.get(route, ""))

#     # ── Answers ───────────────────────────────────────────────
#     if data.get("sql_answer"):
#         st.markdown("### 📊 Data")
#         st.info(data["sql_answer"])

#     if data.get("rag_answer"):
#         st.markdown("### 📖 Explanation")
#         st.success(data["rag_answer"])

#     if not data.get("sql_answer") and not data.get("rag_answer"):
#         if data.get("final_answer"):
#             st.info(data["final_answer"])

#     # ── Raw Data Table ────────────────────────────────────────
#     if data.get("rows", 0) > 0:
#         st.markdown("### 📋 Raw Data")
#         try:
#             sql_resp = requests.post(
#                 f"{API_URL}/sql",
#                 json    = {"question": question},
#                 timeout = 30
#             ).json()

#             if sql_resp.get("results"):
#                 df = pd.DataFrame(
#                     sql_resp["results"],
#                     columns = sql_resp["columns"]
#                 )
#                 st.dataframe(df, use_container_width=True)
#         except:
#             pass

#     # ── Source Passages ───────────────────────────────────────
#     if data.get("passages"):
#         with st.expander(f"📚 Sources ({len(data['passages'])} passages)"):
#             for i, p in enumerate(data["passages"], 1):
#                 source = p.get("source", "fsam")
#                 if source == "user":
#                     label = "📄 Your uploaded paper"
#                 else:
#                     label = f"🗄 {p['paper_id']}"

#                 relevance = round(1 - p["distance"], 2)
#                 st.markdown(f"**[{i}] {label}** — relevance: {relevance}")
#                 st.caption(p["text"][:300] + "...")
#                 if i < len(data["passages"]):
#                     st.divider()

#     # ── SQL Query ─────────────────────────────────────────────
#     if data.get("sql"):
#         with st.expander("🔍 SQL Query"):
#             st.code(data["sql"], language="sql")

# elif search and not question.strip():
#     st.warning("Please enter a question.")

"""
app.py — Streamlit Frontend (Clean Redesign)
=============================================
Clean research-grade UI.
Search scope selector only appears after PDF upload.
"""

import streamlit as st
import requests
import pandas as pd

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title = "FSAM Research Assistant",
    page_icon  = "🔬",
    layout     = "wide"
)

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    /* Import clean research font */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    /* Global font */
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* Hide Streamlit default header */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Main container */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Title styling */
    h1 {
        font-size: 2rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.5px;
        color: #F0F4F8 !important;
    }

    /* Section headers */
    h3 {
        font-size: 1rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94A3B8 !important;
        margin-top: 1.5rem !important;
    }

    /* Answer boxes */
    .stAlert {
        border-radius: 8px;
        border-left: 3px solid;
    }

    /* Metric labels */
    [data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #64748B !important;
    }

    /* Metric values */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 600 !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 6px;
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 500;
        letter-spacing: 0.3px;
        transition: all 0.15s ease;
    }

    /* Search button */
    .stButton > button[kind="primary"] {
        background: #2563EB;
        border: none;
        font-size: 0.95rem;
    }

    .stButton > button[kind="primary"]:hover {
        background: #1D4ED8;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }

    /* Text input */
    .stTextInput > div > div > input {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 1rem;
        border-radius: 6px;
        padding: 0.6rem 1rem;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        border-right: 1px solid #1E293B;
    }

    /* Code blocks */
    code {
        font-family: 'IBM Plex Mono', monospace !important;
    }

    /* Divider */
    hr {
        border-color: #1E293B;
        margin: 1.5rem 0;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        border-radius: 8px;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: #94A3B8 !important;
    }

    /* Radio buttons */
    .stRadio > div {
        gap: 0.5rem;
    }

    /* Caption */
    .stCaption {
        color: #64748B !important;
        font-size: 0.8rem !important;
    }

    /* Upload area card */
    .upload-card {
        background: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 1.5rem;
    }

    /* Active paper badge */
    .paper-badge {
        background: #052E16;
        border: 1px solid #166534;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
        font-size: 0.8rem;
        color: #86EFAC;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Database")

    try:
        stats = requests.get(f"{API_URL}/stats", timeout=5).json()
        c1, c2 = st.columns(2)
        c1.metric("Papers", stats["total_papers"])
        c2.metric("Alloys", stats["total_alloys"])
    except:
        st.error("⚠ API offline")

    st.divider()

    st.markdown("### Try These")

    st.caption("DATA QUESTIONS")
    sql_examples = [
        "What is the hardness of AA6061?",
        "Which alloy has highest UTS?",
        "Compare AA6061 and AA7075 grain size",
        "Papers with rotation speed > 1000 rpm",
    ]
    for ex in sql_examples:
        if st.button(ex, use_container_width=True, key=f"s_{ex}"):
            st.session_state.question = ex

    st.caption("EXPLANATION QUESTIONS")
    rag_examples = [
        "Why does grain size decrease in AFSD?",
        "How does rotation speed affect microstructure?",
        "Explain recrystallization in FSAM",
        "What causes hardness variation in AA7075?",
    ]
    for ex in rag_examples:
        if st.button(ex, use_container_width=True, key=f"r_{ex}"):
            st.session_state.question = ex


# ── Main Page ─────────────────────────────────────────────────
st.title("🔬 FSAM Research Assistant")
st.caption("Natural language search across Friction Stir Additive Manufacturing research papers.")
st.divider()

# ── TOP SECTION: Upload + Question ────────────────────────────
upload_col, question_col = st.columns([1, 2], gap="large")


# ── UPLOAD COLUMN ─────────────────────────────────────────────
with upload_col:
    st.markdown("### Upload Paper")
    st.caption("Add a PDF to search alongside the built-in database.")

    uploaded_file = st.file_uploader(
        "PDF only",
        type             = ["pdf"],
        label_visibility = "collapsed"
    )

    if uploaded_file:
        # Show file info
        size_mb = len(uploaded_file.getvalue()) / 1_000_000
        st.caption(f"📎 {uploaded_file.name[:35]}{'...' if len(uploaded_file.name) > 35 else ''} · {size_mb:.1f} MB")

        if st.button("⊕ Add to Search Index",
                     use_container_width=True,
                     type="primary"):
            with st.spinner("Processing PDF..."):
                try:
                    resp = requests.post(
                        f"{API_URL}/upload",
                        files   = {"file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            "application/pdf"
                        )},
                        timeout = 120
                    )
                    result = resp.json()

                    if resp.status_code == 200:
                        st.success(
                            f"✓ {result['chunks_added']} sections indexed"
                        )
                        st.session_state.search_user    = True
                        st.session_state.uploaded_paper = uploaded_file.name
                        st.rerun()
                    else:
                        st.error(f"Failed: {result.get('detail', 'unknown error')}")

                except Exception as e:
                    st.error(f"Error: {e}")

    # Show active paper badge + remove
    if st.session_state.get("search_user"):
        name = st.session_state.get("uploaded_paper", "")
        st.markdown(
            f'<div class="paper-badge">📄 '
            f'{name[:28] + "..." if len(name) > 28 else name}'
            f' · Active</div>',
            unsafe_allow_html=True
        )
        st.write("")
        if st.button("✕ Remove paper", use_container_width=True):
            st.session_state.search_user    = False
            st.session_state.uploaded_paper = None
            st.rerun()


# ── QUESTION COLUMN ────────────────────────────────────────────
with question_col:
    st.markdown("### Ask a Question")

    default  = st.session_state.get("question", "")
    question = st.text_input(
        "question_input",
        value            = default,
        placeholder      = "What is the hardness of AA6061?  ·  Why does grain size decrease in AFSD?",
        label_visibility = "collapsed"
    )

    # ── Search Scope — ONLY shows after upload ────────────────
    search_user  = False
    search_scope = "database"

    if st.session_state.get("search_user"):
        st.caption("SEARCH IN")
        scope = st.radio(
            "scope",
            options          = [
                "Database only",
                "Uploaded paper only",
                "Both database + uploaded paper"
            ],
            index            = 2,       # default: both
            label_visibility = "collapsed",
            horizontal       = False
        )

        if scope == "Uploaded paper only":
            search_scope = "user_only"
            search_user  = True
        elif scope == "Both database + uploaded paper":
            search_scope = "both"
            search_user  = True
        else:
            search_scope = "database"
            search_user  = False

    search = st.button(
        "Search →",
        use_container_width = True,
        type                = "primary"
    )


st.divider()


# ── RESULTS ────────────────────────────────────────────────────
if search and question.strip():

    with st.spinner(""):
        try:
            # Build request based on scope
            if search_scope == "user_only":
                # Search only uploaded paper
                # We use /ask with search_user=True
                # and pass a flag in question to indicate user_only
                resp = requests.post(
                    f"{API_URL}/ask",
                    json    = {
                        "question":    question,
                        "search_user": True
                    },
                    timeout = 90
                )
            else:
                resp = requests.post(
                    f"{API_URL}/ask",
                    json    = {
                        "question":    question,
                        "search_user": search_user
                    },
                    timeout = 90
                )

            data = resp.json()

        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to API. Make sure FastAPI is running on port 8000.")
            st.stop()
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    # ── Route label ──────────────────────────────────────────
    route = data.get("route", "")
    route_map = {
        "sql":  "📊  Database search",
        "rag":  "📖  Research paper search",
        "both": "🔀  Database + Research papers"
    }
    if route in route_map:
        st.caption(route_map[route])

    # ── Data Answer ───────────────────────────────────────────
    if data.get("sql_answer"):
        st.markdown("### 📊 Data")
        st.info(data["sql_answer"])

    # ── Explanation Answer ────────────────────────────────────
    if data.get("rag_answer"):
        st.markdown("### 📖 Explanation")
        st.success(data["rag_answer"])

    # ── Fallback ──────────────────────────────────────────────
    if not data.get("sql_answer") and not data.get("rag_answer"):
        if data.get("final_answer"):
            st.info(data["final_answer"])

    # ── Raw Data Table ────────────────────────────────────────
    if data.get("rows", 0) > 0:
        st.markdown("### 📋 Raw Data")
        try:
            sql_resp = requests.post(
                f"{API_URL}/sql",
                json    = {"question": question},
                timeout = 30
            ).json()

            if sql_resp.get("results"):
                df = pd.DataFrame(
                    sql_resp["results"],
                    columns = sql_resp["columns"]
                )
                st.dataframe(df, use_container_width=True)
        except:
            pass

    # ── Source Passages ───────────────────────────────────────
    if data.get("passages"):
        with st.expander(
            f"View sources  ·  {len(data['passages'])} passages found"
        ):
            for i, p in enumerate(data["passages"], 1):
                source    = p.get("source", "fsam")
                relevance = round(1 - p["distance"], 2)

                if source == "user":
                    label      = "📄 Your paper"
                    badge_color = "#052E16"
                    text_color  = "#86EFAC"
                else:
                    label      = f"🗄 {p['paper_id']}"
                    badge_color = "#0F172A"
                    text_color  = "#94A3B8"

                st.markdown(
                    f'<span style="background:{badge_color};color:{text_color};'
                    f'padding:2px 8px;border-radius:4px;font-size:0.8rem;">'
                    f'{label}</span>'
                    f' &nbsp; relevance: **{relevance}**',
                    unsafe_allow_html=True
                )
                st.caption(p["text"][:350] + "...")

                if i < len(data["passages"]):
                    st.divider()

    # ── SQL Used ──────────────────────────────────────────────
    if data.get("sql"):
        with st.expander("SQL query used"):
            st.code(data["sql"], language="sql")

elif search and not question.strip():
    st.warning("Please enter a question.")