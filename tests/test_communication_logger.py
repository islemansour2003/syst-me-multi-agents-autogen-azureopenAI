import json

from agents.base_agents import create_user_proxy_agent
from agents.codeur_agent import CodeurAgent
from protocol.logger import CommunicationLogger
from protocol.tracing import trace_context
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


# --- Traçabilité (US 12) ---

def test_logger_records_trace_id_when_context_active(tmp_path):
    logger = CommunicationLogger(log_path=str(tmp_path / "communications.jsonl"), stdout_logging=False)
    codeur = CodeurAgent(llm_config=fake_llm_config("print('hi')"))
    codeur.register_model_client(model_client_cls=FakeModelClient)
    proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)
    logger.attach(codeur)
    logger.attach(proxy)

    with trace_context("trace-xyz"):
        proxy.initiate_chat(codeur, message="Écris une fonction", max_turns=1)

    entries = logger.read_all()
    assert all(e["trace_id"] == "trace-xyz" for e in entries)


def test_logger_records_none_trace_id_without_context(tmp_path):
    logger = CommunicationLogger(log_path=str(tmp_path / "communications.jsonl"), stdout_logging=False)
    codeur = CodeurAgent(llm_config=fake_llm_config("print('hi')"))
    codeur.register_model_client(model_client_cls=FakeModelClient)
    proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)
    logger.attach(codeur)
    logger.attach(proxy)

    proxy.initiate_chat(codeur, message="Écris une fonction", max_turns=1)

    entries = logger.read_all()
    assert all(e["trace_id"] is None for e in entries)


def test_find_by_trace_id_filters_to_matching_entries(tmp_path):
    logger = CommunicationLogger(log_path=str(tmp_path / "communications.jsonl"), stdout_logging=False)
    codeur = CodeurAgent(llm_config=fake_llm_config("print('hi')"))
    codeur.register_model_client(model_client_cls=FakeModelClient)
    proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)
    logger.attach(codeur)
    logger.attach(proxy)

    with trace_context("requete-1"):
        proxy.initiate_chat(codeur, message="Première requête", max_turns=1)
    with trace_context("requete-2"):
        proxy.initiate_chat(codeur, message="Deuxième requête", max_turns=1)

    entries_1 = logger.find_by_trace_id("requete-1")
    entries_2 = logger.find_by_trace_id("requete-2")

    assert len(entries_1) > 0
    assert all(e["trace_id"] == "requete-1" for e in entries_1)
    assert len(entries_2) > 0
    assert all(e["trace_id"] == "requete-2" for e in entries_2)
    assert logger.find_by_trace_id("inexistante") == []


# --- Logs structurés stdout (US 12) ---

def test_logger_emits_structured_json_to_stdout(capsys, tmp_path):
    logger = CommunicationLogger(log_path=str(tmp_path / "communications.jsonl"))
    codeur = CodeurAgent(llm_config=fake_llm_config("print('hi')"))
    codeur.register_model_client(model_client_cls=FakeModelClient)
    proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)
    logger.attach(codeur)
    logger.attach(proxy)

    with trace_context("trace-stdout"):
        proxy.initiate_chat(codeur, message="Écris une fonction", max_turns=1)

    captured = capsys.readouterr()
    json_lines = [line for line in captured.out.splitlines() if line.strip().startswith("{")]
    assert len(json_lines) > 0
    parsed = [json.loads(line) for line in json_lines]
    assert all(entry["trace_id"] == "trace-stdout" for entry in parsed)
    assert all("from" in entry and "to" in entry for entry in parsed)


def test_logger_stdout_logging_can_be_disabled(capsys, tmp_path):
    logger = CommunicationLogger(log_path=str(tmp_path / "communications.jsonl"), stdout_logging=False)
    codeur = CodeurAgent(llm_config=fake_llm_config("print('hi')"))
    codeur.register_model_client(model_client_cls=FakeModelClient)
    proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)
    logger.attach(codeur)
    logger.attach(proxy)

    proxy.initiate_chat(codeur, message="Écris une fonction", max_turns=1)

    captured = capsys.readouterr()
    assert not any(line.strip().startswith('{"timestamp"') for line in captured.out.splitlines())
