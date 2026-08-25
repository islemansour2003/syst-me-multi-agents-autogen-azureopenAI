"""
Test manuel (non pytest) : reproduit le scénario du bug (requête vague envoyée au
système) avec le vrai Azure OpenAI, et vérifie que le système gère la situation
proprement (convergence ou détection de boucle + demande de clarification),
sans jamais boucler indéfiniment.
Usage: python scripts/smoke_test_loop_detection.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.code_review_loop import run_code_review_loop

if __name__ == "__main__":
    # Plan volontairement vague, sans spécification technique concrète.
    plan_vague = "Fais quelque chose d'utile avec des données."

    result = run_code_review_loop(plan_vague, max_rounds=5)

    print(f"\nApprouvé : {result['approuve']}")
    print(f"Boucle détectée : {result['boucle_detectee']} (raison : {result['raison_boucle']})")
    print(f"Nombre d'échanges : {result['nombre_echanges']}")
    print("\n--- Dernier message échangé ---")
    print(result["historique"][-1]["content"])
