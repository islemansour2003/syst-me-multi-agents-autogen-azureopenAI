import statistics
from dataclasses import asdict, dataclass
from typing import Any, Dict, List


@dataclass
class Anomaly:
    index: int
    value: float
    z_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_statistics(data: List[float]) -> Dict[str, Any]:
    """Calcule les statistiques descriptives d'une série de valeurs numériques."""
    if not data:
        raise ValueError("La liste de données est vide.")
    return {
        "count": len(data),
        "mean": statistics.fmean(data),
        "median": statistics.median(data),
        "min": min(data),
        "max": max(data),
        "stdev": statistics.pstdev(data) if len(data) > 1 else 0.0,
    }


def detect_anomalies(data: List[float], threshold: float = 2.0) -> List[Anomaly]:
    """Détecte les valeurs aberrantes via la méthode du z-score (écarts-types par rapport à la moyenne).

    Retourne une liste vide si les données sont trop courtes ou sans variance
    (pas d'écart-type => pas de notion d'aberration).
    """
    if len(data) < 2:
        return []
    mean = statistics.fmean(data)
    stdev = statistics.pstdev(data)
    if stdev == 0:
        return []

    anomalies = []
    for index, value in enumerate(data):
        z_score = (value - mean) / stdev
        if abs(z_score) >= threshold:
            anomalies.append(Anomaly(index=index, value=value, z_score=round(z_score, 2)))
    return anomalies
