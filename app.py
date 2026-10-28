from datetime import datetime, timezone
import json
from typing import Any
import pandas as pd
import plotly.express as px
from sqlalchemy import desc, select
import streamlit as st

from src.agents.qna_agent import answer_telemetry_question
from src.agents.response_agent import generate_crisis_response
from src.agents.sentiment_agent import analyze_post
from src.alerts.webhook_notifier import send_slack_alert
from src.database.connection import SessionLocal, init_db
from src.database.models import AlertLog, Mention
from src.ingestion.youtube_collector import YouTubeCollector

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Brand Sentiment & Crisis Monitoring Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure database tables exist
init_db()


def load_mentions_df() -> pd.DataFrame:
    """Load mentions from the database into a pandas DataFrame."""
    session = SessionLocal()
    try:
        stmt = select(Mention).order_by(desc(Mention.timestamp))
        mentions = session.execute(stmt).scalars().all()
        if not mentions:
            return pd.DataFrame()

        data: list[dict[str, Any]] = [
            {
                "id": m.id,
                "platform": m.platform,
                "post_id": m.post_id,
                "author": m.author,
                "content": m.content,
                "timestamp": m.timestamp,
                "sentiment": m.sentiment,
                "sentiment_score": m.sentiment_score,
                "category": m.category,
                "key_entities": m.key_entities,
                "keywords": m.keywords,
                "severity_rating": m.severity_rating,
                "summary": m.summary,
                "created_at": m.created_at,
            }
            for m in mentions
        ]
        return pd.DataFrame(data)
    finally:
        session.close()


def run_pipeline_action(query: str, limit: int = 5) -> tuple[int, int, int]:
    """Execute ingestion and analysis pipeline directly from Streamlit."""
    collector = YouTubeCollector()
    posts = collector.fetch_posts(query=query, limit=limit)
    total_fetched = len(posts)

    new_saved = 0
    crisis_count = 0

    if not posts:
        return 0, 0, 0

    session = SessionLocal()
    try:
        for post in posts:
            post_id = post["post_id"]
            existing = session.execute(
                select(Mention).where(Mention.post_id == post_id)
            ).scalar_one_or_none()

            if existing:
                continue

            analysis = analyze_post(post["content"])
            mention = Mention(
                platform=post["platform"],
                post_id=post_id,
                author=post["author"],
                content=post["content"],
                timestamp=post["timestamp"],
                sentiment=analysis.sentiment,
                sentiment_score=analysis.sentiment_score,
                category=analysis.category,
                key_entities=json.dumps(analysis.key_entities),
                keywords=json.dumps(analysis.keywords),
                severity_rating=analysis.severity_rating,
                summary=analysis.summary,
            )
            session.add(mention)
            session.commit()
            new_saved += 1

            if analysis.severity_rating >= 7:
                crisis_count += 1
                pr_response = generate_crisis_response(
                    post_content=post["content"],
                    summary=analysis.summary,
                    category=analysis.category,
                )
                send_slack_alert(
                    post_content=post["content"],
                    severity=analysis.severity_rating,
                    category=analysis.category,
                    summary=analysis.summary,
                    url=post.get("url", ""),
                    pr_draft=pr_response,
                )
                alert_log = AlertLog(
                    triggered_at=datetime.now(timezone.utc),
                    severity_level=f"Severity {analysis.severity_rating}",
                    post_count=1,
                    alert_message=f"[{analysis.category}] {analysis.summary}\nPR Draft:\n{pr_response}",
                )
                session.add(alert_log)
                session.commit()

        return total_fetched, new_saved, crisis_count
    finally:
        session.close()


# Sidebar Controls
st.sidebar.title("🛡️ Controls & Filters")
brand_query = st.sidebar.text_input("Brand Search Query", value="OpenAI")
fetch_limit = st.sidebar.slider("Ingestion Batch Limit", min_value=1, max_value=20, value=5)

if st.sidebar.button("🚀 Run Ingestion & AI Pipeline", use_container_width=True):
    with st.spinner(f"Ingesting live posts, comments & running LLM agents for '{brand_query}'..."):
        fetched, saved, alerts = run_pipeline_action(brand_query, limit=fetch_limit)
        st.sidebar.success(
            f"Pipeline complete!\nFetched: {fetched} | New Saved: {saved} | High Severity: {alerts}"
        )

