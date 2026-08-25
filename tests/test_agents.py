from autogen import AssistantAgent, UserProxyAgent
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agents.base_agents import (
    create_assistant_agent,
    create_user_proxy_agent,
    get_conversation_history,
    reset_conversation,
)
from tests.fake_model_client import FakeModelClient, fake_llm_config


def make_assistant(reply_text: str = "Réponse simulée. TERMINATE") -> AssistantAgent:
    assistant = create_assistant_agent(llm_config=fake_llm_config(reply_text))
    assistant.register_model_client(model_client_cls=FakeModelClient)
    return assistant


# --- Classes d'agents définies et instanciables ---

def test_assistant_agent_is_instantiable():
    assistant = make_assistant()
    assert isinstance(assistant, AssistantAgent)
    assert assistant.name == "assistant"


def test_user_proxy_agent_is_instantiable():
    user_proxy = create_user_proxy_agent()
    assert isinstance(user_proxy, UserProxyAgent)
    assert user_proxy.name == "user_proxy"
    assert user_proxy.human_input_mode == "NEVER"
    assert user_proxy.llm_config is False


def test_agents_have_distinct_names_when_customized():
    assistant = create_assistant_agent(name="planificateur", llm_config=fake_llm_config())
    user_proxy = create_user_proxy_agent(name="orchestrateur")
    assert assistant.name == "planificateur"
    assert user_proxy.name == "orchestrateur"


# --- Pattern de communication bidirectionnel ---

def test_bidirectional_communication():
    assistant = make_assistant("Bien reçu, TERMINATE")
    user_proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)

    result = user_proxy.initiate_chat(assistant, message="Bonjour", max_turns=1)

    assert len(result.chat_history) == 2
    assert result.chat_history[0]["content"] == "Bonjour"
    assert "Bien reçu" in result.chat_history[1]["content"]

    fake_client = assistant.client._clients[0]
    assert isinstance(fake_client, FakeModelClient)
    assert fake_client.call_count == 1
    assert fake_client.received_messages[0][-1]["content"] == "Bonjour"


# --- Gestion des messages et de l'historique ---

def test_message_history_is_recorded_on_both_agents():
    assistant = make_assistant()
    user_proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)

    user_proxy.initiate_chat(assistant, message="Premier message", max_turns=1)

    history_from_user_proxy = get_conversation_history(user_proxy, assistant)
    history_from_assistant = get_conversation_history(assistant, user_proxy)

    assert len(history_from_user_proxy) == 2
    assert history_from_user_proxy[0]["content"] == "Premier message"
    # Chaque agent voit le rôle depuis son propre point de vue (assistant/user),
    # mais le contenu échangé doit être identique des deux côtés.
    contents_from_user_proxy = [m["content"] for m in history_from_user_proxy]
    contents_from_assistant = [m["content"] for m in history_from_assistant]
    assert contents_from_user_proxy == contents_from_assistant


def test_reset_conversation_clears_history():
    assistant = make_assistant()
    user_proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)

    user_proxy.initiate_chat(assistant, message="Un message", max_turns=1)
    assert len(get_conversation_history(user_proxy, assistant)) > 0

    reset_conversation(user_proxy, assistant)

    assert get_conversation_history(user_proxy, assistant) == []
    assert get_conversation_history(assistant, user_proxy) == []
