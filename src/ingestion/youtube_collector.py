import logging
from datetime import datetime, timezone
from typing import Any

from config.settings import settings
from src.ingestion.base import BaseCollector

logger = logging.getLogger(__name__)


class YouTubeCollector(BaseCollector):
    """Collector for retrieving YouTube video details and top comments via YouTube Data API v3."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key: str = (api_key if api_key is not None else settings.YOUTUBE_API_KEY).strip()

    def fetch_posts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search YouTube for videos matching query and return standardized post records."""
        if not self.api_key:
            print("WARNING: YOUTUBE_API_KEY is missing or empty. Skipping YouTube collection.")
            return []

        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError

            youtube = build("youtube", "v3", developerKey=self.api_key)

            # Search for videos matching the query
            search_request = youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=min(limit, 50),
                order="date",
            )
            search_response = search_request.execute()

            items = search_response.get("items", [])
            results: list[dict[str, Any]] = []

            for item in items:
                video_id = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if not video_id or not snippet:
                    continue

                title = snippet.get("title", "")
                description = snippet.get("description", "")
                author = snippet.get("channelTitle", "Unknown")
                published_at_str = snippet.get("publishedAt")

                # Parse publishedAt ISO timestamp
                if published_at_str:
                    try:
                        published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                    except Exception:
                        published_at = datetime.now(timezone.utc)
                else:
                    published_at = datetime.now(timezone.utc)

                # Fetch top comments for video
                comments_list: list[str] = []
                try:
                    comments_request = youtube.commentThreads().list(
                        part="snippet",
                        videoId=video_id,
                        maxResults=5,
                        textFormat="plainText",
                    )
                    comments_response = comments_request.execute()
                    for c_item in comments_response.get("items", []):
                        top_comment = (
                            c_item.get("snippet", {})
                            .get("topLevelComment", {})
                            .get("snippet", {})
                            .get("textDisplay", "")
                        )
                        if top_comment:
                            comments_list.append(top_comment.strip())
                except Exception as c_err:
                    logger.debug("Could not fetch comments for video %s: %s", video_id, c_err)

                comments_text = " // ".join(comments_list) if comments_list else "None"
                content = f"Title: {title} | Description: {description} | Top Comments: {comments_text}".strip()
                url = f"https://www.youtube.com/watch?v={video_id}"

                results.append(
                    {
                        "platform": "YouTube",
                        "post_id": f"yt_{video_id}",
                        "author": author,
                        "content": content,
                        "timestamp": published_at,
                        "url": url,
                    }
                )

                if len(results) >= limit:
                    break

            return results

        except HttpError as e:
            print(f"WARNING: YouTube Data API HTTP error occurred: {e}. Returning empty list.")
            return []
        except Exception as e:
            print(f"WARNING: Unexpected error in YouTubeCollector: {e}. Returning empty list.")
            return []

