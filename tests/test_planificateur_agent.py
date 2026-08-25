from autogen import AssistantAgent

from agents.planificateur_agent import PLANIFICATEUR_SYSTEM_MESSAGE, PlanificateurAgent
from tests.fake_model_client import FakeModelClient, fake_llm_config


def register_fake_client(agent: AssistantAgent) -> AssistantAgent:
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


def test_planificateur_agent_is_instantiable():
    agent = PlanificateurAgent(llm_config=fake_llm_config())
    assert isinstance(agent, PlanificateurAgent)
    assert isinstance(agent, AssistantAgent)
    assert agent.name == "planificateur"
    assert agent.system_message == PLANIFICATEUR_SYSTEM_MESSAGE


def test_planificateur_agent_accepts_custom_name():
    agent = PlanificateurAgent(name="chef_de_projet", llm_config=fake_llm_config())
    assert agent.name == "chef_de_projet"


def test_planificateur_produces_a_plan():
    planificateur = register_fake_client(
        PlanificateurAgent(llm_config=fake_llm_config("1. Étape un\n2. Étape deux\nTERMINATE"))
    )
    fake_client = planificateur.client._clients[0]
    reply = fake_client.create({"messages": [{"role": "user", "content": "Construis une API météo"}]})
    content = fake_client.message_retrieval(reply)[0]
    assert "Étape un" in content
