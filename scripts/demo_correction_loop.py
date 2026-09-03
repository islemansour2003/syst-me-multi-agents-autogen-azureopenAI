"""Démo visuelle de la boucle Codeur <-> Réviseur (US 2.2).

Rejoue, sans appel réseau (agents scriptés via CyclingFakeModelClient), un
scénario où le Réviseur rejette une première fois puis approuve, pour montrer
que la correction fonctionne réellement dans la chaîne RoutingEngine.
Utile pour une capture d'écran quand on n'a pas ou plus accès à Azure.

Lancer depuis la racine du projet :
    python scripts/demo_correction_loop.py
"""

import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from agents.analyste_agent import AnalysteAgent
from agents.codeur_agent import CodeurAgent
from agents.planificateur_agent import PlanificateurAgent
from agents.reviseur_agent import ReviseurAgent
from protocol.routing_engine import RoutingEngine
from tests.fake_model_client import fake_llm_config
from tests.test_routing_engine import make_agent, make_cycling_agent, make_team

ICONES = {
    "recherche": "🔎",
    "planificateur": "🗂️",
    "codeur": "💻",
    "analyse": "📊",
    "reviseur": "🔍",
}


def main() -> None:
    recherche_team = make_team("Contexte trouvé sur le sujet. TERMINATE", name="recherche")
    codeur = make_cycling_agent(
        CodeurAgent,
        [
            "```python\ndef diviser(a, b):\n    return a / b\n```",
            "```python\ndef diviser(a, b):\n    if b == 0:\n        raise ValueError(\"Division par zéro impossible\")\n    return a / b\n```",
        ],
    )
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        max_rounds=5,
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(
            PlanificateurAgent, "1. Écrire une fonction diviser(a, b).\nTERMINATE"
        ),
        codeur_factory=lambda: codeur,
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nCode cohérent avec le plan.\nTERMINATE"),
        reviseur_factory=lambda: make_cycling_agent(
            ReviseurAgent,
            ["Il manque une gestion d'erreur pour b == 0.", "CODE_APPROUVE"],
        ),
    )

    print("=" * 70)
    print("DEMO — Boucle de correction Codeur <-> Réviseur (US 2.2)")
    print("Demande : \"Écris une fonction Python qui divise deux nombres.\"")
    print("=" * 70)

    result = engine.route("Écris une fonction Python qui divise deux nombres.")

    for i, step in enumerate(result.steps, start=1):
        icone = ICONES.get(step.agent, "•")
        print(f"\n[{i}] {icone}  {step.agent.upper()}")
        print("-" * 70)
        print(step.content.strip())

    print("\n" + "=" * 70)
    print(f"Résultat final approuvé : {result.approuve}")
    print(f"Boucle infinie détectée : {result.boucle_detectee}")
    print(f"Trace ID : {result.trace_id}")
    print("=" * 70)


if __name__ == "__main__":
    main()
