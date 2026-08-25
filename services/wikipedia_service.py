from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

import requests

SEARCH_URL = "https://{lang}.wikipedia.org/w/api.php"
SUMMARY_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
TIMEOUT = 10

# Wikimedia bloque (403) les requêtes sans User-Agent identifiable :
# https://meta.wikimedia.org/wiki/User-Agent_policy
HEADERS = {"User-Agent": "SmartovateMultiAgentPoC/1.0 (https://github.com/smartovate; contact-project-maintainer)"}


@dataclass
class WikipediaResult:
    title: str
    summary: str
    url: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def search_wikipedia(query: str, lang: str = "fr") -> Optional[WikipediaResult]:
    """Recherche un article Wikipedia et retourne son résumé structuré.

    Retourne None si aucun article ne correspond à la requête.
    """
    search_response = requests.get(
        SEARCH_URL.format(lang=lang),
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 1,
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    search_response.raise_for_status()
    results = search_response.json().get("query", {}).get("search", [])
    if not results:
        return None

    title = results[0]["title"]
    summary_response = requests.get(
        SUMMARY_URL.format(lang=lang, title=title.replace(" ", "_")),
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    summary_response.raise_for_status()
    summary_data = summary_response.json()

    return WikipediaResult(
        title=summary_data.get("title", title),
        summary=summary_data.get("extract", ""),
        url=summary_data.get("content_urls", {}).get("desktop", {}).get("page", ""),
    )
