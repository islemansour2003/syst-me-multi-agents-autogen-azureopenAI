import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from protocol.tracing import get_trace_id


class JsonFormatter(logging.Formatter):
    """Formate chaque log en une ligne JSON — le format que les systèmes de
    logs centralisés (Azure Log Analytics, etc.) savent parser et indexer
    automatiquement, contrairement à du texte libre."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        trace_id = get_trace_id()
        if trace_id:
            payload["trace_id"] = trace_id
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload, ensure_ascii=False)


class _StdoutHandler(logging.StreamHandler):
    """StreamHandler qui résout sys.stdout à chaque émission plutôt qu'une
    seule fois à la création. Le logger est mis en cache globalement (voir
    ci-dessous), donc son handler est créé une seule fois pour tout le
    process — s'il capturait `sys.stdout` une fois pour toutes, un
    remplacement ultérieur de `sys.stdout` (ex: capsys/capfd de pytest, qui
    redirigent la sortie test par test) ne serait plus vu."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def get_structured_logger(name: str = "multiagents") -> logging.Logger:
    """Logger qui écrit du JSON structuré sur stdout.

    C'est le pattern standard pour une application conteneurisée (12-factor
    app) : on n'essaie pas d'envoyer les logs soi-même vers un service cloud —
    on les écrit sur stdout, et c'est la plateforme d'hébergement (ex: Azure
    Container Apps) qui les capture et les centralise automatiquement dans
    Log Analytics. Zéro changement de code nécessaire lors du déploiement.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:  # évite les handlers en double si appelé plusieurs fois
        handler = _StdoutHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
