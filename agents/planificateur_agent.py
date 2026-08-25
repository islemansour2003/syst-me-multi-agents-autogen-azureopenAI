from typing import Any, Dict, Optional

from autogen import AssistantAgent

from config.azure_config import get_llm_config

PLANIFICATEUR_SYSTEM_MESSAGE = """Tu es l'agent Planificateur d'une équipe multi-agents.
Ton rôle est de décomposer la demande de l'utilisateur en un plan d'action structuré,
sous forme d'étapes numérotées, claires et ordonnées, destinées à être exécutées par
l'agent Codeur puis validées par l'agent Réviseur.
Ne rédige jamais de code toi-même : produis uniquement le plan.
Termine ta réponse par TERMINATE une fois le plan complet fourni."""


class PlanificateurAgent(AssistantAgent):
    """Agent Planificateur (US 2.1) : décompose la demande en sous-tâches."""

    def __init__(
        self,
        name: str = "planificateur",
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            system_message=PLANIFICATEUR_SYSTEM_MESSAGE,
            llm_config=llm_config or get_llm_config(),
            **kwargs,
        )
