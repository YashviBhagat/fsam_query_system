"""
app.py — Streamlit Frontend (Redesigned)
=========================================
Clean UI with:
- Upload paper → auto activates (no dropdown needed)
- Two buttons: Search This Paper / Search Database
- Green badge showing active paper
- Clear paper button
- Token limit error detection
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
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

    #MainMenu {visibility: hidden;}
    footer     {visibility: hidden;}
    .block-container { padding-top: 1.5rem; }

    h1 {
        font-size: 1.8rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.5px;
    }

    [data-testid="stSidebar"] { border-right: 1px solid #1E293B; }

    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 600 !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #64748B !important;
    }

    section[data-testid="stSidebar"] .stButton > button {
        background: transparent;
        border: 1px solid #1E293B;
        border-radius: 6px;
        color: #94A3B8;
        font-size: 0.78rem;
        text-align: left;
        padding: 0.4rem 0.6rem;
        transition: all 0.15s ease;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        background: #1E293B;
        color: #F0F4F8;
        border-color: #334155;
    }

    .stButton > button[kind="primary"] {
        background: #2563EB;
        border: none;
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.15s ease;
    }

    .stButton > button[kind="primary"]:hover {
        background: #1D4ED8;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(37,99,235,0.3);
    }

    hr { border-color: #1E293B; margin: 0.75rem 0; }

    .paper-badge {
        background: #052E16;
        border: 1px solid #166534;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
        font-size: 0.82rem;
        color: #86EFAC;
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
    }

    .history-item {
        background: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
        margin-bottom: 0.4rem;
    }

    .history-filename {
        font-size: 0.8rem;
        font-weight: 500;
        color: #E2E8F0;
    }

    .history-meta {
        font-size: 0.7rem;
        color: #64748B;
        margin-top: 2px;
    }

    .stCaption { color: #64748B !important; font-size: 0.75rem !important; }
    code { font-family: 'IBM Plex Mono', monospace !important; }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────
def load_history():
    try:
        resp = requests.get(f"{API_URL}/history", timeout=5)
        return resp.json().get("history", [])
    except:
        return []


def is_token_limit_error(text: str) -> bool:
    phrases = [
        "rate limit", "rate_limit", "token",
        "quota", "exceeded", "429",
        "too many requests", "limit reached",
        "tokens per day", "tokens per minute"
    ]
    return any(p in str(text).lower() for p in phrases)


def show_token_error():
    st.error(
        "⚠️ **Daily Token Limit Reached**\n\n"
        "The Groq API free tier allows 100,000 tokens per day. "
        "This limit has been reached for today.\n\n"
        "**What you can do:**\n"
        "- Wait until midnight UTC for the limit to reset\n"
        "- Upgrade to Groq Dev tier (~$3/month)\n"
        "- Ask shorter or simpler questions to use fewer tokens"
    )


# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:

    # ── Stats ────────────────────────────────────────────────
    st.markdown("### Database")
    try:
        stats = requests.get(f"{API_URL}/stats", timeout=5).json()
        c1, c2 = st.columns(2)
        c1.metric("Papers", stats["total_papers"])
        c2.metric("Alloys", stats["total_alloys"])
        st.caption("✅ API Online")
    except:
        st.error("⚠ API offline")

    st.divider()

    # ── Upload History ───────────────────────────────────────
    st.markdown("### Upload History")
    history = load_history()

    if not history:
        st.caption("No papers uploaded yet.")
    else:
        for record in history:
            name    = record["filename"]
            display = name[:28] + "..." if len(name) > 28 else name
            meta    = (f"{record['uploaded_at']} · "
                       f"{record['chunks_added']} sections · "
                       f"{record['file_size_mb']} MB")

            col_name, col_del = st.columns([4, 1])
            with col_name:
                st.markdown(
                    f'<div class="history-item">'
                    f'<div class="history-filename">📄 {display}</div>'
                    f'<div class="history-meta">{meta}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with col_del:
                st.write("")
                if st.button("✕", key=f"del_{record['id']}",
                             help="Remove from history"):
                    requests.delete(
                        f"{API_URL}/history/{record['id']}",
                        timeout=5
                    )
                    if (st.session_state.get("active_paper_id") ==
                            record.get("paper_id")):
                        st.session_state.paper_uploaded    = False
                        st.session_state.active_paper_id   = None
                        st.session_state.active_paper_name = None
                    st.rerun()

    st.divider()

    # ── Example Questions ────────────────────────────────────
    st.markdown("### Try These")

    st.caption("DATA QUESTIONS")
    for ex in [
        "What is the hardness of AA6061?",
        "Which alloy has highest UTS?",
        "Compare AA6061 and AA7075 grain size",
        "Papers with rotation speed > 1000 rpm",
    ]:
        if st.button(ex, use_container_width=True, key=f"s_{ex}"):
            st.session_state.question = ex

    st.caption("EXPLANATION QUESTIONS")
    for ex in [
        "Why does grain size decrease in AFSD?",
        "How does rotation speed affect microstructure?",
        "Explain recrystallization in FSAM",
        "What causes hardness variation in AA7075?",
    ]:
        if st.button(ex, use_container_width=True, key=f"r_{ex}"):
            st.session_state.question = ex


# ── MAIN PAGE ─────────────────────────────────────────────────
st.title("🔬 FSAM Research Assistant")
st.caption("Natural language search across Friction Stir Additive Manufacturing research papers.")
st.divider()

# ── TOP SECTION: Upload + Question ────────────────────────────
upload_col, question_col = st.columns([1, 2], gap="large")


# ── UPLOAD COLUMN ─────────────────────────────────────────────
with upload_col:
    st.markdown("#### 📄 Upload Paper")
    st.caption("Add a PDF to search alongside the database.")

    uploaded_file = st.file_uploader(
        "PDF",
        type             = ["pdf"],
        label_visibility = "collapsed"
    )

    if uploaded_file:
        size_mb    = len(uploaded_file.getvalue()) / 1_000_000
        short_name = (uploaded_file.name[:30] + "..."
                      if len(uploaded_file.name) > 30
                      else uploaded_file.name)
        st.caption(f"📎 {short_name} · {size_mb:.1f} MB")

        if st.button("⊕ Add to Search",
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
                        result = resp.json()

                        # Store paper info in session state
                        st.session_state.paper_uploaded    = True
                        st.session_state.active_paper_id   = result.get("paper_id")
                        st.session_state.active_paper_name = uploaded_file.name

                        st.success(
                            f"✓ {result['chunks_added']} sections indexed"
                            f" | paper_id: {result.get('paper_id')}"  # ← show paper_id
                        )
                        st.rerun()
                    else:
                        st.error(f"Failed: {result.get('detail')}")

                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Active Paper Green Badge ───────────────────────────
    # ── Active Paper Green Badge ───────────────────────────
    if st.session_state.get("paper_uploaded"):
        name    = st.session_state.get("active_paper_name", "")
        display = name[:38] + "..." if len(name) > 38 else name
        st.markdown(
            f'<div class="paper-badge">'
            f'📄 <strong>Active paper:</strong><br>{display}'
            f'</div>',
            unsafe_allow_html=True
        )

        # ── DEBUG LINE — shows paper_id on screen ─────────
        st.caption(
            f"🔑 paper_id: {st.session_state.get('active_paper_id')}"
        )

        if st.button("✕ Remove paper",
                     use_container_width=True):
            st.session_state.paper_uploaded    = False
            st.session_state.active_paper_id   = None
            st.session_state.active_paper_name = None
            st.rerun()


# ── QUESTION COLUMN ────────────────────────────────────────────
with question_col:
    st.markdown("#### 💬 Ask a Question")

    default  = st.session_state.get("question", "")
    question = st.text_input(
        "question",
        value            = default,
        placeholder      = "e.g. What is the hardness of AA6061?",
        label_visibility = "collapsed"
    )

    paper_active = st.session_state.get("paper_uploaded", False)

    if paper_active:
        # Show which paper is active
        name = st.session_state.get("active_paper_name", "")
        short = name[:45] + "..." if len(name) > 45 else name
        st.caption(f"📄 Active: **{short}**")

        # Two buttons side by side
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            search_paper = st.button(
                "📄 Search This Paper",
                use_container_width = True,
                type                = "primary",
                key                 = "btn_paper"
            )
        with btn_col2:
            search_db = st.button(
                "🗄 Search Database",
                use_container_width = True,
                key                 = "btn_db"
            )
    else:
        # No paper — single database button
        search_paper = False
        search_db    = st.button(
            "🔍 Search Database",
            use_container_width = True,
            type                = "primary",
            key                 = "btn_db_only"
        )


st.divider()


# ── RESULTS ────────────────────────────────────────────────────
search_triggered = search_paper or search_db

if search_triggered and question.strip():

    # Build payload based on which button was clicked
    if search_paper:
        st.write("DEBUG paper_id:", st.session_state.get("active_paper_id"))
        payload      = {
            "question":      question,
            "search_user":   True,
            "search_fsam":   False,
            "user_paper_id": st.session_state.get("active_paper_id")
        }
        search_label = "📄 Searching uploaded paper..."
    else:
        payload      = {
            "question":    question,
            "search_user": False,
            "search_fsam": True,
        }
        search_label = "🗄 Searching database..."

    with st.spinner(search_label):
        try:
            resp = requests.post(
                f"{API_URL}/ask",
                json    = payload,
                timeout = 90
            )

            # Token limit check on HTTP level
            if resp.status_code == 429 or is_token_limit_error(resp.text):
                show_token_error()
                st.stop()

            data = resp.json()

            # Token limit check inside response body
            if is_token_limit_error(str(data.get("final_answer", ""))) or \
               is_token_limit_error(str(data.get("rag_answer", ""))) or \
               is_token_limit_error(str(data.get("error", ""))):
                show_token_error()
                st.stop()

        except requests.exceptions.ConnectionError:
            st.error(
                "Cannot connect to API. "
                "Is FastAPI running on port 8000?"
            )
            st.stop()
        except Exception as e:
            if is_token_limit_error(str(e)):
                show_token_error()
            else:
                st.error(f"Error: {e}")
            st.stop()

    # ── Source badge ─────────────────────────────────────────
    if search_paper:
        name = st.session_state.get("active_paper_name", "uploaded paper")
        st.caption(f"Results from: 📄 {name}")
    else:
        st.caption("Results from: 🗄 FSAM Research Database (57 papers)")

    # ── Route label ──────────────────────────────────────────
    route     = data.get("route", "")
    route_map = {
        "sql":  "📊 Database search",
        "rag":  "📖 Research paper search",
        "both": "🔀 Database + Research papers"
    }
    if route in route_map:
        st.caption(route_map[route])

    # ── SQL Answer ────────────────────────────────────────────
    if data.get("sql_answer"):
        st.markdown("### 📊 Data")
        st.info(data["sql_answer"])

    # ── RAG Answer ────────────────────────────────────────────
    if data.get("rag_answer"):
        st.markdown("### 📖 Explanation")
        st.success(data["rag_answer"])

    # ── Fallback ──────────────────────────────────────────────
    if not data.get("sql_answer") and not data.get("rag_answer"):
        if data.get("final_answer"):
            st.info(data["final_answer"])

    # ── General error ─────────────────────────────────────────
    if data.get("error") and not data.get("final_answer"):
        st.error(f"Error: {data['error']}")

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
            f"📚 Sources — {len(data['passages'])} passages"
        ):
            for i, p in enumerate(data["passages"], 1):
                source    = p.get("source", "fsam")
                relevance = round(1 - p["distance"], 2)

                if source == "user":
                    label = "📄 Your paper"
                    color = "#86EFAC"
                else:
                    label = f"🗄 {p['paper_id']}"
                    color = "#94A3B8"

                st.markdown(
                    f'<span style="color:{color};font-weight:500;">'
                    f'{label}</span>'
                    f' &nbsp;·&nbsp; relevance: {relevance}',
                    unsafe_allow_html=True
                )
                st.caption(p["text"][:300] + "...")
                if i < len(data["passages"]):
                    st.divider()

    # ── SQL Query ─────────────────────────────────────────────
    if data.get("sql"):
        with st.expander("🔍 SQL query used"):
            st.code(data["sql"], language="sql")

elif search_triggered and not question.strip():
    st.warning("Please enter a question.")