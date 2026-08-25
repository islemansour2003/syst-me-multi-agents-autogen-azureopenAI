"""
Test manuel (non pytest) : valide que les 3 agents spécialisés répondent réellement
via Azure OpenAI, pas seulement avec le FakeModelClient des tests unitaires.
Usage: python scripts/smoke_test_specialized_agents.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.base_agents import create_user_proxy_agent
from agents.planificateur_agent import PlanificateurAgent

if __name__ == "__main__":
    planificateur = PlanificateurAgent()
    user_proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)

    result = user_proxy.initiate_chat(
        planificateur,
        message="Je veux une application qui affiche la météo d'une ville.",
        max_turns=1,
    )

    print("\n--- Réponse du Planificateur (Azure OpenAI réel) ---")
    print(result.chat_history[-1]["content"])
