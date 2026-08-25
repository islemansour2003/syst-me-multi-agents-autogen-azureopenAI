import pytest

from services.news_service import NewsArticle, search_news
from services.wikipedia_service import WikipediaResult, search_wikipedia


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# --- NewsAPI ---

def test_search_news_returns_structured_articles(monkeypatch):
    monkeypatch.setenv("NEWS_API_KEY", "fake-key")

    def fake_get(url, params=None, timeout=None):
        assert params["apiKey"] == "fake-key"
        assert params["q"] == "intelligence artificielle"
        return FakeResponse(
            {
                "articles": [
                    {
                        "title": "Titre 1",
                        "description": "Description 1",
                        "url": "https://example.com/1",
                        "source": {"name": "Source 1"},
                        "publishedAt": "2026-08-20T10:00:00Z",
                    },
                    {
                        "title": "Titre 2",
                        "description": None,
                        "url": "https://example.com/2",
                        "source": {"name": "Source 2"},
                        "publishedAt": "2026-08-21T10:00:00Z",
                    },
                ]
            }
        )

    monkeypatch.setattr("services.news_service.requests.get", fake_get)

    articles = search_news("intelligence artificielle", max_results=5)

    assert len(articles) == 2
    assert isinstance(articles[0], NewsArticle)
    assert articles[0].title == "Titre 1"
    assert articles[0].source == "Source 1"
    assert articles[1].description == ""  # None normalisé en chaîne vide


def test_search_news_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("NEWS_API_KEY", raising=False)
    with pytest.raises(EnvironmentError):
        search_news("test")


def test_search_news_respects_max_results(monkeypatch):
    monkeypatch.setenv("NEWS_API_KEY", "fake-key")

    def fake_get(url, params=None, timeout=None):
        return FakeResponse(
            {
                "articles": [
                    {
                        "title": f"Article {i}",
                        "description": "",
                        "url": "",
                        "source": {"name": "S"},
                        "publishedAt": "",
                    }
                    for i in range(10)
                ]
            }
        )

    monkeypatch.setattr("services.news_service.requests.get", fake_get)

    articles = search_news("test", max_results=3)
    assert len(articles) == 3


# --- Wikipedia ---

def test_search_wikipedia_returns_structured_result(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        if params is not None and params.get("action") == "query":
            return FakeResponse({"query": {"search": [{"title": "Python (langage)"}]}})
        return FakeResponse(
            {
                "title": "Python (langage)",
                "extract": "Python est un langage de programmation.",
                "content_urls": {"desktop": {"page": "https://fr.wikipedia.org/wiki/Python_(langage)"}},
            }
        )

    monkeypatch.setattr("services.wikipedia_service.requests.get", fake_get)

    result = search_wikipedia("Python")

    assert isinstance(result, WikipediaResult)
    assert result.title == "Python (langage)"
    assert "langage de programmation" in result.summary
    assert result.url.startswith("https://fr.wikipedia.org")


def test_search_wikipedia_returns_none_when_no_results(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse({"query": {"search": []}})

    monkeypatch.setattr("services.wikipedia_service.requests.get", fake_get)

    result = search_wikipedia("zzzznonexistent")
    assert result is None
