"""
Tests d'intégration (US 11) : contrairement aux tests unitaires (qui isolent une
seule fonction/classe), ces tests font passer une demande à travers plusieurs
composants réels enchaînés — RoutingEngine, TaskDelegator, CommunicationLogger,
LoopDetector, ProgressiveSummaryTransform, GroupChatManager — exactement comme
en production. Seul l'appel LLM lui-même est simulé (FakeModelClient) : tout le
reste (routage, transformations de messages, hooks, boucles, export) est le vrai
code de production, pas des mocks.

20 scénarios couvrant les tickets 1 à 10.
"""
import json

import pytest

from agents.analyste_agent import AnalysteAgent
from agents.codeur_agent import CodeurAgent
from agents.orchestrator import build_orchestrator
from agents.planificateur_agent import PlanificateurAgent
from agents.reviseur_agent import ReviseurAgent
from protocol.consensus import collect_verdicts, resolve_consensus
from protocol.delegator import Task, TaskDelegator
from protocol.logger import CommunicationLogger
from protocol.router import ROUTE_ANALYSE, ROUTE_DEVELOPPEMENT, ROUTE_RECHERCHE, ROUTE_RECHERCHE_ET_ANALYSE
from protocol.routing_engine import RoutingEngine
from services.wikipedia_service import search_wikipedia
from tests.fake_model_client import fake_llm_config
from tests.test_routing_engine import make_agent, make_cycling_agent, make_team


# --- 1-4. RoutingEngine : les 4 chemins, bout en bout ---

def test_integration_recherche_only_end_to_end():
    recherche_team = make_team("Python est un langage. TERMINATE", name="recherche")
    engine = RoutingEngine(llm_config=fake_llm_config(), recherche_team_factory=lambda: recherche_team)

    result = engine.route("C'est quoi Python ?")

    assert result.route == ROUTE_RECHERCHE
    assert result.resultat_final
    assert result.approuve is None  # non applicable à ce chemin


def test_integration_analyse_only_end_to_end():
    analyse_team = make_team("### Rapport d'Analyse\nTERMINATE", name="analyse")
    engine = RoutingEngine(llm_config=fake_llm_config(), analyse_team_factory=lambda: analyse_team)

    result = engine.route("Analyse ces valeurs : 10, 20, 30.")

    assert result.route == ROUTE_ANALYSE
    assert "Rapport d'Analyse" in result.resultat_final


def test_integration_recherche_et_analyse_end_to_end():
    recherche_team = make_team("Infos HTTP. TERMINATE", name="recherche")
    analyse_team = make_team("Stats calculées. TERMINATE", name="analyse")
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        recherche_team_factory=lambda: recherche_team,
        analyse_team_factory=lambda: analyse_team,
    )

    result = engine.route("Recherche des infos sur HTTP et analyse ces temps : 10, 20, 30.")

    assert result.route == ROUTE_RECHERCHE_ET_ANALYSE
    assert "Infos HTTP" in result.resultat_final and "Stats calculées" in result.resultat_final


def test_integration_full_dev_chain_end_to_end():
    recherche_team = make_team("Contexte trouvé. TERMINATE", name="recherche")
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape\nTERMINATE"),
        codeur_factory=lambda: make_agent(CodeurAgent, "```python\nprint('hi')\n```"),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nTERMINATE"),
        reviseur_factory=lambda: make_agent(ReviseurAgent, "CODE_APPROUVE"),
    )

    result = engine.route("Écris une fonction Python qui affiche 'hello'.")

    assert result.route == ROUTE_DEVELOPPEMENT
    assert result.approuve is True
    assert [s.agent for s in result.steps] == ["recherche", "planificateur", "codeur", "analyse", "reviseur"]


# --- 5-6. Export : détection du format selon le contenu (comportement Streamlit) ---

def test_integration_export_detects_python_extension():
    recherche_team = make_team("Contexte. TERMINATE", name="recherche")
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape\nTERMINATE"),
        codeur_factory=lambda: make_agent(CodeurAgent, "```python\nprint('hi')\n```"),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nTERMINATE"),
        reviseur_factory=lambda: make_agent(ReviseurAgent, "CODE_APPROUVE"),
    )
    result = engine.route("Écris une fonction Python.")
    extension = "py" if "```python" in result.resultat_final else "txt"
    assert extension == "py"


