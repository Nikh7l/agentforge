"""AgentForge Dashboard — Streamlit UI for code review visualization."""

from __future__ import annotations

import time

import httpx
import streamlit as st

# ── Page config ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AgentForge",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ──────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api"

SEVERITY_COLORS = {
    "critical": "#FF4444",
    "warning": "#FFAA00",
    "info": "#4488FF",
}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
}


# ── Custom CSS ─────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    /* Dark theme adjustments */
    .score-box {
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 1rem;
    }
    .score-high { background: linear-gradient(135deg, #0d4d0d, #1a8a1a); color: #4dff4d; }
    .score-mid { background: linear-gradient(135deg, #4d4d0d, #8a8a1a); color: #ffff4d; }
    .score-low { background: linear-gradient(135deg, #4d0d0d, #8a1a1a); color: #ff4d4d; }

    .finding-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.8rem;
        border-left: 4px solid;
    }
    .finding-critical { border-color: #FF4444; }
    .finding-warning { border-color: #FFAA00; }
    .finding-info { border-color: #4488FF; }

    .agent-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ── Helpers ────────────────────────────────────────────────────────────


def score_class(score: int) -> str:
    if score >= 70:
        return "score-high"
    elif score >= 50:
        return "score-mid"
    return "score-low"


def api_available() -> bool:
    try:
        r = httpx.get("http://localhost:8000/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


# ── Sidebar ────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("# 🔥 AgentForge")
    st.markdown("*Multi-Agent Code Review Platform*")
    st.divider()

    page = st.radio(
        "Navigate",
        ["📝 New Review", "📋 Review History", "📊 Analytics"],
        label_visibility="collapsed",
    )

    st.divider()

    # API status
    if api_available():
        st.success("✅ API Connected")
    else:
        st.warning("⚠️ API Offline — Start with:\n`uvicorn agentforge.api.app:app`")

    st.divider()
    st.caption("Built with LangGraph + OpenRouter")


# ── New Review Page ────────────────────────────────────────────────────

if page == "📝 New Review":
    st.title("Submit Code for Review")
    st.markdown(
        "Paste your code below and let our AI agents analyze it for **security**, **performance**, **architecture**, and **correctness** issues."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        filename = st.text_input("Filename", value="example.py", placeholder="e.g. app.py")
    with col2:
        language = st.selectbox("Language", ["Auto-detect", "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust"])

    code = st.text_area(
        "Code",
        height=400,
        placeholder="Paste your code here...",
    )

    context = st.text_area(
        "Additional Context (optional)",
        height=80,
        placeholder="Describe what this code does, relevant architecture decisions, etc.",
    )

    if st.button("🚀 Run Review", type="primary", use_container_width=True):
        if not code.strip():
            st.error("Please paste some code to review.")
        elif not api_available():
            st.error("API is offline. Start it with: `uvicorn agentforge.api.app:app --reload`")
        else:
            with st.spinner("🤖 Agents are reviewing your code..."):
                try:
                    r = httpx.post(
                        f"{API_BASE}/review",
                        json={
                            "code": code,
                            "filename": filename,
                            "language": None if language == "Auto-detect" else language.lower(),
                            "context": context or None,
                        },
                        timeout=10,
                    )
                    r.raise_for_status()
                    review_data = r.json()
                    review_id = review_data["review_id"]

                    st.info(f"Review submitted! ID: `{review_id}`")

                    # Poll for results
                    progress_bar = st.progress(0, text="Waiting for agents...")
                    for i in range(120):  # Max 2 minutes
                        time.sleep(1)
                        progress_bar.progress(
                            min(i / 60, 0.95),
                            text=f"Agents working... ({i}s)",
                        )

                        res = httpx.get(f"{API_BASE}/review/{review_id}", timeout=5)
                        data = res.json()

                        if data["status"] == "completed":
                            progress_bar.progress(1.0, text="✅ Review complete!")
                            st.session_state["current_review"] = data
                            st.rerun()
                            break
                        elif data["status"] == "failed":
                            progress_bar.empty()
                            st.error(f"Review failed: {data.get('result', {}).get('error', 'Unknown error')}")
                            break
                    else:
                        progress_bar.empty()
                        st.warning("Review is taking longer than expected. Check the History page.")

                except httpx.HTTPError as e:
                    st.error(f"API error: {e}")

    # Display results if available
    if "current_review" in st.session_state:
        review_data = st.session_state["current_review"]
        result = review_data.get("result", {})

        if result:
            st.divider()

            # Score
            score = result.get("overall_score", 0)
            st.markdown(
                f'<div class="score-box {score_class(score)}">{score}/100</div>',
                unsafe_allow_html=True,
            )

            # Summary
            st.markdown(f"### Summary\n{result.get('summary', 'No summary available.')}")

            # Findings
            findings = result.get("findings", [])
            if findings:
                st.markdown(f"### Findings ({len(findings)})")
                for f in findings:
                    sev = f.get("severity", "info")
                    emoji = SEVERITY_EMOJI.get(sev, "⚪")
                    color = SEVERITY_COLORS.get(sev, "#888")
                    lines = f"Lines {f.get('line_start', '?')}-{f.get('line_end', '?')}" if f.get("line_start") else ""

                    st.markdown(
                        f'<div class="finding-card finding-{sev}">'
                        f"<strong>{emoji} [{sev.upper()}] {f.get('category', '')}</strong> {lines}<br>"
                        f"{f.get('description', '')}<br>"
                        f"<em>💡 Fix: {f.get('suggested_fix', '—')}</em>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.success("✅ No issues found — code looks great!")

            # Agent reports
            agent_reports = result.get("agent_reports", [])
            if agent_reports:
                st.markdown("### Agent Reports")
                tabs = st.tabs([r.get("agent_name", "Unknown") for r in agent_reports])
                for tab, report in zip(tabs, agent_reports, strict=False):
                    with tab:
                        if report.get("error"):
                            st.error(f"Agent error: {report['error']}")
                        else:
                            st.markdown(f"**Summary**: {report.get('summary', 'N/A')}")
                            st.markdown(f"**Findings**: {len(report.get('findings', []))}")
                            for f in report.get("findings", []):
                                sev = f.get("severity", "info")
                                st.markdown(
                                    f"- {SEVERITY_EMOJI.get(sev, '⚪')} **{f.get('category', '')}**: {f.get('description', '')}"
                                )

            # Clear button
            if st.button("🗑️ Clear Results"):
                del st.session_state["current_review"]
                st.rerun()


# ── History Page ───────────────────────────────────────────────────────

elif page == "📋 Review History":
    st.title("📋 Review History")

    if not api_available():
        st.warning("API is offline.")
    else:
        try:
            r = httpx.get(f"{API_BASE}/reviews", timeout=5)
            reviews = r.json()

            if not reviews:
                st.info("No reviews yet. Submit some code to get started!")
            else:
                for rev in reviews:
                    status_emoji = {"completed": "✅", "pending": "⏳", "failed": "❌"}.get(rev["status"], "❓")
                    with st.expander(
                        f"{status_emoji} {rev['id'][:8]}... — {rev['status']} — {rev.get('created_at', '?')}"
                    ):
                        if rev["status"] == "completed":
                            res = httpx.get(f"{API_BASE}/review/{rev['id']}", timeout=5)
                            data = res.json()
                            result = data.get("result", {})
                            if result:
                                score = result.get("overall_score", "?")
                                st.metric("Score", f"{score}/100")
                                st.markdown(result.get("summary", ""))
                        elif rev["status"] == "pending":
                            st.info("Review is still in progress...")
                        else:
                            st.error("Review failed.")
        except Exception as e:
            st.error(f"Failed to load reviews: {e}")


# ── Analytics Page ─────────────────────────────────────────────────────

elif page == "📊 Analytics":
    st.title("📊 Feedback Analytics")

    if not api_available():
        st.warning("API is offline.")
    else:
        try:
            r = httpx.get(f"{API_BASE}/feedback/stats", timeout=5)
            stats = r.json()

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Feedback", stats.get("total", 0))
            col2.metric("Accepted", stats.get("accepted", 0))
            col3.metric("Rejected", stats.get("rejected", 0))
            col4.metric("Acceptance Rate", f"{stats.get('acceptance_rate', 0)}%")

            st.divider()
            st.markdown("### How Feedback Works")
            st.markdown(
                "When agents produce findings, you can **accept** or **reject** each one. "
                "This data is tracked to identify which agents and categories produce the most "
                "useful suggestions. Over time, agent prompts can be refined based on these insights."
            )

        except Exception as e:
            st.error(f"Failed to load stats: {e}")
