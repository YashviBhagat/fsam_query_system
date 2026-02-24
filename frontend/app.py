"""
app.py — Streamlit Frontend
============================
The user interface for the FSAM Query System.
Talks to FastAPI backend at http://localhost:8000
"""

import streamlit as st
import requests
import pandas as pd

# ── Configuration ────────────────────────────────────────────
API_URL = "http://localhost:8000"

st.set_page_config(
    page_title = "FSAM Research Assistant",
    page_icon  = "🔬",
    layout     = "wide"
)

# ── Header ───────────────────────────────────────────────────
st.title("🔬 FSAM Research Assistant")
st.markdown("Query **Friction Stir Additive Manufacturing** research papers using natural language.")
st.divider()

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.header("📊 Database Info")

    # Fetch stats from API
    try:
        stats = requests.get(f"{API_URL}/stats").json()
        st.metric("Total Papers",  stats["total_papers"])
        st.metric("Unique Alloys", stats["total_alloys"])
        st.metric("Hardness Data", f"{stats['hardness_count']} papers")
        st.metric("UTS Data",      f"{stats['uts_count']} papers")

        st.subheader("Papers by Process")
        for process, count in stats["processes"].items():
            st.write(f"**{process}:** {count} papers")

    except:
        st.error("Cannot connect to API. Is the server running?")

    st.divider()

    # Alloy selector
    st.subheader("📋 Available Alloys")
    try:
        alloys_data = requests.get(f"{API_URL}/alloys").json()
        alloys      = alloys_data["alloys"]
        selected    = st.selectbox(
            "Quick select an alloy:",
            [""] + alloys
        )
    except:
        selected = ""
        st.error("Could not load alloys")

    st.divider()

    # Example questions
    st.subheader("💡 Example Questions")
    examples = [
        "What is the hardness of AA6061?",
        "Which alloy has the highest UTS?",
        "Compare grain size of AA6061 and AA7075",
        "Show papers with rotation speed above 1000 rpm",
        "What is yield strength of 6xxx series?",
        "What process gives lowest grain size?",
        "What is traverse speed of AA7075 with T6 temper?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state.question = ex


# ── Main Query Area ───────────────────────────────────────────
col1, col2 = st.columns([3, 1])

with col1:
    # Pre-fill from sidebar selection or example button
    default = st.session_state.get("question", "")
    if selected:
        default = f"What are the mechanical properties of {selected}?"

    question = st.text_input(
        "Ask a question about FSAM research:",
        value       = default,
        placeholder = "e.g. What is the hardness of AA6061?",
    )

with col2:
    st.write("")
    st.write("")
    search = st.button("🔍 Search", use_container_width=True, type="primary")

# ── Process Query ─────────────────────────────────────────────
if search and question.strip():

    with st.spinner("Searching research papers..."):
        try:
            response = requests.post(
                f"{API_URL}/query",
                json    = {"question": question},
                timeout = 30
            )
            data = response.json()

        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to API. Make sure the FastAPI server is running.")
            st.code(".venv/bin/uvicorn backend.api.main:app --reload --port 8000")
            st.stop()

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.stop()

    # ── Display Results ──────────────────────────────────────
    if data.get("error"):
        st.error(f"❌ {data['error']}")

    elif data.get("rows", 0) == 0:
        st.warning("No results found. Try rephrasing your question.")

    else:
        # Answer
        st.success("✅ Answer found!")
        st.markdown("### 💬 Answer")
        st.info(data["answer"])

        # Metrics row
        m1, m2, m3 = st.columns(3)
        m1.metric("Papers Found", data["rows"])
        #m2.metric("Question",     question[:30] + "...")
        m3.metric("Status",       "✅ Success")

        st.divider()

        # Raw SQL results as table
        st.markdown("### 📊 Raw Data")

        # Fetch raw table from /sql endpoint
        try:
            sql_response = requests.post(
                f"{API_URL}/sql",
                json    = {"question": question},
                timeout = 30
            ).json()

            if sql_response.get("results"):
                df = pd.DataFrame(
                    sql_response["results"],
                    columns = sql_response["columns"]
                )
                st.dataframe(df, use_container_width=True)

        except:
            st.write("Could not load raw data table.")

        # SQL query used
        with st.expander("🔍 View SQL Query"):
            st.code(data["sql"], language="sql")

elif search and not question.strip():
    st.warning("Please enter a question.")