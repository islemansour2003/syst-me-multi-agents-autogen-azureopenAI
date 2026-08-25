
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from autogen import Agent, GroupChat, GroupChatManager
from openai import APITimeoutError

from agents.base_agents import create_user_proxy_agent
from agents.codeur_agent import CodeurAgent
from agents.planificateur_agent import PlanificateurAgent
from agents.reviseur_agent import ReviseurAgent
from config.azure_config import get_llm_config
from protocol.logger import DEFAULT_LOG_PATH, CommunicationLogger
from protocol.loop_detection import CLARIFICATION_MARKER, LoopDetectionHook
from protocol.memory import attach_memory_management

MAX_ROUND_DEFAULT = 10


def _manager_is_terminal(msg: Dict[str, Any]) -> bool:
    # NB: on ne teste pas "TERMINATE" ici — le Planificateur en met un à chaque
    # réponse (fin de son propre tour), ce qui arrêterait le GroupChat après la
    # toute première étape si on le testait au niveau du manager.
    content = str(msg.get("content", ""))
    return "CODE_APPROUVE" in content or CLARIFICATION_MARKER in content


@dataclass
class SpeakerEvent:
    round_index: int
    speaker: str
    timestamp: str
    content_preview: str


@dataclass
class MonitoringReport:
    """Dashboard de monitoring des interactions (US 6) : qui a parlé, quand,
    et comment la conversation s'est terminée."""

    started_at: str
    ended_at: Optional[str] = None
    events: List[SpeakerEvent] = field(default_factory=list)
    outcome: Optional[str] = None  # "approuve" | "boucle_detectee" | "max_round_atteint" | "timeout" | "erreur"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "outcome": self.outcome,
            "error": self.error,
            "nombre_tours": len(self.events),
            "sequence_agents": [e.speaker for e in self.events],
        }

    def render(self) -> str:
        lignes = [
            "=== Dashboard de monitoring ===",
            f"Début    : {self.started_at}",
            f"Fin      : {self.ended_at}",
            f"Résultat : {self.outcome}",
            f"Tours    : {len(self.events)}",
            "",
            f"{'Tour':<5}{'Agent':<16}Aperçu du message",
            "-" * 70,
        ]
        for e in self.events:
            lignes.append(f"{e.round_index:<5}{e.speaker:<16}{e.content_preview}")
        if self.error:
            lignes.append(f"\nErreur : {self.error}")
        return "\n".join(lignes)


def build_orchestrator(
    llm_config: Optional[Dict[str, Any]] = None,
    max_round: int = MAX_ROUND_DEFAULT,
    logger: Optional[CommunicationLogger] = None,
    user_proxy: Optional[Agent] = None,
    planificateur: Optional[PlanificateurAgent] = None,
    codeur: Optional[CodeurAgent] = None,
    reviseur: Optional[ReviseurAgent] = None,
    ui_hook: Optional[Callable] = None,
) -> Tuple[Agent, GroupChatManager, LoopDetectionHook]:
    """Construit le GroupChat + GroupChatManager orchestrant Planificateur, Codeur
    et Réviseur (US 3.1 / ticket 6 : "agent orchestrateur").

    Règles de routing : fonction déterministe (pas de sélection "auto" laissée au
    LLM du manager) — user_proxy -> planificateur -> codeur -> reviseur, puis
    reviseur <-> codeur en boucle jusqu'à approbation, détection de boucle
    (LoopDetectionHook, cf. Bug 1), ou max_round atteint.

    `user_proxy`/`planificateur`/`codeur`/`reviseur` permettent d'injecter des
    instances déjà configurées (utile pour les tests) ; sinon ils sont créés
    avec `llm_config` (ou la config Azure par défaut).

    `ui_hook` (signature identique à un hook `process_message_before_send`) est
    attaché à chaque agent en plus du logger : utilisé par l'interface Streamlit
    (US 3.2) pour afficher les échanges en temps réel, sans dupliquer la logique
    d'orchestration.
    """
    config = llm_config or get_llm_config()

    user_proxy = user_proxy or create_user_proxy_agent(name="utilisateur", max_consecutive_auto_reply=1)
    planificateur = planificateur or PlanificateurAgent(llm_config=config)
    codeur = codeur or CodeurAgent(llm_config=config)
    reviseur = reviseur or ReviseurAgent(llm_config=config)

    loop_hook = LoopDetectionHook(max_rounds=max_round)
    reviseur.register_hook("process_message_before_send", loop_hook)

    # Perte de contexte sur les longs échanges (Bug 7) : au-delà de 10 messages
    # dans le GroupChat, les plus anciens sont résumés au lieu d'être perdus.
    for participant in (planificateur, codeur, reviseur):
        attach_memory_management(participant, max_messages=10, keep_recent=6)

    agents = [user_proxy, planificateur, codeur, reviseur]
    if logger:
        for agent in agents:
            logger.attach(agent)
    if ui_hook:
        for agent in agents:
            # Idempotent : un agent injecté (tests, réutilisation) pourrait déjà
            # porter ce hook — AutoGen refuse de l'enregistrer une 2e fois.
            hooks = agent.hook_lists.get("process_message_before_send", [])
            if ui_hook not in hooks:
                agent.register_hook("process_message_before_send", ui_hook)

    def route_next_speaker(last_speaker: Agent, groupchat: GroupChat):
        """Sélection automatique de l'agent suivant (US 6, critère 2)."""
        if last_speaker is user_proxy:
            return planificateur
        if last_speaker is planificateur:
            return codeur
        if last_speaker is codeur:
            return reviseur
        if last_speaker is reviseur:
            # Si le Réviseur avait approuvé ou déclenché une clarification, le
            # GroupChatManager aurait déjà arrêté la conversation avant d'appeler
            # cette fonction (cf. _manager_is_terminal) : on n'arrive ici que
            # lorsqu'il demande une correction, donc retour au Codeur.
            return codeur
        return None

    group_chat = GroupChat(
        agents=agents,
        messages=[],
        max_round=max_round,
        speaker_selection_method=route_next_speaker,
        allow_repeat_speaker=False,
    )
    manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=config,
        is_termination_msg=_manager_is_terminal,
    )

    return user_proxy, manager, loop_hook


