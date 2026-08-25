"""
Test manuel (non pytest) : valide la boucle autonome Codeur <-> Réviseur (US 2.2)
avec le vrai Azure OpenAI.
Usage: python scripts/smoke_test_code_review_loop.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.code_review_loop import run_code_review_loop

if __name__ == "__main__":
    plan = (
        "1. Écrire une fonction is_prime(n) qui détermine si un entier est premier.\n"
        "2. Gérer les cas limites (n < 2).\n"
        "3. Retourner un booléen."
    )

    result = run_code_review_loop(plan, max_rounds=5)

    print(f"\nApprouvé par le Réviseur : {result['approuve']}")
    print(f"Nombre d'échanges dans la boucle : {result['nombre_echanges']}")
    print("\n--- Code final ---")
    print(result["code_final"])