def test_integration_export_defaults_to_txt_for_pure_text():
    recherche_team = make_team("Résumé en texte simple, aucun code. TERMINATE", name="recherche")
    engine = RoutingEngine(llm_config=fake_llm_config(), recherche_team_factory=lambda: recherche_team)
    result = engine.route("C'est quoi Python ?")
    extension = "py" if "```python" in result.resultat_final else "txt"
    assert extension == "txt"


# --- 7-8. CommunicationLogger intégré à une vraie chaîne ---

def test_integration_logger_captures_full_chain(tmp_path):
    log_path = str(tmp_path / "communications.jsonl")
    logger = CommunicationLogger(log_path=log_path)
    recherche_team = make_team("Contexte. TERMINATE", name="recherche")

    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        logger=logger,
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape\nTERMINATE"),
        codeur_factory=lambda: make_agent(CodeurAgent, "```python\nprint('hi')\n```"),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nTERMINATE"),
        reviseur_factory=lambda: make_agent(ReviseurAgent, "CODE_APPROUVE"),
    )
    engine.route("Écris une fonction Python.")

    entries = logger.read_all()
    assert len(entries) > 0
    senders = {e["from"] for e in entries}
    assert {"planificateur", "codeur", "reviseur"}.issubset(senders)
    # Le fichier doit être du JSONL valide, ligne par ligne.
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            json.loads(line)


def test_integration_logger_survives_codeur_retry_without_crashing(tmp_path):
    # Régression du bug "hook already registered" : le logger (comme le ui_hook)
    # doit pouvoir être attaché plusieurs fois au même agent réutilisé.
    log_path = str(tmp_path / "communications.jsonl")
    logger = CommunicationLogger(log_path=log_path)
    recherche_team = make_team("Contexte. TERMINATE", name="recherche")

    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        logger=logger,
        max_rounds=5,
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape\nTERMINATE"),
        codeur_factory=lambda: make_cycling_agent(CodeurAgent, ["```python\nv1\n```", "```python\nv2\n```"]),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nTERMINATE"),
        reviseur_factory=lambda: make_cycling_agent(ReviseurAgent, ["Corrige X.", "CODE_APPROUVE"]),
    )
    result = engine.route("Écris une fonction Python.")  # ne doit pas lever

    assert result.approuve is True
    assert len(logger.read_all()) > 0


# --- 9-13. TaskDelegator : chaque type de tâche + parallélisme ---

@pytest.mark.parametrize(
    "task_type,factory_key,reply",
    [
        ("plan", "agent_factories", "1. Étape\nTERMINATE"),
        ("code", "agent_factories", "```python\nprint('hi')\n```"),
        ("review", "agent_factories", "CODE_APPROUVE"),
    ],
)
def test_integration_delegator_simple_task_types(task_type, factory_key, reply):
    cls_by_type = {"plan": PlanificateurAgent, "code": CodeurAgent, "review": ReviseurAgent}
    agent = make_agent(cls_by_type[task_type], reply)
    delegator = TaskDelegator(agent_factories={task_type: lambda: agent})

    result = delegator.delegate(Task(type=task_type, message="Une tâche de test."))

    assert result.strip() != ""


def test_integration_delegator_recherche_and_analyse_team_types():
    recherche_team = make_team("Réponse recherche. TERMINATE", name="recherche")
    analyse_team = make_team("Réponse analyse. TERMINATE", name="analyse")
    delegator = TaskDelegator(
        team_factories={"recherche": lambda: recherche_team, "analyse": lambda: analyse_team}
    )

    r1 = delegator.delegate(Task(type="recherche", message="Qui est Ada Lovelace ?"))
    r2 = delegator.delegate(Task(type="analyse", message="Analyse.", data=[1, 2, 3]))

    assert "Réponse recherche" in r1
    assert "Réponse analyse" in r2


