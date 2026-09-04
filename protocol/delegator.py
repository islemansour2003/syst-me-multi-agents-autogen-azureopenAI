import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from autogen import ConversableAgent

from agents.analyste_agent import build_analyste_team
from agents.base_agents import create_user_proxy_agent
from agents.codeur_agent import CodeurAgent
from agents.planificateur_agent import PlanificateurAgent
from agents.research_agent import build_research_team
from agents.reviseur_agent import ReviseurAgent
from protocol.logger import CommunicationLogger

TASK_TYPES = {"plan", "code", "review", "recherche", "analyse"}
SIMPLE_TASK_TYPES = {"plan", "code", "review"}
TEAM_TASK_TYPES = {"recherche", "analyse"}


class UnknownTaskTypeError(ValueError):
    """Levée quand un Task porte un type non pris en charge par le délégateur."""


@dataclass
class Task:
    type: str
    message: str
    data: Optional[List[float]] = None  # utilisé uniquement pour le type "analyse"

    def __post_init__(self) -> None:
        if self.type not in TASK_TYPES:
            raise UnknownTaskTypeError(
                f"Type de tâche inconnu : {self.type!r}. Types valides : {sorted(TASK_TYPES)}"
            )


class TaskDelegator:
    """Système de délégation de tâches : route chaque tâche vers l'agent spécialisé
    compétent (US 5), en synchrone ou en asynchrone (plusieurs délégations en parallèle).

    `agent_factories`/`team_factories` permettent d'injecter des agents déjà construits
    (utile pour les tests, ou pour réutiliser des instances) à la place des agents réels
    par défaut.
    """

    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        logger: Optional[CommunicationLogger] = None,
        agent_factories: Optional[Dict[str, Callable[[], ConversableAgent]]] = None,
        team_factories: Optional[Dict[str, Callable[[], Tuple[ConversableAgent, ConversableAgent]]]] = None,
        ui_hook: Optional[Callable] = None,
    ) -> None:
        # Résolu paresseusement : chaque Agent (ou team builder) applique déjà
        # `llm_config or get_llm_config()` dans son propre constructeur, donc
        # get_llm_config() (qui exige les vraies variables Azure) n'est appelé
        # que si une factory par défaut est réellement invoquée — pas si
        # agent_factories/team_factories couvre déjà le type de tâche utilisé.
        self.llm_config = llm_config
        self.logger = logger
        self.ui_hook = ui_hook

        self._agent_factories: Dict[str, Callable[[], ConversableAgent]] = {
            "plan": lambda: PlanificateurAgent(llm_config=self.llm_config),
            "code": lambda: CodeurAgent(llm_config=self.llm_config),
            "review": lambda: ReviseurAgent(llm_config=self.llm_config),
        }
        if agent_factories:
            self._agent_factories.update(agent_factories)

        self._team_factories: Dict[str, Callable[[], Tuple[ConversableAgent, ConversableAgent]]] = {
            "recherche": lambda: build_research_team(llm_config=self.llm_config),
            "analyse": lambda: build_analyste_team(llm_config=self.llm_config),
        }
        if team_factories:
            self._team_factories.update(team_factories)

    def _attach_extras(self, *agents: Any) -> None:
        if self.logger is not None:
            for agent in agents:
                self.logger.attach(agent)
        if self.ui_hook is not None:
            for agent in agents:
                # Idempotent : évite une double registration si un agent est
                # réutilisé sur plusieurs délégations (AutoGen refuse d'enregistrer
                # deux fois le même hook sur un agent).
                hooks = agent.hook_lists.get("process_message_before_send", [])
                if self.ui_hook not in hooks:
                    agent.register_hook("process_message_before_send", self.ui_hook)

    def delegate(self, task: Task) -> str:
        """Délègue une tâche et attend sa résolution (synchrone)."""
        if task.type in TEAM_TASK_TYPES:
            message = task.message
            if task.type == "analyse":
                if task.data is None:
                    raise ValueError("Une tâche 'analyse' nécessite des données (task.data).")
                message = f"{task.message}\n\nDonnées : {task.data}"
            assistant, executor = self._team_factories[task.type]()
            self._attach_extras(assistant, executor)
            result = executor.initiate_chat(assistant, message=message)
            return result.chat_history[-1]["content"]

        agent = self._agent_factories[task.type]()
        proxy = create_user_proxy_agent(name=f"delegator_{task.type}", max_consecutive_auto_reply=1)
        self._attach_extras(agent, proxy)
        result = proxy.initiate_chat(agent, message=task.message, max_turns=1)
        return result.chat_history[-1]["content"]

    async def delegate_async(self, task: Task) -> str:
        """Délègue une tâche de façon asynchrone (utilisable avec asyncio.gather)."""
        if task.type in TEAM_TASK_TYPES:
            message = task.message
            if task.type == "analyse":
                if task.data is None:
                    raise ValueError("Une tâche 'analyse' nécessite des données (task.data).")
                message = f"{task.message}\n\nDonnées : {task.data}"
            assistant, executor = self._team_factories[task.type]()
            self._attach_extras(assistant, executor)
            result = await executor.a_initiate_chat(assistant, message=message)
            return result.chat_history[-1]["content"]

        agent = self._agent_factories[task.type]()
        proxy = create_user_proxy_agent(name=f"delegator_{task.type}", max_consecutive_auto_reply=1)
        self._attach_extras(agent, proxy)
        result = await proxy.a_initiate_chat(agent, message=task.message, max_turns=1)
        return result.chat_history[-1]["content"]

    async def delegate_many_async(self, tasks: List[Task]) -> List[str]:
        """Délègue plusieurs tâches en parallèle (protocole de messagerie asynchrone)."""
        return await asyncio.gather(*(self.delegate_async(t) for t in tasks))

    def delegate_many(self, tasks: List[Task]) -> List[str]:
        """Variante synchrone pratique de delegate_many_async (bloque jusqu'à la fin)."""
        return asyncio.run(self.delegate_many_async(tasks))
