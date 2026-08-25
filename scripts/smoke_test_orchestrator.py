"""
Test manuel (non pytest) : valide l'agent orchestrateur (GroupChatManager, US 6)
avec le vrai Azure OpenAI — Planificateur -> Codeur -> Réviseur coordonnés
automatiquement, avec dashboard de monitoring en sortie.
Usage: python scripts/smoke_test_orchestrator.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator import run_orchestrated_task

if __name__ == "__main__":
    result = run_orchestrated_task(
        "Écris une fonction Python qui vérifie si une chaîne de caractères est un palindrome.",
        max_round=10,
    )

    print("\n" + result["report"].render())

    print("\n--- Résultat final ---")
    print(result["resultat_final"])
