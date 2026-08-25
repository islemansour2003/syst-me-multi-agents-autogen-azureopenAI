"""
Test manuel (non pytest) : valide l'agent Analyste avec le vrai Azure OpenAI,
sur des données contenant une anomalie volontaire.
Usage: python scripts/smoke_test_analyste_agent.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.analyste_agent import analyze_data

if __name__ == "__main__":
    # Températures journalières (°C) sur 10 jours, avec une lecture de capteur
    # visiblement défaillante (57.0) au milieu d'une série stable.
    temperatures = [21.5, 22.0, 21.8, 22.3, 57.0, 21.9, 22.1, 21.7, 22.4, 21.6]

    rapport = analyze_data(
        "Voici des relevés de température (°C) d'un capteur sur 10 jours consécutifs.",
        temperatures,
    )

    print("\n--- Rapport final de l'agent Analyste ---")
    print(rapport)
