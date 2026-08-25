from typing import Any, Dict, Optional

from autogen import AssistantAgent

from config.azure_config import get_llm_config

CODEUR_SYSTEM_MESSAGE = """Tu es l'agent Codeur d'une équipe multi-agents.
Tu reçois un plan d'action ou des instructions précises et tu génères du code Python
fonctionnel, lisible et commenté pour répondre à la demande.
Si l'agent Réviseur signale des erreurs ou des améliorations, corrige ton code en
conséquence dans ta réponse suivante."""


class CodeurAgent(AssistantAgent):
    """Agent Codeur (US 2.2) : génère du code Python à partir du plan."""

    def __init__(
        self,
        name: str = "codeur",
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            system_message=CODEUR_SYSTEM_MESSAGE,
            llm_config=llm_config or get_llm_config(),
            **kwargs,
        )
