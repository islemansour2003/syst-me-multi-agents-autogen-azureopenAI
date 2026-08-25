from typing import Any, Dict, List, Optional

from autogen import AssistantAgent, ConversableAgent, UserProxyAgent

from config.azure_config import get_llm_config

DEFAULT_ASSISTANT_SYSTEM_MESSAGE = (
    "Tu es un agent assistant utile. Réponds de manière claire et concise."
)


def create_assistant_agent(
    name: str = "assistant",
    system_message: str = DEFAULT_ASSISTANT_SYSTEM_MESSAGE,
    llm_config: Optional[Dict[str, Any]] = None,
) -> AssistantAgent:
    """Crée un AssistantAgent (agent génératif, s'appuie sur le LLM)."""
    return AssistantAgent(
        name=name,
        system_message=system_message,
        llm_config=llm_config or get_llm_config(),
    )


def create_user_proxy_agent(
    name: str = "user_proxy",
    human_input_mode: str = "NEVER",
    max_consecutive_auto_reply: int = 5,
) -> UserProxyAgent:
    """Crée un UserProxyAgent (pilote la conversation, pas de LLM).

    L'exécution de code reste désactivée ici (code_execution_config=False) :
    elle sera activée dans un environnement Docker isolé lors de l'implémentation
    de l'agent Codeur (US 2.2 / Bug 3 du cahier des charges).
    """
    return UserProxyAgent(
        name=name,
        human_input_mode=human_input_mode,
        max_consecutive_auto_reply=max_consecutive_auto_reply,
        # "in" plutôt que "endswith" : le LLM ponctue parfois après TERMINATE
        # (ex: "TERMINATE."), ce qui faisait échouer un endswith() strict et
        # provoquait une boucle infinie de relances (cf. Bug 1 du cahier des charges).
        is_termination_msg=lambda msg: "TERMINATE" in str(msg.get("content", "")),
        code_execution_config=False,
    )


def get_conversation_history(agent: ConversableAgent, other_agent: ConversableAgent) -> List[Dict[str, Any]]:
    """Retourne l'historique des messages échangés entre deux agents."""
    return agent.chat_messages.get(other_agent, [])


def reset_conversation(*agents: ConversableAgent) -> None:
    """Réinitialise l'historique de conversation des agents donnés."""
    for agent in agents:
        agent.reset()
