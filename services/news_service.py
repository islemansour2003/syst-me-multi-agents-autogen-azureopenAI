import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

import requests

NEWS_API_URL = "https://newsapi.org/v2/everything"
TIMEOUT = 10


@dataclass
class NewsArticle:
    title: str
    description: str
    url: str
    source: str
    published_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def search_news(query: str, max_results: int = 5, language: str = "fr") -> List[NewsArticle]:
    """Recherche des articles d'actualité récents via NewsAPI et retourne une liste structurée."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise EnvironmentError("NEWS_API_KEY manquant dans .env")

    response = requests.get(
        NEWS_API_URL,
        params={
            "q": query,
            "apiKey": api_key,
            "language": language,
            "pageSize": max_results,
            "sortBy": "relevancy",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()

    return [
        NewsArticle(
            title=item.get("title") or "",
            description=item.get("description") or "",
            url=item.get("url") or "",
            source=(item.get("source") or {}).get("name", ""),
            published_at=item.get("publishedAt") or "",
        )
        for item in data.get("articles", [])[:max_results]
    ]
