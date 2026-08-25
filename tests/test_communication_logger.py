from agents.base_agents import create_user_proxy_agent
from agents.codeur_agent import CodeurAgent
from protocol.logger import CommunicationLogger
from tests.fake_model_client import FakeModelClient, fake_llm_config


def test_logger_records_messages_sent_in_both_directions(tmp_path):
    log_path = tmp_path / "communications.jsonl"
    logger = CommunicationLogger(log_path=str(log_path))

    codeur = CodeurAgent(llm_config=fake_llm_config("print('hi')"))
    codeur.register_model_client(model_client_cls=FakeModelClient)
    proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)

    logger.attach(codeur)
    logger.attach(proxy)

    proxy.initiate_chat(codeur, message="Écris une fonction", max_turns=1)

    entries = logger.read_all()
    assert len(entries) == 2  # le message envoyé par le proxy + la réponse du codeur

    assert entries[0]["from"] == proxy.name
    assert entries[0]["to"] == codeur.name
    assert entries[0]["content"] == "Écris une fonction"
    assert "timestamp" in entries[0]

    assert entries[1]["from"] == codeur.name
    assert entries[1]["to"] == proxy.name
    assert "print" in entries[1]["content"]


def test_logger_creates_parent_directory(tmp_path):
    log_path = tmp_path / "nested" / "dir" / "communications.jsonl"
    CommunicationLogger(log_path=str(log_path))
    assert log_path.parent.exists()


def test_read_all_returns_empty_list_when_no_log_file(tmp_path):
    logger = CommunicationLogger(log_path=str(tmp_path / "nonexistent.jsonl"))
    assert logger.read_all() == []
