"""Vérification rapide en direct (vrai Azure OpenAI) du Réviseur durci."""

import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from protocol.routing_engine import RoutingEngine

ICONES = {
    "recherche": "\U0001f50e",
    "planificateur": "\U0001f5c2",
    "codeur": "\U0001f4bb",
    "analyse": "\U0001f4ca",
    "reviseur": "\U0001f50d",
}


def main() -> None:
    engine = RoutingEngine(max_rounds=3)
    demande = (
        "Écris une fonction Python nommée diviser qui prend deux nombres et "
        "retourne leur division, en gérant le cas où le diviseur est zéro en "
        "levant une ValueError avec le message exact \"Division par zéro "
        "impossible\", et gère aussi le cas où les entrées ne sont pas des "
        "nombres en levant un TypeError."
    )
    result = engine.route(demande)

    for i, step in enumerate(result.steps, start=1):
        icone = ICONES.get(step.agent, "-")
        print(f"\n[{i}] {icone} {step.agent.upper()}")
        print("-" * 70)
        print(step.content.strip())

    print("\n" + "=" * 70)
    print(f"Approuvé : {result.approuve} | Boucle détectée : {result.boucle_detectee}")
    print("=" * 70)


if __name__ == "__main__":
    main()