# Load current data
df = load_mentions_df()

# Sidebar Filters
available_categories = (
    sorted(df["category"].dropna().unique().tolist())
    if not df.empty and "category" in df.columns
    else []
)
all_sentiments = ["Positive", "Neutral", "Negative"]

selected_categories = st.sidebar.multiselect(
    "Filter by Category",
    options=available_categories,
    default=available_categories,
)
selected_sentiments = st.sidebar.multiselect(
    "Filter by Sentiment",
    options=all_sentiments,
    default=all_sentiments,
)

# Apply filters
filtered_df = df.copy() if not df.empty else pd.DataFrame()
if not filtered_df.empty:
    if selected_categories:
        filtered_df = filtered_df[filtered_df["category"].isin(selected_categories)]
    if selected_sentiments:
        filtered_df = filtered_df[filtered_df["sentiment"].isin(selected_sentiments)]

# Dashboard Header
st.title("🛡️ Brand Sentiment & Crisis Monitoring Dashboard")
st.caption("Real-time multi-platform brand intelligence, video comment telemetry, and executive crisis detection.")
st.markdown("---")

# Main Navigation Tabs
tab_analytics, tab_qna, tab_crisis = st.tabs(
    ["📊 Analytics Dashboard", "💬 Ask Your Telemetry", "🚨 High-Severity Crisis Feed"]
)

