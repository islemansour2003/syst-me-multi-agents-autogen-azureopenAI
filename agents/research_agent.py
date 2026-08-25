from typing import Any, Dict, Optional, Tuple

from autogen import AssistantAgent, UserProxyAgent, register_function

from agents.base_agents import create_user_proxy_agent
from config.azure_config import get_llm_config
from services.news_service import search_news
from services.wikipedia_service import search_wikipedia

RECHERCHE_SYSTEM_MESSAGE = """Tu es l'agent Recherche d'une équipe multi-agents.
Ton rôle est de répondre aux questions de l'utilisateur en t'appuyant sur les outils
mis à ta disposition :
- search_wikipedia : pour du contexte encyclopédique et des définitions.
- search_news : pour des actualités et informations récentes sur un sujet.

Utilise le ou les outils pertinents pour collecter l'information, puis rédige un
résumé clair et structuré des résultats obtenus, en citant tes sources (titres et URLs).
Si un outil ne retourne aucun résultat, dis-le explicitement plutôt que d'inventer une réponse.
Termine ta réponse par TERMINATE."""


class RechercheAgent(AssistantAgent):
    """Agent Recherche : décide quels outils appeler (search_wikipedia, search_news),
    ne les exécute pas lui-même (voir build_research_team)."""

    def __init__(
        self,
        name: str = "recherche",
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            system_message=RECHERCHE_SYSTEM_MESSAGE,
            llm_config=llm_config or get_llm_config(),
            **kwargs,
        )


def _search_wikipedia_tool(query: str, lang: str = "fr") -> Dict[str, Any]:
    """Recherche un résumé encyclopédique sur Wikipedia pour un sujet donné."""
    result = search_wikipedia(query, lang=lang)
    if result is None:
        return {"found": False, "query": query}
    return {"found": True, **result.to_dict()}


def _search_news_tool(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Recherche des articles d'actualité récents sur un sujet donné via NewsAPI."""
    articles = search_news(query, max_results=max_results)
    return {"count": len(articles), "articles": [a.to_dict() for a in articles]}


def build_research_team(
    llm_config: Optional[Dict[str, Any]] = None,
) -> Tuple[AssistantAgent, UserProxyAgent]:
    """Crée l'agent Recherche et son exécuteur d'outils, prêts à converser.

    L'exécuteur (UserProxyAgent) n'exécute que les 2 fonctions enregistrées
    (search_wikipedia, search_news) — pas de code arbitraire, donc pas besoin
    de sandbox Docker ici.
    """
    assistant = RechercheAgent(llm_config=llm_config)
    executor = create_user_proxy_agent(name="research_executor", max_consecutive_auto_reply=6)

    register_function(
        _search_wikipedia_tool,
        caller=assistant,
        executor=executor,
        name="search_wikipedia",
        description="Recherche un résumé encyclopédique sur Wikipedia pour un sujet donné.",
    )
    register_function(
        _search_news_tool,
        caller=assistant,
        executor=executor,
        name="search_news",
        description="Recherche des articles d'actualité récents sur un sujet donné via NewsAPI.",
    )

    return assistant, executor


def ask_research_agent(query: str, llm_config: Optional[Dict[str, Any]] = None) -> str:
    """Pose une question à l'agent Recherche et retourne son résumé final."""
    assistant, executor = build_research_team(llm_config=llm_config)
    result = executor.initiate_chat(assistant, message=query)
    return result.chat_history[-1]["content"]
