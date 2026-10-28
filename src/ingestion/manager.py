import logging
from typing import Any

from src.ingestion.base import BaseCollector
from src.ingestion.reddit_collector import RedditCollector
from src.ingestion.youtube_collector import YouTubeCollector

logger = logging.getLogger(__name__)


class IngestionManager:
    """Orchestrates multi-platform social media data ingestion."""

    def __init__(
        self,
        collectors: list[BaseCollector] | None = None,
    ) -> None:
        if collectors is not None:
            self.collectors = collectors
        else:
            self.collectors = [
                YouTubeCollector(),
                RedditCollector(),
            ]

    def fetch_all(self, query: str, limit_per_platform: int = 10) -> list[dict[str, Any]]:
        """Fetch posts across all registered collectors and aggregate them.

        Args:
            query: Brand or topic name to search.
            limit_per_platform: Number of posts to retrieve from each platform.

        Returns:
            Aggregated list of standardized post dictionaries.
        """
        aggregated_posts: list[dict[str, Any]] = []

        for collector in self.collectors:
            platform_name = collector.__class__.__name__
            try:
                posts = collector.fetch_posts(query=query, limit=limit_per_platform)
                aggregated_posts.extend(posts)
            except Exception as e:
                print(f"WARNING: Collector {platform_name} encountered an error: {e}")

        return aggregated_posts


if __name__ == "__main__":
    import json

    manager = IngestionManager()
    search_query = "OpenAI"
    print(f"Fetching posts for query: '{search_query}' (limit_per_platform=5)...\n")

    posts = manager.fetch_all(query=search_query, limit_per_platform=5)

    # Group counts and samples by platform
    platforms: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        plat = post["platform"]
        platforms.setdefault(plat, []).append(post)

    print("--- Ingestion Results Summary ---")
    for plat in ["YouTube", "Reddit"]:
        plat_posts = platforms.get(plat, [])
        print(f"Platform: {plat} | Total Collected: {len(plat_posts)}")
        if plat_posts:
            sample = plat_posts[0].copy()
            # Format datetime for readable display
            sample["timestamp"] = sample["timestamp"].isoformat()
            # Truncate content for display readability
            sample["content"] = (
                sample["content"][:150] + "..."
                if len(sample["content"]) > 150
                else sample["content"]
            )
            print(f"Sample Post:\n{json.dumps(sample, indent=2)}\n")
        else:
            print("No posts collected (either API key missing, rate-limited, or no results found).\n")

