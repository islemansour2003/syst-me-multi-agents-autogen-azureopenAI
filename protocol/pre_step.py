import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from protocol.delegator import Task, TaskDelegator


def normalize_text(texte: str) -> str:
    """Minuscules, sans accents, apostrophes/tirets remplacés par des espaces :
    rend la détection tolérante aux variantes courantes ("qu'est-ce que" vs
    "qu'est ce que" vs "quest-ce que", accents optionnels, etc.)."""
    texte = texte.lower()
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.replace("'", "").replace("-", " ")
    return re.sub(r"\s+", " ", texte).strip()


RECHERCHE_KEYWORDS = [
    normalize_text(mot)
    for mot in [
        "recherche",
        "wikipedia",
        "actualité",
        "actualités",
        "renseigne",
        "informe",
        "qu'est-ce que",
        "qui est",
        "définition",
        "définis",
        "c'est quoi",
        "c'est qui",
    ]
]
ANALYSE_KEYWORDS = [
    normalize_text(mot)
    for mot in [
        "analyse",
        "statistique",
        "statistiques",
        "anomalie",
        "anomalies",
        "moyenne",
        "tendance",
        "données",
    ]
]

NUMBER_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")
MIN_VALEURS_POUR_ANALYSE = 2


@dataclass
class DetectedNeeds:
    besoin_recherche: bool
    besoin_analyse: bool
    donnees_numeriques: Optional[List[float]]


def detect_needs(demande: str) -> DetectedNeeds:
    """Détecte, par mots-clés, si la demande nécessite une recherche web et/ou
    une analyse de données avant de lancer le pipeline de développement.

    Volontairement simple et déterministe (pas d'appel LLM) : rapide, gratuit,
    et testable sans mock — au prix de rater des formulations qui n'utilisent
    aucun des mots-clés attendus. La comparaison est tolérante aux accents,
    apostrophes et tirets (cf. `normalize_text`).
    """
    texte = normalize_text(demande)

    besoin_recherche = any(mot in texte for mot in RECHERCHE_KEYWORDS)
    besoin_analyse = any(mot in texte for mot in ANALYSE_KEYWORDS)

    donnees_numeriques = None
    if besoin_analyse:
        nombres = NUMBER_PATTERN.findall(demande)
        if len(nombres) >= MIN_VALEURS_POUR_ANALYSE:
            donnees_numeriques = [float(n.replace(",", ".")) for n in nombres]
        else:
            # Pas assez de valeurs exploitables : l'analyse n'aurait rien à traiter.
            besoin_analyse = False

    return DetectedNeeds(
        besoin_recherche=besoin_recherche,
        besoin_analyse=besoin_analyse,
        donnees_numeriques=donnees_numeriques,
    )


def run_pre_step(demande: str, delegator: TaskDelegator) -> Dict[str, Any]:
    """Exécute la pré-étape (US 8) : détecte les besoins, délègue à Recherche
    et/ou Analyste via le `TaskDelegator` (ticket 5) si nécessaire, avant que
    le pipeline Planificateur -> Codeur -> Réviseur ne démarre.
    """
    needs = detect_needs(demande)
    resultats: Dict[str, str] = {}

    if needs.besoin_recherche:
        resultats["recherche"] = delegator.delegate(Task(type="recherche", message=demande))

    if needs.besoin_analyse and needs.donnees_numeriques:
        resultats["analyse"] = delegator.delegate(
            Task(type="analyse", message=demande, data=needs.donnees_numeriques)
        )

    return {"needs": needs, "resultats": resultats}


def build_enriched_demande(demande: str, resultats: Dict[str, str]) -> str:
    """Construit la demande enrichie transmise au Planificateur : la demande
    originale, suivie du contexte obtenu de chaque pré-étape exécutée."""
    if not resultats:
        return demande

    contexte = "\n\n".join(f"[Contexte — {cle}]\n{valeur}" for cle, valeur in resultats.items())
    return f"{demande}\n\n{contexte}"
