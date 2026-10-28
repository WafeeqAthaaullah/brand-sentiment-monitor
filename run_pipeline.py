import argparse
import json
import sys
from datetime import datetime, timezone
from sqlalchemy import select

from src.database.connection import SessionLocal, init_db
from src.database.models import AlertLog, Mention
from src.ingestion.youtube_collector import YouTubeCollector
from src.agents.sentiment_agent import analyze_post
from src.agents.response_agent import generate_crisis_response
from src.alerts.webhook_notifier import send_slack_alert


def run_pipeline(query: str, limit: int = 5) -> None:
    """Execute end-to-end sentiment monitoring and crisis alert pipeline.

    Args:
        query: Search brand/topic keyword.
        limit: Max number of posts to fetch from YouTube.
    """
    print("=" * 60)
    print(f"🚀 Starting Brand Sentiment Pipeline for query: '{query}'")
    print(f"Fetch limit: {limit}")
    print("=" * 60)

    # 1. Ensure DB tables exist
    init_db()

    # 2. Fetch live YouTube posts
    collector = YouTubeCollector()
    posts = collector.fetch_posts(query=query, limit=limit)
    total_fetched = len(posts)
    print(f"Found {total_fetched} post(s) from YouTube.")

    if not posts:
        print("No posts to process. Exiting pipeline.")
        return

    new_saved_count = 0
    high_severity_count = 0

    session = SessionLocal()
    try:
        for idx, post in enumerate(posts, start=1):
            post_id = post["post_id"]
            title_or_snippet = post["content"][:80].replace("\n", " ")

            print(f"\n[{idx}/{total_fetched}] Processing post: {post_id}")
            print(f"Snippet: {title_or_snippet}...")

            # Check if mention already exists
            existing = session.execute(
                select(Mention).where(Mention.post_id == post_id)
            ).scalar_one_or_none()

            if existing:
                print(f"ℹ️ Post '{post_id}' already exists in database. Skipping duplicate analysis.")
                continue

            # Analyze content with LLM agent
            analysis = analyze_post(post["content"])
            print(
                f"📊 Sentiment: {analysis.sentiment} (Score: {analysis.sentiment_score:.2f}) | "
                f"Category: {analysis.category} | Severity: {analysis.severity_rating}/10"
            )

            # Persist to Mention table
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
            new_saved_count += 1

            # High severity crisis check (severity >= 7)
            if analysis.severity_rating >= 7:
                high_severity_count += 1
                print(f"🚨 CRITICAL ALERT TRIGGERED! Severity rating: {analysis.severity_rating}/10")

                # Generate executive PR response draft
                pr_response = generate_crisis_response(
                    post_content=post["content"],
                    summary=analysis.summary,
                    category=analysis.category,
                )

                # Send Slack alert
                send_slack_alert(
                    post_content=post["content"],
                    severity=analysis.severity_rating,
                    category=analysis.category,
                    summary=analysis.summary,
                    url=post.get("url", ""),
                    pr_draft=pr_response,
                )

                # Log to AlertLog table
                alert_log = AlertLog(
                    triggered_at=datetime.now(timezone.utc),
                    severity_level=f"Severity {analysis.severity_rating}",
                    post_count=1,
                    alert_message=f"[{analysis.category}] {analysis.summary}\nPR Draft:\n{pr_response}",
                )
                session.add(alert_log)
                session.commit()

    except Exception as e:
        session.rollback()
        print(f"❌ Error during pipeline execution: {e}", file=sys.stderr)
        raise
    finally:
        session.close()

    print("\n" + "=" * 60)
    print("📈 Pipeline Execution Summary")
    print("=" * 60)
    print(f"Query:                   {query}")
    print(f"Total Posts Fetched:     {total_fetched}")
    print(f"New Records Saved:       {new_saved_count}")
    print(f"High-Severity Alerts:    {high_severity_count}")
    print("=" * 60 + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Brand Sentiment & Crisis Monitoring Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--query",
        type=str,
        default="OpenAI",
        help="Search brand/topic query to monitor",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of YouTube posts to fetch",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(query=args.query, limit=args.limit)

