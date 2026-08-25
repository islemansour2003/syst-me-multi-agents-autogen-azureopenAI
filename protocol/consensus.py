from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from autogen import ConversableAgent

from agents.base_agents import create_user_proxy_agent


@dataclass
class Verdict:
    agent_name: str
    content: str
    approved: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def collect_verdicts(
    task: str,
    agents: List[ConversableAgent],
    approval_keyword: str = "CODE_APPROUVE",
) -> List[Verdict]:
    """Envoie la même tâche à plusieurs agents, indépendamment les uns des autres,
    et recueille leurs verdicts respectifs."""
    verdicts = []
    for agent in agents:
        proxy = create_user_proxy_agent(name=f"consensus_{agent.name}", max_consecutive_auto_reply=1)
        result = proxy.initiate_chat(agent, message=task, max_turns=1)
        content = result.chat_history[-1]["content"]
        verdicts.append(Verdict(agent_name=agent.name, content=content, approved=approval_keyword in content))
    return verdicts


def resolve_consensus(
    verdicts: List[Verdict],
    arbitre: Optional[ConversableAgent] = None,
    task: Optional[str] = None,
    approval_keyword: str = "CODE_APPROUVE",
) -> Dict[str, Any]:
    """Détermine s'il y a consensus entre les verdicts, et résout le conflit sinon.

    - Unanimité (tous approuvent, ou tous rejettent) => consensus direct.
    - Avis partagés => conflit :
        - si un `arbitre` (et la `task` d'origine) sont fournis, on lui soumet les
          avis divergents pour trancher ;
        - sinon la décision par défaut est "rejete" (position prudente : en cas de
          doute non résolu, ne pas approuver — cf. Bug 3 du cahier des charges).
    """
    if not verdicts:
        raise ValueError("Aucun verdict à résoudre.")

    approvals = [v.approved for v in verdicts]
    unanimous_approve = all(approvals)
    unanimous_reject = not any(approvals)

    if unanimous_approve or unanimous_reject:
        return {
            "consensus": True,
            "decision": "approuve" if unanimous_approve else "rejete",
            "verdicts": [v.to_dict() for v in verdicts],
            "arbitrage": None,
        }

    decision = "rejete"
    arbitrage = None
    if arbitre is not None and task is not None:
        avis_resume = "\n".join(
            f"- {v.agent_name} : {'APPROUVE' if v.approved else 'REJETE'} — {v.content}" for v in verdicts
        )
        proxy = create_user_proxy_agent(name="arbitre_proxy", max_consecutive_auto_reply=1)
        result = proxy.initiate_chat(
            arbitre,
            message=(
                f"Les avis suivants sont en conflit sur la tâche : {task}\n\n{avis_resume}\n\n"
                f"Tranche : réponds par {approval_keyword} si tu approuves, sinon explique pourquoi tu rejettes."
            ),
            max_turns=1,
        )
        arbitrage = result.chat_history[-1]["content"]
        decision = "approuve" if approval_keyword in arbitrage else "rejete"

    return {
        "consensus": False,
        "decision": decision,
        "verdicts": [v.to_dict() for v in verdicts],
        "arbitrage": arbitrage,
    }
