from dataclasses import dataclass

from protocol.pre_step import DetectedNeeds, detect_needs, normalize_text

CODE_KEYWORDS = [
    normalize_text(mot)
    for mot in [
        "écris",
        "crée",
        "créer",
        "implémente",
        "code",
        "fonction",
        "programme",
        "corrige",
        "développe",
        "développement",
        "script",
        "classe",
        "algorithme",
        "bug",
        "erreur",
        "refactor",
        "optimise",
        "teste",
        "génère",
    ]
]

# Routes possibles.
ROUTE_RECHERCHE = "recherche"
ROUTE_ANALYSE = "analyse"
ROUTE_RECHERCHE_ET_ANALYSE = "recherche_et_analyse"
ROUTE_DEVELOPPEMENT = "developpement"


@dataclass
class RoutingDecision:
    route: str
    needs: DetectedNeeds
    needs_code: bool


def route_request(demande: str) -> RoutingDecision:
    """Décide comment traiter la demande, avant de lancer quoi que ce soit :

    - Si la demande réclame explicitement du code (mots-clés type "écris",
      "corrige", "fonction"...), ou si rien de spécifique n'est détecté :
      pipeline complet Planificateur -> Codeur -> Réviseur (US 6), avec
      pré-étape Recherche/Analyste en amont si en plus détectée (US 8).
    - Sinon, si la demande est purement informative (recherche et/ou analyse
      détectées, mais pas de code demandé) : on interroge directement le(s)
      agent(s) concerné(s) et on s'arrête là — pas de Codeur/Réviseur, qui
      n'ont rien à faire d'une simple question de définition ou de chiffres.

    Toujours déterministe (mots-clés, pas d'appel LLM) : rapide, gratuit,
    testable sans mock.
    """
    needs = detect_needs(demande)
    texte = normalize_text(demande)
    needs_code = any(mot in texte for mot in CODE_KEYWORDS)

    if needs_code or (not needs.besoin_recherche and not needs.besoin_analyse):
        route = ROUTE_DEVELOPPEMENT
    elif needs.besoin_recherche and needs.besoin_analyse:
        route = ROUTE_RECHERCHE_ET_ANALYSE
    elif needs.besoin_recherche:
        route = ROUTE_RECHERCHE
    else:
        route = ROUTE_ANALYSE

    return RoutingDecision(route=route, needs=needs, needs_code=needs_code)
