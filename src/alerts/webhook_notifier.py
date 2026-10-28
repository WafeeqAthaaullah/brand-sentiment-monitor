import logging
from typing import Any
import requests

from config.settings import settings

logger = logging.getLogger(__name__)


def send_slack_alert(
    post_content: str,
    severity: int,
    category: str,
    summary: str,
    url: str,
    pr_draft: str | None = None,
) -> bool:
    """Send a formatted crisis alert notification to Slack via incoming webhook.

    Args:
        post_content: Content of the high-severity mention.
        severity: Severity rating (1-10).
        category: Classified category.
        summary: AI-generated summary of the incident.
        url: Direct link to the source post.
        pr_draft: Optional executive PR talking-point draft.

    Returns:
        True if the webhook was sent successfully, False otherwise.
    """
    webhook_url = settings.SLACK_WEBHOOK_URL

    if not webhook_url or not webhook_url.strip() or "xxx/yyy/zzz" in webhook_url:
        print("\n" + "=" * 60)
        print("[SLACK ALERT NOTIFICATION (SIMULATION - NO WEBHOOK CONFIGURED)]")
        print(f"Severity: {severity}/10 | Category: {category}")
        print(f"Summary: {summary}")
        print(f"URL: {url}")
        if pr_draft:
            print(f"Executive PR Talking Point:\n{pr_draft}")
        print("=" * 60 + "\n")
        return False

    # Build Slack Block Kit payload
    truncated_content = post_content[:300] + ("..." if len(post_content) > 300 else "")
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 Crisis Alert: Severity {severity}/10 Flagged",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Category:*\n{category}"},
                {"type": "mrkdwn", "text": f"*Severity:*\n{severity}/10"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:*\n{summary}\n\n*Content:*\n> {truncated_content}\n\n*Link:* <{url}|View Original Post>",
            },
        },
    ]

    if pr_draft:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Executive PR Response Draft:*\n```{pr_draft}```",
                },
            }
        )

    payload = {
        "text": f"🚨 High-severity brand crisis alert ({severity}/10) in category '{category}'",
        "blocks": blocks,
    }

    try:
        response = requests.post(
            webhook_url.strip(),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if response.status_code == 200:
            logger.info("Slack alert dispatched successfully.")
            return True
        else:
            print(f"WARNING: Slack webhook returned non-200 status: {response.status_code} ({response.text})")
            return False

    except Exception as e:
        print(f"WARNING: Failed to send Slack alert via webhook: {e}")
        return False

