"""
Test de charge (US 11) : 50 requêtes simultanées à travers le système complet
(RoutingEngine -> chaîne à 5 agents -> journalisation partagée).

Utilise FakeModelClient (pas le vrai Azure OpenAI) pour rester automatisé, gratuit
et déterministe : l'objectif ici est de vérifier la *correction* du système sous
charge concurrente (pas de plantage, pas de corruption du log partagé, pas de
fuite d'état entre requêtes) — pas la latence réelle d'Azure, qui dépend de leur
infrastructure et se mesure séparément (cf. scripts/load_test_real_azure.py,
en opt-in, hors suite automatisée car coûteux en tokens).
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.analyste_agent import AnalysteAgent
from agents.codeur_agent import CodeurAgent
from agents.planificateur_agent import PlanificateurAgent
from agents.reviseur_agent import ReviseurAgent
from protocol.logger import CommunicationLogger
from protocol.routing_engine import RoutingEngine
from tests.fake_model_client import fake_llm_config
from tests.test_routing_engine import make_agent, make_team

CONCURRENT_REQUESTS = 50


def _run_one_request(request_id: int, log_path: str):
    logger = CommunicationLogger(log_path=log_path)
    recherche_team = make_team(f"Contexte {request_id}. TERMINATE", name=f"recherche_{request_id}")

    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        logger=logger,
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, f"1. Étape {request_id}\nTERMINATE"),
        codeur_factory=lambda: make_agent(CodeurAgent, f"```python\nprint({request_id})\n```"),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nTERMINATE"),
        reviseur_factory=lambda: make_agent(ReviseurAgent, "CODE_APPROUVE"),
    )
    return engine.route(f"Écris une fonction Python numéro {request_id}.")


def test_load_50_concurrent_requests_all_succeed(tmp_path):
    log_path = str(tmp_path / "load_test.jsonl")

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        futures = [executor.submit(_run_one_request, i, log_path) for i in range(CONCURRENT_REQUESTS)]
        results = [f.result(timeout=60) for f in as_completed(futures)]
    elapsed = time.perf_counter() - start

    assert len(results) == CONCURRENT_REQUESTS
    assert all(r.approuve is True for r in results)
    assert all(r.route == "developpement" for r in results)

    print(
        f"\n{CONCURRENT_REQUESTS} requêtes concurrentes traitées en {elapsed:.2f}s "
        f"({CONCURRENT_REQUESTS / elapsed:.1f} req/s, exécution locale simulée)."
    )


def test_load_no_cross_request_contamination(tmp_path):
    # Chaque requête doit récupérer SON PROPRE code, pas celui d'une autre requête
    # exécutée en parallèle (pas de fuite d'état entre threads).
    log_path = str(tmp_path / "load_test.jsonl")

    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        futures = {executor.submit(_run_one_request, i, log_path): i for i in range(CONCURRENT_REQUESTS)}
        for future in as_completed(futures):
            request_id = futures[future]
            result = future.result(timeout=60)
            assert f"print({request_id})" in result.resultat_final


def test_load_communication_log_not_corrupted_under_concurrency(tmp_path):
    log_path = str(tmp_path / "load_test.jsonl")

    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        futures = [executor.submit(_run_one_request, i, log_path) for i in range(CONCURRENT_REQUESTS)]
        for future in as_completed(futures):
            future.result(timeout=60)

    with open(log_path, encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]

    assert len(lines) > 0
    for line in lines:
        json.loads(line)  # lève une exception si une ligne est corrompue/entrelacée

    # 50 requêtes x 5 agents (recherche, planificateur, codeur, analyse, reviseur)
    # = au moins 250 messages journalisés (executor interne de Recherche en ajoute
    # d'autres, donc "au moins", pas une égalité stricte).
    assert len(lines) >= CONCURRENT_REQUESTS * 5
