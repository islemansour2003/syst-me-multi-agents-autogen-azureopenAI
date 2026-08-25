from typing import Any, Dict, List, Optional, Tuple

from autogen import AssistantAgent, UserProxyAgent, register_function

from agents.base_agents import create_user_proxy_agent
from config.azure_config import get_llm_config
from services.analysis_service import compute_statistics, detect_anomalies

ANALYSTE_SYSTEM_MESSAGE = """Tu es l'agent Analyste d'une équipe multi-agents.
Ton rôle est d'analyser des données structurées et de produire un rapport clair.

Applique un raisonnement en chaîne (Chain-of-Thought) explicite, en suivant ces étapes
dans ta réponse, sans en sauter :
1. Observation : résume ce que représentent les données fournies.
2. Calculs : utilise l'outil get_statistics pour obtenir les statistiques descriptives.
3. Anomalies : utilise l'outil detect_anomalies pour identifier les valeurs aberrantes.
4. Patterns : identifie les tendances, régularités ou corrélations visibles dans les
   données et les statistiques obtenues.
5. Conclusion : synthétise tes observations en une conclusion actionnable.

Termine toujours ta réponse par un rapport structuré au format suivant :

### Rapport d'Analyse
**Résumé** : ...
**Statistiques** : ...
**Anomalies détectées** : ...
**Patterns identifiés** : ...
**Conclusion** : ...

Termine ta réponse par TERMINATE."""


class AnalysteAgent(AssistantAgent):
    """Agent Analyste : raisonnement en chaîne + détection d'anomalies/patterns
    sur des données structurées, via les outils get_statistics et detect_anomalies."""

    def __init__(
        self,
        name: str = "analyste",
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            system_message=ANALYSTE_SYSTEM_MESSAGE,
            llm_config=llm_config or get_llm_config(),
            **kwargs,
        )


def _get_statistics_tool(data: List[float]) -> Dict[str, Any]:
    """Calcule les statistiques descriptives (moyenne, médiane, min, max, écart-type)
    d'une série de valeurs numériques."""
    return compute_statistics(data)


def _detect_anomalies_tool(data: List[float], threshold: float = 2.0) -> Dict[str, Any]:
    """Détecte les valeurs aberrantes (anomalies) dans une série de valeurs numériques
    via la méthode du z-score."""
    anomalies = detect_anomalies(data, threshold=threshold)
    return {"count": len(anomalies), "anomalies": [a.to_dict() for a in anomalies]}


def build_analyste_team(
    llm_config: Optional[Dict[str, Any]] = None,
) -> Tuple[AssistantAgent, UserProxyAgent]:
    """Crée l'agent Analyste et son exécuteur d'outils, prêts à converser.

    L'exécuteur n'exécute que les 2 fonctions enregistrées (calculs statistiques
    déterministes) — pas de code arbitraire, donc pas besoin de sandbox Docker ici.
    """
    assistant = AnalysteAgent(llm_config=llm_config)
    executor = create_user_proxy_agent(name="analyste_executor", max_consecutive_auto_reply=6)

    register_function(
        _get_statistics_tool,
        caller=assistant,
        executor=executor,
        name="get_statistics",
        description="Calcule les statistiques descriptives (moyenne, médiane, min, max, écart-type) d'une série de valeurs numériques.",
    )
    register_function(
        _detect_anomalies_tool,
        caller=assistant,
        executor=executor,
        name="detect_anomalies",
        description="Détecte les valeurs aberrantes (anomalies) dans une série de valeurs numériques via la méthode du z-score.",
    )

    return assistant, executor


def analyze_data(description: str, data: List[float], llm_config: Optional[Dict[str, Any]] = None) -> str:
    """Demande à l'agent Analyste d'analyser une série de données et retourne son rapport final."""
    assistant, executor = build_analyste_team(llm_config=llm_config)
    message = f"{description}\n\nDonnées : {data}"
    result = executor.initiate_chat(assistant, message=message)
    return result.chat_history[-1]["content"]
