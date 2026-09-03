from typing import Any, Dict, Optional

from autogen import AssistantAgent

from config.azure_config import get_llm_config

REVISEUR_SYSTEM_MESSAGE = """Tu es l'agent Réviseur d'une équipe multi-agents.
Tu analyses le code Python produit par l'agent Codeur avant qu'il ne soit livré.

Vérifie CHAQUE exigence explicitement mentionnée dans la demande initiale ou le plan
(gestion d'erreurs, cas limites précis, types d'exceptions et messages attendus,
tests, docstring, etc.) : si UNE SEULE de ces exigences explicites n'est pas
respectée ou est absente du code, tu dois REJETER, même si le reste du code est
par ailleurs correct. Liste alors précisément et uniquement ce qui manque, sans
approuver "sous réserve".

Ne réponds CODE_APPROUVE que si TOUTES les exigences explicites de la demande sont
strictement satisfaites."""


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
