import pytest
from autogen import AssistantAgent

from agents.base_agents import create_user_proxy_agent
from agents.codeur_agent import CodeurAgent
from agents.planificateur_agent import PlanificateurAgent
from agents.reviseur_agent import ReviseurAgent
from protocol.delegator import Task, TaskDelegator, UnknownTaskTypeError
from tests.fake_model_client import FakeModelClient, fake_llm_config


def make_agent(cls, reply_text: str):
    agent = cls(llm_config=fake_llm_config(reply_text))
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


def make_team(reply_text: str):
    assistant = AssistantAgent(name="fake_assistant", llm_config=fake_llm_config(reply_text))
    assistant.register_model_client(model_client_cls=FakeModelClient)
    executor = create_user_proxy_agent(name="fake_executor", max_consecutive_auto_reply=1)
    return assistant, executor


# --- Types de tâches ---

def test_task_rejects_unknown_type():
    with pytest.raises(UnknownTaskTypeError):
        Task(type="inconnu", message="test")


# --- Délégation vers les agents simples (plan / code / review) ---

def test_delegate_plan_routes_to_planificateur():
    planificateur = make_agent(PlanificateurAgent, "1. Étape un\nTERMINATE")
    delegator = TaskDelegator(agent_factories={"plan": lambda: planificateur})
    result = delegator.delegate(Task(type="plan", message="Construis une API météo"))
    assert "Étape un" in result


def test_delegate_code_routes_to_codeur():
    codeur = make_agent(CodeurAgent, "```python\nprint('hi')\n```")
    delegator = TaskDelegator(agent_factories={"code": lambda: codeur})
    result = delegator.delegate(Task(type="code", message="1. Étape un"))
    assert "print" in result


def test_delegate_review_routes_to_reviseur():
    reviseur = make_agent(ReviseurAgent, "CODE_APPROUVE")
    delegator = TaskDelegator(agent_factories={"review": lambda: reviseur})
    result = delegator.delegate(Task(type="review", message="print('hi')"))
    assert result == "CODE_APPROUVE"


# --- Délégation vers les équipes outillées (recherche / analyse) ---

def test_delegate_recherche_uses_team_factory():
    assistant, executor = make_team("Résumé de recherche. TERMINATE")
    delegator = TaskDelegator(team_factories={"recherche": lambda: (assistant, executor)})
    result = delegator.delegate(Task(type="recherche", message="Qui est Ada Lovelace ?"))
    assert "Résumé de recherche" in result


def test_delegate_analyse_requires_data():
    delegator = TaskDelegator(team_factories={"analyse": lambda: (_ for _ in ()).throw(AssertionError("ne devrait pas être appelé"))})
    with pytest.raises(ValueError):
        delegator.delegate(Task(type="analyse", message="Analyse ces données"))


def test_delegate_analyse_uses_team_factory_when_data_provided():
    assistant, executor = make_team("### Rapport d'Analyse\nTERMINATE")
    delegator = TaskDelegator(team_factories={"analyse": lambda: (assistant, executor)})
    result = delegator.delegate(Task(type="analyse", message="Analyse ces valeurs", data=[1, 2, 3]))
    assert "Rapport d'Analyse" in result


# --- Délégation asynchrone (plusieurs tâches en parallèle) ---

def test_delegate_many_runs_all_tasks_and_preserves_order():
    reviseur_a = make_agent(ReviseurAgent, "CODE_APPROUVE")
    reviseur_b = make_agent(ReviseurAgent, "Corrige la ligne 3.")
    calls = iter([reviseur_a, reviseur_b])

    delegator = TaskDelegator(agent_factories={"review": lambda: next(calls)})
    tasks = [
        Task(type="review", message="print('a')"),
        Task(type="review", message="print('b')"),
    ]
    results = delegator.delegate_many(tasks)

    assert results == ["CODE_APPROUVE", "Corrige la ligne 3."]
