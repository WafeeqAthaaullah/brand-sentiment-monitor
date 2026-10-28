from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """Abstract base class for all social media and web data collectors."""

    @abstractmethod
    def fetch_posts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch posts matching the given brand search query.

        Args:
            query: Brand or topic query keyword.
            limit: Maximum number of posts to fetch.

        Returns:
            List of standardized post dictionaries with structure:
            {
                'platform': str,
                'post_id': str,
                'author': str,
                'content': str,
                'timestamp': datetime,
                'url': str
            }
        """
        pass