with tab_analytics:
    # KPI Metric Cards
    total_mentions = len(filtered_df)
    negative_pct = 0.0
    avg_severity = 0.0
    high_severity_spikes = 0

    if total_mentions > 0:
        negative_count = len(filtered_df[filtered_df["sentiment"] == "Negative"])
        negative_pct = (negative_count / total_mentions) * 100.0
        avg_severity = filtered_df["severity_rating"].mean()
        high_severity_spikes = len(filtered_df[filtered_df["severity_rating"] >= 7])

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(label="Total Mentions", value=f"{total_mentions:,}")
    with kpi2:
        st.metric(
            label="Negative Sentiment %",
            value=f"{negative_pct:.1f}%",
            delta=f"{'-' if negative_pct > 25 else ''}{negative_pct:.1f}%",
            delta_color="inverse",
        )
    with kpi3:
        st.metric(label="Average Severity Rating", value=f"{avg_severity:.2f} / 10")
    with kpi4:
        st.metric(
            label="High-Severity Spikes (>= 7)",
            value=str(high_severity_spikes),
            delta="Needs Attention" if high_severity_spikes > 0 else "Normal",
            delta_color="inverse",
        )

    st.markdown("---")

    # Visualizations
    if not filtered_df.empty:
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Sentiment Distribution")
            sentiment_counts = (
                filtered_df["sentiment"]
                .value_counts()
                .reset_index(name="count")
                .rename(columns={"index": "sentiment"})
            )
            color_map = {
                "Positive": "#10B981",
                "Neutral": "#6B7280",
                "Negative": "#EF4444",
            }
            fig_donut = px.pie(
                sentiment_counts,
                values="count",
                names="sentiment",
                hole=0.45,
                color="sentiment",
                color_discrete_map=color_map,
            )
            fig_donut.update_traces(textinfo="percent+label")
            fig_donut.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=320)
            st.plotly_chart(fig_donut, use_container_width=True)

        with chart_col2:
            st.subheader("Category Volume")
            cat_counts = (
                filtered_df["category"]
                .value_counts()
                .reset_index(name="count")
                .rename(columns={"index": "category"})
            )
            fig_bar = px.bar(
                cat_counts,
                x="category",
                y="count",
                color="category",
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig_bar.update_layout(
                xaxis_title="Category",
                yaxis_title="Mentions Count",
                showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20),
                height=320,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("Severity Rating vs. Sentiment Score Over Time")
        fig_scatter = px.scatter(
            filtered_df,
            x="timestamp",
            y="severity_rating",
            size="severity_rating",
            color="sentiment",
            color_discrete_map=color_map,
            hover_data=["author", "category", "sentiment_score", "summary"],
            title="Incident Severity Timeline",
        )
        fig_scatter.update_layout(
            yaxis_title="Severity Rating (1-10)",
            xaxis_title="Post Timestamp",
            height=380,
            margin=dict(t=40, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    else:
        st.info("No mentions available matching the current filters. Run the ingestion pipeline using the sidebar.")

    st.markdown("---")

    # Telemetry Data Table
    st.subheader("📋 Raw Telemetry & Mentions Data")
    if not filtered_df.empty:
        display_cols = [
            "id",
            "platform",
            "timestamp",
            "author",
            "sentiment",
            "sentiment_score",
            "category",
            "severity_rating",
            "summary",
            "key_entities",
            "keywords",
            "content",
        ]
        available_cols = [c for c in display_cols if c in filtered_df.columns]
        st.dataframe(
            filtered_df[available_cols],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("No records to display.")

with tab_qna:
    st.subheader("💬 Ask Your Telemetry (AI Q&A)")
    st.caption("Ask questions about brand sentiment, customer feedback, bugs, and incident patterns across your ingested data.")

    qna_query = st.text_input(
        "Ask a question about your ingested brand data (e.g., 'What are customers saying about software bugs?'):",
        placeholder="e.g. What are the most common complaints or praises from users?",
    )

    if st.button("🔍 Get AI Answer", use_container_width=False):
        if not qna_query.strip():
            st.warning("Please enter a question before submitting.")
        elif df.empty:
            st.warning("No telemetry records are currently stored. Please run the ingestion pipeline first.")
        else:
            with st.spinner("Analyzing telemetry records with AI..."):
                records_payload = df.to_dict(orient="records")
                ai_answer = answer_telemetry_question(qna_query, records_payload)
                st.session_state["last_qna_answer"] = ai_answer
                st.session_state["last_qna_query"] = qna_query

    if "last_qna_answer" in st.session_state:
        st.markdown(f"**Question:** *{st.session_state.get('last_qna_query', '')}*")
        st.markdown("### 🤖 Brand Analyst Insights")
        st.markdown(st.session_state["last_qna_answer"])

with tab_crisis:
    st.subheader("🚨 High-Severity Crisis Feed (Severity >= 7)")
    critical_df = (
        df[df["severity_rating"] >= 7].sort_values(by="timestamp", ascending=False)
        if not df.empty
        else pd.DataFrame()
    )

    if not critical_df.empty:
        st.warning(f"Found {len(critical_df)} high-severity incident(s) requiring executive attention.")
        for idx, row in critical_df.iterrows():
            expander_title = (
                f"⚠️ [{row['platform']}] Severity {row['severity_rating']}/10 - {row['category']} - "
                f"@{row['author']} ({row['timestamp']})"
            )
            with st.expander(expander_title, expanded=False):
                st.markdown(f"**Incident Summary:** {row['summary']}")
                st.markdown(f"**Post Content:**\n> {row['content']}")
                st.markdown(
                    f"**Metrics:** Sentiment: `{row['sentiment']}` | Score: `{row['sentiment_score']:.2f}` | Post ID: `{row['post_id']}`"
                )
                if "key_entities" in row and row["key_entities"]:
                    st.markdown(f"**Key Entities:** `{row['key_entities']}`")
                if "keywords" in row and row["keywords"]:
                    st.markdown(f"**Keywords:** `{row['keywords']}`")

                btn_key = f"pr_btn_{row['id']}"
                area_key = f"pr_area_{row['id']}"

                if st.button("Generate Executive PR Draft", key=btn_key):
                    with st.spinner("Generating executive talking point with PR Agent..."):
                        pr_text = generate_crisis_response(
                            post_content=str(row["content"]),
                            summary=str(row["summary"]),
                            category=str(row["category"]),
                        )
                        st.session_state[area_key] = pr_text

                if area_key in st.session_state:
                    st.markdown("### Executive PR Response Draft")
                    st.info(st.session_state[area_key])
    else:
        st.success("✅ No critical crisis incidents detected (all posts currently below Severity 7).")