def run_orchestrated_task(
    demande: str,
    llm_config: Optional[Dict[str, Any]] = None,
    max_round: int = MAX_ROUND_DEFAULT,
    log_path: str = DEFAULT_LOG_PATH,
    user_proxy: Optional[Agent] = None,
    planificateur: Optional[PlanificateurAgent] = None,
    codeur: Optional[CodeurAgent] = None,
    reviseur: Optional[ReviseurAgent] = None,
    ui_hook: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Lance une tâche à travers l'orchestrateur (GroupChatManager) et retourne
    à la fois le résultat et un rapport de monitoring (US 6, critère "dashboard").

    Gestion des erreurs/timeouts (US 6, critère 3) : toute erreur d'appel LLM
    (dont les timeouts, cf. `LLM_TIMEOUT_SECONDS` dans la config Azure) est
    capturée pour retourner un rapport exploitable plutôt que de laisser planter
    l'appelant.
    """
    logger = CommunicationLogger(log_path=log_path)
    entries_avant = len(logger.read_all())
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        user_proxy, manager, loop_hook = build_orchestrator(
            llm_config=llm_config,
            max_round=max_round,
            logger=logger,
            user_proxy=user_proxy,
            planificateur=planificateur,
            codeur=codeur,
            reviseur=reviseur,
            ui_hook=ui_hook,
        )
        result = user_proxy.initiate_chat(manager, message=demande)
    except APITimeoutError as exc:
        report = MonitoringReport(
            started_at=started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            outcome="timeout",
            error=str(exc),
        )
        return {"report": report, "chat_history": [], "resultat_final": None}
    except Exception as exc:  # noqa: BLE001 - on veut capturer toute erreur d'appel LLM
        report = MonitoringReport(
            started_at=started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            outcome="erreur",
            error=str(exc),
        )
        return {"report": report, "chat_history": [], "resultat_final": None}

    ended_at = datetime.now(timezone.utc).isoformat()

    nouvelles_entrees = logger.read_all()[entries_avant:]
    events = [
        SpeakerEvent(
            round_index=i,
            speaker=e["from"],
            timestamp=e["timestamp"],
            content_preview=str(e["content"])[:80],
        )
        for i, e in enumerate(nouvelles_entrees)
    ]

    if loop_hook.triggered:
        outcome = "boucle_detectee"
    elif any("CODE_APPROUVE" in str(m.get("content", "")) for m in result.chat_history):
        outcome = "approuve"
    elif len(result.chat_history) >= max_round:
        outcome = "max_round_atteint"
    else:
        outcome = "termine"

    report = MonitoringReport(started_at=started_at, ended_at=ended_at, events=events, outcome=outcome)

    return {
        "report": report,
        "chat_history": result.chat_history,
        "resultat_final": result.chat_history[-1]["content"] if result.chat_history else None,
    }
