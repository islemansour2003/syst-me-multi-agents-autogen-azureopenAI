from autogen import AssistantAgent

from agents.codeur_agent import CODEUR_SYSTEM_MESSAGE, CodeurAgent
from tests.fake_model_client import FakeModelClient, fake_llm_config


def register_fake_client(agent: AssistantAgent) -> AssistantAgent:
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


def test_codeur_agent_is_instantiable():
    agent = CodeurAgent(llm_config=fake_llm_config())
    assert isinstance(agent, CodeurAgent)
    assert isinstance(agent, AssistantAgent)
    assert agent.name == "codeur"
    assert agent.system_message == CODEUR_SYSTEM_MESSAGE


def test_codeur_agent_accepts_custom_name():
    agent = CodeurAgent(name="dev", llm_config=fake_llm_config())
    assert agent.name == "dev"


def test_codeur_produces_code():
    codeur = register_fake_client(
        CodeurAgent(llm_config=fake_llm_config("```python\nprint('hello')\n```"))
    )
    fake_client = codeur.client._clients[0]
    reply = fake_client.create({"messages": [{"role": "user", "content": "1. Étape un"}]})
    content = fake_client.message_retrieval(reply)[0]
    assert "print" in content
