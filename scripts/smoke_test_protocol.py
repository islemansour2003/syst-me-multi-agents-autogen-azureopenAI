"""
Test manuel (non pytest) : valide le protocole de communication inter-agents (US 5)
avec le vrai Azure OpenAI :
- délégation asynchrone de plusieurs tâches en parallèle (timing comparé) ;
- journalisation de toutes les communications dans logs/communications.jsonl ;
- consensus/conflit entre 2 agents Réviseur indépendants, avec arbitrage.

Usage: python scripts/smoke_test_protocol.py
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.reviseur_agent import ReviseurAgent
from protocol.consensus import collect_verdicts, resolve_consensus
from protocol.delegator import Task, TaskDelegator
from protocol.logger import CommunicationLogger

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "communications.jsonl")


def demo_delegation_asynchrone():
    print("\n" + "=" * 70)
    print("1. DÉLÉGATION ASYNCHRONE (2 tâches en parallèle)")
    print("=" * 70)

    logger = CommunicationLogger(log_path=LOG_PATH)
    delegator = TaskDelegator(logger=logger)

    tasks = [
        Task(type="recherche", message="Qu'est-ce que le protocole HTTP ?"),
        Task(type="analyse", message="Voici des temps de réponse serveur (ms).", data=[120, 118, 125, 480, 122]),
    ]

    start = time.perf_counter()
    results = delegator.delegate_many(tasks)
    elapsed_parallel = time.perf_counter() - start

    print(f"\n2 tâches délégation en parallèle : {elapsed_parallel:.1f}s")
    print(f"\n[Résultat recherche] {results[0][:200]}...")
    print(f"\n[Résultat analyse]  {results[1][:200]}...")
    return logger


def demo_logging(logger: CommunicationLogger):
    print("\n" + "=" * 70)
    print("2. LOGGING DES COMMUNICATIONS")
    print("=" * 70)
    entries = logger.read_all()
    print(f"\n{len(entries)} messages journalisés dans {LOG_PATH}")
    for entry in entries[:4]:
        print(f"  [{entry['timestamp']}] {entry['from']} -> {entry['to']} : {str(entry['content'])[:80]}")
    print("  ...")


def demo_consensus():
    print("\n" + "=" * 70)
    print("3. CONSENSUS / CONFLIT ENTRE AGENTS")
    print("=" * 70)

    code_a_revoir = """def diviser(a, b):
    return a / b
"""

    reviseur_1 = ReviseurAgent(name="reviseur_strict")
    reviseur_2 = ReviseurAgent(name="reviseur_permissif")

    verdicts = collect_verdicts(f"Voici le code à relire :\n\n{code_a_revoir}", [reviseur_1, reviseur_2])
    for v in verdicts:
        print(f"\n[{v.agent_name}] approuvé={v.approved}\n{v.content[:300]}")

    arbitre = ReviseurAgent(name="arbitre")
    resultat = resolve_consensus(
        verdicts,
        arbitre=arbitre,
        task=f"Voici le code à relire :\n\n{code_a_revoir}",
    )

    print(f"\nConsensus atteint sans arbitrage : {resultat['consensus']}")
    print(f"Décision finale : {resultat['decision']}")
    if resultat["arbitrage"]:
        print(f"\n[Arbitrage]\n{resultat['arbitrage'][:300]}")


if __name__ == "__main__":
    logger = demo_delegation_asynchrone()
    demo_logging(logger)
    demo_consensus()
