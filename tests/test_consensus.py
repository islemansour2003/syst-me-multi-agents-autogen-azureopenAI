import pytest

from agents.reviseur_agent import ReviseurAgent
from protocol.consensus import Verdict, collect_verdicts, resolve_consensus
from tests.fake_model_client import FakeModelClient, fake_llm_config


def make_reviseur(reply_text: str, name: str = "reviseur") -> ReviseurAgent:
    agent = ReviseurAgent(name=name, llm_config=fake_llm_config(reply_text))
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


def test_collect_verdicts_marks_approval_correctly():
    a = make_reviseur("CODE_APPROUVE", name="reviseur_a")
    b = make_reviseur("Il manque une gestion d'erreur.", name="reviseur_b")

    verdicts = collect_verdicts("print('hi')", [a, b])

    assert len(verdicts) == 2
    assert verdicts[0].agent_name == "reviseur_a"
    assert verdicts[0].approved is True
    assert verdicts[1].agent_name == "reviseur_b"
    assert verdicts[1].approved is False


def test_resolve_consensus_unanimous_approve():
    verdicts = [Verdict("a", "CODE_APPROUVE", True), Verdict("b", "CODE_APPROUVE", True)]
    result = resolve_consensus(verdicts)
    assert result["consensus"] is True
    assert result["decision"] == "approuve"
    assert result["arbitrage"] is None


def test_resolve_consensus_unanimous_reject():
    verdicts = [Verdict("a", "Corrige X", False), Verdict("b", "Corrige Y", False)]
    result = resolve_consensus(verdicts)
    assert result["consensus"] is True
    assert result["decision"] == "rejete"


def test_resolve_consensus_conflict_without_arbitre_defaults_to_reject():
    verdicts = [Verdict("a", "CODE_APPROUVE", True), Verdict("b", "Corrige X", False)]
    result = resolve_consensus(verdicts)
    assert result["consensus"] is False
    assert result["decision"] == "rejete"
    assert result["arbitrage"] is None


def test_resolve_consensus_conflict_with_arbitre_resolves():
    verdicts = [Verdict("a", "CODE_APPROUVE", True), Verdict("b", "Corrige X", False)]
    arbitre = make_reviseur("Après vérification, CODE_APPROUVE.", name="arbitre")

    result = resolve_consensus(verdicts, arbitre=arbitre, task="print('hi')")

    assert result["consensus"] is False
    assert result["decision"] == "approuve"
    assert "CODE_APPROUVE" in result["arbitrage"]


def test_resolve_consensus_raises_on_empty_verdicts():
    with pytest.raises(ValueError):
        resolve_consensus([])
