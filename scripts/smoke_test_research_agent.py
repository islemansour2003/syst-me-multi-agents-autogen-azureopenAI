"""
Test manuel (non pytest) : valide l'agent Recherche avec les vraies APIs
(Wikipedia + NewsAPI) et le vrai Azure OpenAI, pas des mocks.
Usage: python scripts/smoke_test_research_agent.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.research_agent import ask_research_agent

if __name__ == "__main__":
    reponse = ask_research_agent(
        "Qui est Ada Lovelace, et y a-t-il des actualités récentes sur l'intelligence artificielle ?"
    )
    print("\n--- Résumé final de l'agent Recherche ---")
    print(reponse)