def test_integration_delegator_parallel_execution_preserves_order():
    reviseur_a = make_agent(ReviseurAgent, "CODE_APPROUVE")
    reviseur_b = make_agent(ReviseurAgent, "Corrige la ligne 3.")
    agents_iter = iter([reviseur_a, reviseur_b])
    delegator = TaskDelegator(agent_factories={"review": lambda: next(agents_iter)})

    results = delegator.delegate_many(
        [Task(type="review", message="print('a')"), Task(type="review", message="print('b')")]
    )

    assert results == ["CODE_APPROUVE", "Corrige la ligne 3."]


# --- 14-16. Consensus intégré à de vrais agents ---

def test_integration_consensus_unanimous_reject_no_arbitration_call():
    a = make_agent(ReviseurAgent, "Corrige X.")
    b = make_agent(ReviseurAgent, "Corrige Y aussi.")
    verdicts = collect_verdicts("print('test')", [a, b])
    result = resolve_consensus(verdicts)

    assert result["consensus"] is True
    assert result["decision"] == "rejete"
    assert result["arbitrage"] is None


def test_integration_consensus_conflict_triggers_real_arbitration_agent():
    a = make_agent(ReviseurAgent, "CODE_APPROUVE")
    b = make_agent(ReviseurAgent, "Corrige la gestion d'erreur.")
    arbitre = make_agent(ReviseurAgent, "Après vérification, CODE_APPROUVE.")

    verdicts = collect_verdicts("print('test')", [a, b])
    result = resolve_consensus(verdicts, arbitre=arbitre, task="print('test')")

    assert result["consensus"] is False
    assert result["decision"] == "approuve"
    assert "CODE_APPROUVE" in result["arbitrage"]


# --- 17-18. Orchestrateur (GroupChatManager) intégré ---

def test_integration_orchestrator_full_groupchat_flow():
    planificateur = make_agent(PlanificateurAgent, "1. Étape\nTERMINATE")
    codeur = make_agent(CodeurAgent, "```python\nprint('hi')\n```")
    reviseur = make_agent(ReviseurAgent, "CODE_APPROUVE")

    user_proxy, manager, loop_hook = build_orchestrator(
        llm_config=fake_llm_config(),
        planificateur=planificateur,
        codeur=codeur,
        reviseur=reviseur,
    )
    result = user_proxy.initiate_chat(manager, message="Écris une fonction Python.")

    assert any("CODE_APPROUVE" in str(m.get("content", "")) for m in result.chat_history)
    assert loop_hook.triggered is False


def test_integration_orchestrator_manager_ignores_planificateur_terminate():
    # Régression : le manager ne doit pas s'arrêter dès le "TERMINATE" du
    # Planificateur (qui en met un à chaque réponse par conception).
    planificateur = make_agent(PlanificateurAgent, "1. Étape\nTERMINATE")
    codeur = make_agent(CodeurAgent, "```python\nprint('hi')\n```")
    reviseur = make_agent(ReviseurAgent, "CODE_APPROUVE")

    user_proxy, manager, _ = build_orchestrator(
        llm_config=fake_llm_config(), planificateur=planificateur, codeur=codeur, reviseur=reviseur
    )
    result = user_proxy.initiate_chat(manager, message="Écris une fonction Python.")

    speakers = {m.get("name") for m in result.chat_history}
    assert {"planificateur", "codeur", "reviseur"}.issubset(speakers)


# --- 19. Service réel (réseau réel, gratuit, pas de clé nécessaire) ---

def test_integration_wikipedia_service_real_network_call():
    result = search_wikipedia("Python (langage)")
    assert result is not None
    assert result.title
    assert result.url.startswith("https://fr.wikipedia.org")


# --- 20. Router : bout en bout texte -> décision ---

@pytest.mark.parametrize(
    "demande,expected_route",
    [
        ("C'est quoi Python ?", ROUTE_RECHERCHE),
        ("Analyse ces valeurs : 1, 2, 3.", ROUTE_ANALYSE),
        ("Écris une fonction Python qui trie une liste.", ROUTE_DEVELOPPEMENT),
        ("Fais quelque chose d'utile.", ROUTE_DEVELOPPEMENT),
    ],
)
def test_integration_router_end_to_end_decision(demande, expected_route):
    from protocol.router import route_request

    assert route_request(demande).route == expected_route
