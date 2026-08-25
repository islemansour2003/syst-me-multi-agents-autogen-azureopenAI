from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from autogen import ConversableAgent

from agents.analyste_agent import AnalysteAgent, build_analyste_team
from agents.base_agents import create_user_proxy_agent
from agents.codeur_agent import CodeurAgent
from agents.planificateur_agent import PlanificateurAgent
from agents.research_agent import build_research_team
from agents.reviseur_agent import ReviseurAgent
from config.azure_config import get_llm_config
from protocol.logger import CommunicationLogger
from protocol.loop_detection import LoopDetectionHook
from protocol.router import (
    ROUTE_ANALYSE,
    ROUTE_DEVELOPPEMENT,
    ROUTE_RECHERCHE,
    ROUTE_RECHERCHE_ET_ANALYSE,
    route_request,
)

MAX_ROUNDS_DEFAULT = 5


@dataclass
class ChainStep:
    agent: str
    content: str


@dataclass
class RoutingResult:
    route: str
    steps: List[ChainStep] = field(default_factory=list)
    resultat_final: str = ""
    approuve: Optional[bool] = None
    boucle_detectee: bool = False
    raison_boucle: Optional[str] = None


class RoutingEngine:
    """Moteur de routage intelligent : décide, pour chaque demande, quel(s)
    agent(s) mobiliser, sans jamais forcer une simple question dans le pipeline
    de développement, ni sauter d'étape quand du code est effectivement demandé.

    - Demande purement informative -> agent Recherche seul.
    - Demande purement analytique -> agent Analyste seul (données numériques).
    - Demande d'information + de chiffres, sans code -> Recherche + Analyste.
    - Demande nécessitant du code -> chaîne séquentielle à 5 agents, où chaque
      agent reçoit réellement la sortie du précédent :
        1. Recherche     : rassemble le contexte utile à la demande.
        2. Planificateur : construit le plan EN UTILISANT ce contexte.
        3. Codeur        : génère le code EN SUIVANT ce plan.
        4. Analyse       : valide le code produit et rédige un rapport.
        5. Réviseur      : rend son verdict EN S'APPUYANT sur ce rapport.
      Étapes 3-5 rebouclent (US 2.2) : si le Réviseur rejette, le Codeur corrige
      en tenant compte du verdict et du rapport, l'Analyse est refaite sur le
      nouveau code, et le Réviseur relit — jusqu'à approbation, détection de
      boucle (Bug 1, avis du Réviseur qui se répète), ou `max_rounds` atteint.

    `*_factory` permettent d'injecter des agents déjà configurés (utile pour
    les tests) ; sinon ils sont créés avec `llm_config` (ou la config Azure
    par défaut).
    """

    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        ui_hook: Optional[Callable] = None,
        logger: Optional[CommunicationLogger] = None,
        max_rounds: int = MAX_ROUNDS_DEFAULT,
        similarity_threshold: float = 0.85,
        recherche_team_factory: Optional[Callable[[], Tuple[ConversableAgent, ConversableAgent]]] = None,
        analyse_team_factory: Optional[Callable[[], Tuple[ConversableAgent, ConversableAgent]]] = None,
        planificateur_factory: Optional[Callable[[], PlanificateurAgent]] = None,
        codeur_factory: Optional[Callable[[], CodeurAgent]] = None,
        analyste_factory: Optional[Callable[[], AnalysteAgent]] = None,
        reviseur_factory: Optional[Callable[[], ReviseurAgent]] = None,
    ) -> None:
        self.llm_config = llm_config or get_llm_config()
        self.ui_hook = ui_hook
        self.logger = logger
        self.max_rounds = max_rounds
        self.similarity_threshold = similarity_threshold

        self._recherche_team_factory = recherche_team_factory or (
            lambda: build_research_team(llm_config=self.llm_config)
        )
        self._analyse_team_factory = analyse_team_factory or (
            lambda: build_analyste_team(llm_config=self.llm_config)
        )
        self._planificateur_factory = planificateur_factory or (
            lambda: PlanificateurAgent(llm_config=self.llm_config)
        )
        self._codeur_factory = codeur_factory or (lambda: CodeurAgent(llm_config=self.llm_config))
        self._analyste_factory = analyste_factory or (lambda: AnalysteAgent(llm_config=self.llm_config))
        self._reviseur_factory = reviseur_factory or (lambda: ReviseurAgent(llm_config=self.llm_config))

    def _attach(self, *agents: Any) -> None:
        for agent in agents:
            if self.logger is not None:
                self.logger.attach(agent)
            if self.ui_hook is not None:
                # Idempotent : un agent (ex: le Codeur) peut être réutilisé sur
                # plusieurs tours de la boucle de correction, et se faire passer
                # plusieurs fois à _attach() — AutoGen refuse d'enregistrer deux
                # fois le même hook sur un agent.
                hooks = agent.hook_lists.get("process_message_before_send", [])
                if self.ui_hook not in hooks:
                    agent.register_hook("process_message_before_send", self.ui_hook)

    def _one_shot(self, agent: ConversableAgent, message: str) -> str:
        self._attach(agent)
        proxy = create_user_proxy_agent(name=f"proxy_{agent.name}", max_consecutive_auto_reply=1)
        self._attach(proxy)
        result = proxy.initiate_chat(agent, message=message, max_turns=1)
        return result.chat_history[-1]["content"] if result.chat_history else ""

    # --- Point d'entrée ---

    def route(self, demande: str) -> RoutingResult:
        decision = route_request(demande)

        if decision.route == ROUTE_RECHERCHE:
            return self._run_recherche_only(demande)
        if decision.route == ROUTE_ANALYSE:
            return self._run_analyse_only(demande, decision.needs.donnees_numeriques)
        if decision.route == ROUTE_RECHERCHE_ET_ANALYSE:
            return self._run_recherche_et_analyse(demande, decision.needs.donnees_numeriques)
        return self._run_full_chain(demande)

    # --- Raccourcis (pas de code demandé) ---

    def _run_recherche_only(self, demande: str) -> RoutingResult:
        assistant, executor = self._recherche_team_factory()
        self._attach(assistant, executor)
        result = executor.initiate_chat(assistant, message=demande)
        contenu = result.chat_history[-1]["content"] if result.chat_history else ""
        return RoutingResult(route=ROUTE_RECHERCHE, steps=[ChainStep("recherche", contenu)], resultat_final=contenu)

    def _run_analyse_only(self, demande: str, data: Optional[List[float]]) -> RoutingResult:
        assistant, executor = self._analyse_team_factory()
        self._attach(assistant, executor)
        message = f"{demande}\n\nDonnées : {data}"
        result = executor.initiate_chat(assistant, message=message)
        contenu = result.chat_history[-1]["content"] if result.chat_history else ""
        return RoutingResult(route=ROUTE_ANALYSE, steps=[ChainStep("analyse", contenu)], resultat_final=contenu)

    def _run_recherche_et_analyse(self, demande: str, data: Optional[List[float]]) -> RoutingResult:
        recherche = self._run_recherche_only(demande)
        analyse = self._run_analyse_only(demande, data)
        return RoutingResult(
            route=ROUTE_RECHERCHE_ET_ANALYSE,
            steps=recherche.steps + analyse.steps,
            resultat_final=f"{recherche.resultat_final}\n\n---\n\n{analyse.resultat_final}",
        )

    # --- Chaîne complète (code demandé) ---

    def _run_full_chain(self, demande: str) -> RoutingResult:
        steps: List[ChainStep] = []

        # 1. Recherche : rassemble le contexte utile à la demande.
        assistant_r, executor_r = self._recherche_team_factory()
        self._attach(assistant_r, executor_r)
        result_r = executor_r.initiate_chat(assistant_r, message=demande)
        info_recherche = result_r.chat_history[-1]["content"] if result_r.chat_history else ""
        steps.append(ChainStep("recherche", info_recherche))

        # 2. Planificateur : construit le plan EN UTILISANT les infos de Recherche.
        planificateur = self._planificateur_factory()
        message_plan = f"{demande}\n\n[Informations trouvées par l'agent Recherche]\n{info_recherche}"
        plan = self._one_shot(planificateur, message_plan)
        steps.append(ChainStep("planificateur", plan))

        # 3. Codeur : premier jet de code EN SUIVANT le plan du Planificateur.
        codeur = self._codeur_factory()
        code = self._one_shot(codeur, f"Voici le plan à implémenter :\n\n{plan}")
        steps.append(ChainStep("codeur", code))

        # 4-5. Boucle Analyse -> Réviseur -> (Codeur si rejeté), cf. US 2.2 :
        # les agents interagissent de manière autonome jusqu'à approbation, ou
        # jusqu'à ce qu'une boucle soit détectée (Bug 1), ou max_rounds atteint.
        reviseur = self._reviseur_factory()
        loop_hook = LoopDetectionHook(max_rounds=self.max_rounds, similarity_threshold=self.similarity_threshold)
        reviseur.register_hook("process_message_before_send", loop_hook)
        self._attach(reviseur)

        approuve = False
        verdict = ""

        for round_num in range(self.max_rounds):
            # Analyse : valide le code (courant à ce tour) et rédige un rapport.
            analyste = self._analyste_factory()
            message_analyse = (
                "Il n'y a pas de données numériques ici : ignore les outils "
                "get_statistics et detect_anomalies (non disponibles dans ce "
                "contexte) et applique directement ton raisonnement en chaîne "
                "pour évaluer la qualité et la correction du code suivant, puis "
                f"rédige ton rapport habituel :\n\n{code}"
            )
            rapport_analyse = self._one_shot(analyste, message_analyse)
            steps.append(ChainStep("analyse", rapport_analyse))

            # Réviseur : rend son verdict EN S'APPUYANT sur le rapport d'Analyse.
            message_revue = (
                f"Voici le code à relire :\n\n{code}\n\n"
                f"[Rapport de l'agent Analyste]\n{rapport_analyse}\n\n"
                "Tiens compte de ce rapport pour ta décision finale."
            )
            proxy = create_user_proxy_agent(name=f"proxy_reviseur_{round_num}", max_consecutive_auto_reply=1)
            self._attach(proxy)
            result = proxy.initiate_chat(reviseur, message=message_revue, max_turns=1)
            verdict = result.chat_history[-1]["content"] if result.chat_history else ""
            steps.append(ChainStep("reviseur", verdict))

            if loop_hook.triggered or "CODE_APPROUVE" in verdict:
                approuve = "CODE_APPROUVE" in verdict and not loop_hook.triggered
                break

            # Rejeté : le Codeur corrige en tenant compte du verdict du Réviseur.
            message_correction = (
                f"Voici le code précédent :\n\n{code}\n\n"
                f"Retours du Réviseur à corriger :\n{verdict}\n\n"
                "Corrige le code en conséquence."
            )
            code = self._one_shot(codeur, message_correction)
            steps.append(ChainStep("codeur", code))

        return RoutingResult(
            route=ROUTE_DEVELOPPEMENT,
            steps=steps,
            resultat_final=code,
            approuve=approuve,
            boucle_detectee=loop_hook.triggered,
            raison_boucle=loop_hook.reason,
        )
