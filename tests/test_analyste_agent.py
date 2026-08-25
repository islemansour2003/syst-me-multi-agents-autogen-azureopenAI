from autogen import AssistantAgent, UserProxyAgent

from agents.analyste_agent import (
    AnalysteAgent,
    _detect_anomalies_tool,
    _get_statistics_tool,
    build_analyste_team,
)
from services.analysis_service import Anomaly
from tests.fake_model_client import fake_llm_config


# --- Agent instanciable ---

def test_analyste_agent_is_instantiable():
    agent = AnalysteAgent(llm_config=fake_llm_config())
    assert isinstance(agent, AnalysteAgent)
    assert isinstance(agent, AssistantAgent)
    assert agent.name == "analyste"


def test_analyste_agent_accepts_custom_name():
    agent = AnalysteAgent(name="data_analyst", llm_config=fake_llm_config())
    assert agent.name == "data_analyst"


# --- Extraction et structuration (outils exposés à l'agent) ---

def test_get_statistics_tool_delegates_to_service(monkeypatch):
    monkeypatch.setattr(
        "agents.analyste_agent.compute_statistics",
        lambda data: {"count": 3, "mean": 2.0, "median": 2, "min": 1, "max": 3, "stdev": 1.0},
    )
    result = _get_statistics_tool([1, 2, 3])
    assert result == {"count": 3, "mean": 2.0, "median": 2, "min": 1, "max": 3, "stdev": 1.0}


def test_detect_anomalies_tool_structures_result(monkeypatch):
    monkeypatch.setattr(
        "agents.analyste_agent.detect_anomalies",
        lambda data, threshold=2.0: [Anomaly(index=0, value=100, z_score=3.5)],
    )
    result = _detect_anomalies_tool([100, 1, 2])
    assert result == {"count": 1, "anomalies": [{"index": 0, "value": 100, "z_score": 3.5}]}


def test_detect_anomalies_tool_handles_no_anomalies(monkeypatch):
    monkeypatch.setattr("agents.analyste_agent.detect_anomalies", lambda data, threshold=2.0: [])
    result = _detect_anomalies_tool([1, 2, 3])
    assert result == {"count": 0, "anomalies": []}


# --- Outils enregistrés (pattern function-calling) ---

def test_build_analyste_team_registers_both_tools():
    assistant, executor = build_analyste_team(llm_config=fake_llm_config())

    assert isinstance(assistant, AssistantAgent)
    assert isinstance(executor, UserProxyAgent)

    assert "get_statistics" in executor.function_map
    assert "detect_anomalies" in executor.function_map

    tool_names = {tool["function"]["name"] for tool in assistant.llm_config["tools"]}
    assert {"get_statistics", "detect_anomalies"}.issubset(tool_names)
