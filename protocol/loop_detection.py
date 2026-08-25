import difflib
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LoopStatus:
    loop_detected: bool
    reason: Optional[str]  # "repetition" | "max_rounds" | None
    round_reached: int


class LoopDetector:
    """Détecte les échanges qui stagnent entre agents : soit parce qu'un agent
    répète un message quasi identique à son message précédent (pas de nouvelle
    information, signe qu'ils se renvoient la tâche sans converger), soit parce
    que le nombre maximum de rounds est atteint.
    """

    def __init__(self, max_rounds: int, similarity_threshold: float = 0.85):
        self.max_rounds = max_rounds
        self.similarity_threshold = similarity_threshold
        self._last_by_speaker: Dict[str, str] = {}
        self._round = 0

    def observe(self, speaker: str, content: str) -> LoopStatus:
        self._round += 1
        previous = self._last_by_speaker.get(speaker)
        self._last_by_speaker[speaker] = content

        if previous is not None:
            ratio = difflib.SequenceMatcher(None, previous, content).ratio()
            if ratio >= self.similarity_threshold:
                return LoopStatus(True, "repetition", self._round)

        if self._round >= self.max_rounds:
            return LoopStatus(True, "max_rounds", self._round)

        return LoopStatus(False, None, self._round)


CLARIFICATION_MARKER = "CLARIFICATION_REQUISE"


def build_clarification_message(reason: str) -> str:
    if reason == "repetition":
        explication = (
            "les agents se renvoient des messages quasi identiques sans faire "
            "progresser la tâche (aucune nouvelle information d'un round à l'autre)"
        )
    else:
        explication = "le nombre maximum d'itérations a été atteint sans convergence"

    return (
        f"{CLARIFICATION_MARKER}\n\n"
        f"La conversation ne converge pas ({explication}). "
        "Merci de reformuler ou de préciser la demande initiale pour débloquer "
        "l'échange.\n\nTERMINATE"
    )


class LoopDetectionHook:
    """Hook AutoGen (`process_message_before_send`) : observe chaque message
    envoyé par l'agent auquel il est attaché, et remplace le message par une
    demande de clarification dès qu'une boucle est détectée — au lieu de
    laisser la conversation continuer jusqu'à épuisement du plafond de rounds.
    """

    def __init__(self, max_rounds: int, similarity_threshold: float = 0.85):
        self.detector = LoopDetector(max_rounds=max_rounds, similarity_threshold=similarity_threshold)
        self.triggered = False
        self.reason: Optional[str] = None
        self.round_reached: Optional[int] = None

    def __call__(self, sender: Any, message: Any, recipient: Any, silent: bool) -> Any:
        if self.triggered:
            return message

        content = message.get("content") if isinstance(message, dict) else message
        status = self.detector.observe(getattr(sender, "name", str(sender)), content or "")

        if status.loop_detected:
            self.triggered = True
            self.reason = status.reason
            self.round_reached = status.round_reached
            clarification = build_clarification_message(status.reason)
            if isinstance(message, dict):
                return {**message, "content": clarification}
            return clarification

        return message
