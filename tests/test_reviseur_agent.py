from autogen import AssistantAgent

from agents.reviseur_agent import REVISEUR_SYSTEM_MESSAGE, ReviseurAgent
from tests.fake_model_client import FakeModelClient, fake_llm_config


def register_fake_client(agent: AssistantAgent) -> AssistantAgent:
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


def test_reviseur_agent_is_instantiable():
    agent = ReviseurAgent(llm_config=fake_llm_config())
    assert isinstance(agent, ReviseurAgent)
    assert isinstance(agent, AssistantAgent)
    assert agent.name == "reviseur"
    assert agent.system_message == REVISEUR_SYSTEM_MESSAGE


def test_reviseur_agent_accepts_custom_name():
    agent = ReviseurAgent(name="qa", llm_config=fake_llm_config())
    assert agent.name == "qa"


def test_reviseur_can_approve_code():
    reviseur = register_fake_client(
        ReviseurAgent(llm_config=fake_llm_config("CODE_APPROUVE"))
    )
    fake_client = reviseur.client._clients[0]
    reply = fake_client.create({"messages": [{"role": "user", "content": "print('hello')"}]})
    content = fake_client.message_retrieval(reply)[0]
    assert content == "CODE_APPROUVE"
