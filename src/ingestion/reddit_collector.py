import logging
from datetime import datetime, timezone
from typing import Any
import requests

from src.ingestion.base import BaseCollector

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    """Collector for retrieving public Reddit posts matching a search query with fallback URLs."""

    FALLBACK_URLS = [
        "https://www.reddit.com/r/all/search.json",
        "https://www.reddit.com/search.json",
        "https://old.reddit.com/search.json",
    ]

    def __init__(self, user_agent: str | None = None) -> None:
        self.session = requests.Session()
        headers = {
            "User-Agent": user_agent
            or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        self.session.headers.update(headers)

    def fetch_posts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch posts from Reddit using a session and fallback URLs on HTTP 403 errors."""
        params = {
            "q": query,
            "sort": "new",
            "limit": min(limit, 100),
            "restrict_sr": 0,
        }

        data = None

        for endpoint in self.FALLBACK_URLS:
            try:
                response = self.session.get(
                    endpoint,
                    params=params,
                    timeout=10,
                )

                if response.status_code == 403:
                    print(f"WARNING: HTTP 403 encountered on {endpoint}. Trying next fallback...")
                    continue

                if response.status_code == 429:
                    print(f"WARNING: Reddit API rate limited (HTTP 429) on {endpoint}. Trying next fallback...")
                    continue

                response.raise_for_status()
                data = response.json()
                break  # Successful response obtained

            except requests.RequestException as e:
                print(f"WARNING: Network error requesting {endpoint}: {e}. Trying next fallback...")
                continue
            except Exception as e:
                print(f"WARNING: Unexpected error with {endpoint}: {e}. Trying next fallback...")
                continue

        if not data:
            print("WARNING: All Reddit endpoints failed or were blocked. Returning empty list.")
            return []

        try:
            children = data.get("data", {}).get("children", [])
            results: list[dict[str, Any]] = []

            for child in children:
                post = child.get("data", {})
                if not post:
                    continue

                post_id = post.get("id") or post.get("name")
                if not post_id:
                    continue

                title = post.get("title", "")
                selftext = post.get("selftext", "")
                author = post.get("author", "[deleted]")
                created_utc = post.get("created_utc")
                permalink = post.get("permalink", "")

                if created_utc:
                    try:
                        timestamp = datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
                    except Exception:
                        timestamp = datetime.now(timezone.utc)
                else:
                    timestamp = datetime.now(timezone.utc)

                content = f"{title}\n\n{selftext}".strip()
                url = f"https://www.reddit.com{permalink}" if permalink else f"https://reddit.com/{post_id}"

                results.append(
                    {
                        "platform": "Reddit",
                        "post_id": f"reddit_{post_id}",
                        "author": author,
                        "content": content,
                        "timestamp": timestamp,
                        "url": url,
                    }
                )

                if len(results) >= limit:
                    break

            return results

        except Exception as e:
            print(f"WARNING: Unexpected error parsing Reddit response structure: {e}. Returning empty list.")
            return []
