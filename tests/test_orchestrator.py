from agents.codeur_agent import CodeurAgent
from agents.orchestrator import (
    MonitoringReport,
    _manager_is_terminal,
    build_orchestrator,
    run_orchestrated_task,
)
from agents.planificateur_agent import PlanificateurAgent
from agents.reviseur_agent import ReviseurAgent
from tests.fake_model_client import FakeModelClient, fake_llm_config


def make_planificateur(reply_text: str) -> PlanificateurAgent:
    agent = PlanificateurAgent(llm_config=fake_llm_config(reply_text))
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


def make_codeur(reply_text: str) -> CodeurAgent:
    agent = CodeurAgent(llm_config=fake_llm_config(reply_text))
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


def make_reviseur(reply_text: str) -> ReviseurAgent:
    agent = ReviseurAgent(llm_config=fake_llm_config(reply_text))
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


# --- Règles de terminaison du manager ---

def test_manager_does_not_stop_on_plain_terminate():
    # Le Planificateur termine toujours par TERMINATE : ça ne doit pas arrêter
    # tout le GroupChat après sa seule première étape.
    assert _manager_is_terminal({"content": "1. Étape un\nTERMINATE"}) is False


def test_manager_stops_on_code_approuve():
    assert _manager_is_terminal({"content": "CODE_APPROUVE"}) is True


def test_manager_stops_on_clarification_marker():
    assert _manager_is_terminal({"content": "CLARIFICATION_REQUISE\n\n...TERMINATE"}) is True


# --- Construction ---

def test_build_orchestrator_wires_all_agents():
    user_proxy, manager, loop_hook = build_orchestrator(
        llm_config=fake_llm_config(),
        planificateur=make_planificateur("plan"),
        codeur=make_codeur("code"),
        reviseur=make_reviseur("CODE_APPROUVE"),
    )
    agent_names = {a.name for a in manager.groupchat.agents}
    assert agent_names == {"utilisateur", "planificateur", "codeur", "reviseur"}
    assert loop_hook.triggered is False


def test_build_orchestrator_registers_ui_hook_on_all_agents():
    calls = []

    def ui_hook(sender, message, recipient, silent):
        calls.append(sender.name)
        return message

    user_proxy, manager, _ = build_orchestrator(
        llm_config=fake_llm_config(),
        planificateur=make_planificateur("plan"),
        codeur=make_codeur("code"),
        reviseur=make_reviseur("CODE_APPROUVE"),
        ui_hook=ui_hook,
    )
    for agent in manager.groupchat.agents:
        assert ui_hook in agent.hook_lists["process_message_before_send"]


# --- Exécution complète (bout en bout, mockée) ---

def test_run_orchestrated_task_approves_on_first_pass(tmp_path):
    result = run_orchestrated_task(
        "Écris une fonction utilitaire.",
        llm_config=fake_llm_config(),
        max_round=10,
        log_path=str(tmp_path / "communications.jsonl"),
        planificateur=make_planificateur("1. Étape un\nTERMINATE"),
        codeur=make_codeur("```python\nprint('hi')\n```"),
        reviseur=make_reviseur("CODE_APPROUVE"),
    )

    assert result["report"].outcome == "approuve"
    assert result["report"].error is None
    speakers = [e.speaker for e in result["report"].events]
    assert "planificateur" in speakers
    assert "codeur" in speakers
    assert "reviseur" in speakers
    assert "CODE_APPROUVE" in result["resultat_final"]


def test_run_orchestrated_task_detects_loop(tmp_path):
    result = run_orchestrated_task(
        "Écris une fonction utilitaire.",
        llm_config=fake_llm_config(),
        max_round=10,
        log_path=str(tmp_path / "communications.jsonl"),
        planificateur=make_planificateur("1. Étape un\nTERMINATE"),
        codeur=make_codeur("```python\nprint('hi')\n```"),
        # Le Réviseur redonne mot pour mot le même avis à chaque tour.
        reviseur=make_reviseur("Il manque une gestion d'erreur pour b == 0."),
    )

    assert result["report"].outcome == "boucle_detectee"
    assert "CLARIFICATION_REQUISE" in result["resultat_final"]


def test_run_orchestrated_task_captures_errors_gracefully(tmp_path):
    class BrokenCodeur(CodeurAgent):
        def generate_reply(self, *args, **kwargs):
            raise RuntimeError("Panne API simulée")

    result = run_orchestrated_task(
        "Écris une fonction utilitaire.",
        llm_config=fake_llm_config(),
        max_round=10,
        log_path=str(tmp_path / "communications.jsonl"),
        planificateur=make_planificateur("1. Étape un\nTERMINATE"),
        codeur=BrokenCodeur(llm_config=fake_llm_config("code")),
        reviseur=make_reviseur("CODE_APPROUVE"),
    )

    assert result["report"].outcome == "erreur"
    assert "Panne API simulée" in result["report"].error
    assert result["chat_history"] == []


# --- Dashboard de monitoring ---

def test_monitoring_report_to_dict_and_render():
    report = MonitoringReport(started_at="t0", ended_at="t1", outcome="approuve")
    data = report.to_dict()
    assert data["outcome"] == "approuve"
    assert data["nombre_tours"] == 0
    assert "Dashboard" in report.render()
