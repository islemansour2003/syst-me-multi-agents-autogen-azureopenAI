"""
Test de charge OPT-IN contre le vrai Azure OpenAI (US 11, critère "50 requêtes
simultanées"). Contrairement à tests/test_load.py (FakeModelClient, gratuit,
automatisé), ce script consomme de vrais tokens Azure — à lancer volontairement,
jamais dans la suite automatisée.

⚠️  Coût : N requêtes concurrentes en mode "recherche seule" (1 appel LLM chacune)
    = N appels facturés. Le mode par défaut est volontairement limité à 3.

Usage:
    python scripts/load_test_real_azure.py            # 3 requêtes (sûr par défaut)
    python scripts/load_test_real_azure.py --n 50      # 50 requêtes (le scénario du ticket)
"""
import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.research_agent import build_research_team
from protocol.logger import CommunicationLogger

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "load_test_real_azure.jsonl")


def _run_one(request_id: int, logger: CommunicationLogger) -> float:
    assistant, executor = build_research_team()
    logger.attach(assistant)
    logger.attach(executor)
    start = time.perf_counter()
    executor.initiate_chat(assistant, message=f"Qu'est-ce que le nombre premier {request_id * 2 + 3} ?")
    return time.perf_counter() - start


def main(n: int) -> None:
    print(f"⚠️  Lancement de {n} requêtes CONCURRENTES contre le vrai Azure OpenAI (coût réel).")
    if n > 10:
        print("    Ctrl+C dans les 5 prochaines secondes pour annuler...")
        time.sleep(5)

    logger = CommunicationLogger(log_path=LOG_PATH)
    latencies = []
    errors = []

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n) as executor_pool:
        futures = {executor_pool.submit(_run_one, i, logger): i for i in range(n)}
        for future in as_completed(futures):
            request_id = futures[future]
            try:
                latencies.append(future.result())
            except Exception as exc:  # noqa: BLE001
                errors.append((request_id, str(exc)))
    total_elapsed = time.perf_counter() - start

    print(f"\n{'=' * 60}\nRÉSULTATS — {n} requêtes concurrentes\n{'=' * 60}")
    print(f"Réussies      : {len(latencies)}/{n}")
    print(f"Échouées      : {len(errors)}")
    if errors:
        for request_id, err in errors[:5]:
            print(f"  - requête {request_id}: {err}")
    if latencies:
        latencies.sort()
        print(f"Latence min   : {latencies[0]:.2f}s")
        print(f"Latence médiane : {latencies[len(latencies) // 2]:.2f}s")
        print(f"Latence max   : {latencies[-1]:.2f}s")
    print(f"Temps total (mur) : {total_elapsed:.2f}s")
    print(f"Débit           : {len(latencies) / total_elapsed:.2f} req/s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3, help="Nombre de requêtes concurrentes (défaut : 3)")
    args = parser.parse_args()
    main(args.n)
