from typing import Any, Dict, Optional

from agents.base_agents import create_user_proxy_agent
from agents.codeur_agent import CodeurAgent
from agents.reviseur_agent import ReviseurAgent
from config.azure_config import get_llm_config
from protocol.loop_detection import LoopDetectionHook
from protocol.memory import attach_memory_management

MAX_ROUNDS_DEFAULT = 5


def _is_terminal(msg: Dict[str, Any]) -> bool:
    content = str(msg.get("content", ""))
    return "CODE_APPROUVE" in content or "TERMINATE" in content


def run_code_review_loop(
    plan: str,
    max_rounds: int = MAX_ROUNDS_DEFAULT,
    llm_config: Optional[Dict[str, Any]] = None,
    codeur: Optional[CodeurAgent] = None,
    reviseur: Optional[ReviseurAgent] = None,
    similarity_threshold: float = 0.85,
) -> Dict[str, Any]:
    """Fait interagir Codeur et Réviseur de manière autonome (US 2.2) : le Réviseur
    relit le code du Codeur et propose des corrections, jusqu'à ce qu'il l'approuve
    (CODE_APPROUVE), qu'une boucle soit détectée, ou que max_rounds soit atteint.

    Conversation directe à 2 agents (initiate_chat), pas de GroupChat : ce dernier
    est un ticket séparé (US 3.1), utile à partir de 3+ agents coordonnés par un manager.

    Détection de boucle (Bug 1) : si le Réviseur répète un avis quasi identique
    d'un round à l'autre (signe que le Codeur ne fait pas progresser le code, par
    exemple à cause d'une demande initiale trop vague), l'échange est interrompu
    et remplacé par une demande de clarification au lieu de continuer jusqu'à
    épuisement de max_rounds. On observe uniquement les messages du Réviseur (pas
    ceux du Codeur) : comparer des extraits de code par similarité de texte donne
    de faux positifs, un correctif minime restant très proche du code d'origine.

    Perte de contexte sur les longs échanges (Bug 7) : au-delà de 10 messages,
    les plus anciens sont résumés progressivement plutôt que de dégrader la
    qualité des réponses ou de dépasser la fenêtre de contexte du modèle.

    `codeur`/`reviseur` permettent d'injecter des instances déjà configurées
    (utile pour les tests) ; sinon ils sont créés avec `llm_config` (ou la config
    Azure par défaut).
    """
    config = llm_config or get_llm_config()

    codeur = codeur or CodeurAgent(
        llm_config=config,
        max_consecutive_auto_reply=max_rounds,
        # Le Codeur reçoit les messages du Réviseur : il s'arrête si celui-ci approuve,
        # ou si une demande de clarification (TERMINATE) est déclenchée par le hook.
        is_termination_msg=_is_terminal,
    )
    reviseur = reviseur or ReviseurAgent(
        llm_config=config,
        max_consecutive_auto_reply=max_rounds,
    )

    loop_hook = LoopDetectionHook(max_rounds=max_rounds, similarity_threshold=similarity_threshold)
    reviseur.register_hook("process_message_before_send", loop_hook)

    # Perte de contexte sur les longs échanges (Bug 7) : au-delà de 10 messages,
    # les plus anciens sont résumés au lieu d'être tronqués ou de grossir sans limite.
    attach_memory_management(codeur, max_messages=10, keep_recent=6)
    attach_memory_management(reviseur, max_messages=10, keep_recent=6)

    # Phase 1 : premier jet de code à partir du plan (appel simple, hors boucle).
    kickoff_proxy = create_user_proxy_agent(name="kickoff", max_consecutive_auto_reply=1)
    kickoff_result = kickoff_proxy.initiate_chat(
        codeur,
        message=f"Voici le plan à implémenter :\n\n{plan}",
        max_turns=1,
    )
    premier_code = kickoff_result.chat_history[-1]["content"]

    # Phase 2 : boucle autonome Codeur <-> Réviseur.
    review_result = codeur.initiate_chat(reviseur, message=premier_code)
    historique = review_result.chat_history

    approuve = (
        any("CODE_APPROUVE" in str(m.get("content", "")) for m in historique)
        and not loop_hook.triggered
    )
    # Dans l'historique vu par le Codeur, ses propres messages ont le rôle "assistant" :
    # le dernier est donc la dernière version de code qu'il a proposée.
    dernier_code = next(
        (m["content"] for m in reversed(historique) if m.get("role") == "assistant"),
        premier_code,
    )

    return {
        "plan": plan,
        "premier_code": premier_code,
        "code_final": dernier_code,
        "approuve": approuve,
        "nombre_echanges": len(historique),
        "historique": historique,
        "boucle_detectee": loop_hook.triggered,
        "raison_boucle": loop_hook.reason,
    }
