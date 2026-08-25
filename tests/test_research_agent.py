from autogen import AssistantAgent, UserProxyAgent

from agents.research_agent import (
    RechercheAgent,
    _search_news_tool,
    _search_wikipedia_tool,
    build_research_team,
)
from services.news_service import NewsArticle
from services.wikipedia_service import WikipediaResult
from tests.fake_model_client import fake_llm_config


# --- Extraction et structuration des données (outils exposés à l'agent) ---

def test_search_wikipedia_tool_structures_found_result(monkeypatch):
    monkeypatch.setattr(
        "agents.research_agent.search_wikipedia",
        lambda query, lang="fr": WikipediaResult(title="Titre", summary="Résumé", url="https://url"),
    )
    result = _search_wikipedia_tool("test")
    assert result == {"found": True, "title": "Titre", "summary": "Résumé", "url": "https://url"}


def test_search_wikipedia_tool_handles_no_result(monkeypatch):
    monkeypatch.setattr("agents.research_agent.search_wikipedia", lambda query, lang="fr": None)
    result = _search_wikipedia_tool("sujet_inexistant")
    assert result == {"found": False, "query": "sujet_inexistant"}


def test_search_news_tool_structures_articles(monkeypatch):
    monkeypatch.setattr(
        "agents.research_agent.search_news",
        lambda query, max_results=5: [
            NewsArticle(title="T", description="D", url="U", source="S", published_at="P")
        ],
    )
    result = _search_news_tool("test")
    assert result["count"] == 1
    assert result["articles"][0] == {
        "title": "T",
        "description": "D",
        "url": "U",
        "source": "S",
        "published_at": "P",
    }


# --- Agent instanciable et outils enregistrés ---

def test_research_agent_is_instantiable():
    agent = RechercheAgent(llm_config=fake_llm_config())
    assert isinstance(agent, RechercheAgent)
    assert isinstance(agent, AssistantAgent)
    assert agent.name == "recherche"


def test_build_research_team_registers_both_tools():
    assistant, executor = build_research_team(llm_config=fake_llm_config())

    assert isinstance(assistant, AssistantAgent)
    assert isinstance(executor, UserProxyAgent)

    # L'exécuteur doit pouvoir exécuter les 2 outils (extraction de données)
    assert "search_wikipedia" in executor.function_map
    assert "search_news" in executor.function_map

    # L'agent LLM doit connaître la définition des 2 outils (function-calling)
    tool_names = {tool["function"]["name"] for tool in assistant.llm_config["tools"]}
    assert {"search_wikipedia", "search_news"}.issubset(tool_names)
