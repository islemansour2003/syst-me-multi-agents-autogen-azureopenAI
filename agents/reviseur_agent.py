from typing import Any, Dict, Optional

from autogen import AssistantAgent

from config.azure_config import get_llm_config

REVISEUR_SYSTEM_MESSAGE = """Tu es l'agent Réviseur d'une équipe multi-agents.
Tu analyses le code Python produit par l'agent Codeur : tu identifies les erreurs,
bugs, failles de sécurité ou mauvaises pratiques, et tu proposes des corrections précises.
Si le code est correct et complet, réponds uniquement par CODE_APPROUVE."""


class ReviseurAgent(AssistantAgent):
    """Agent Réviseur (US 2.2) : analyse et valide le code du Codeur."""

    def __init__(
        self,
        name: str = "reviseur",
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            system_message=REVISEUR_SYSTEM_MESSAGE,
            llm_config=llm_config or get_llm_config(),
            **kwargs,
        )
