import contextvars
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

_trace_id_var: "contextvars.ContextVar[Optional[str]]" = contextvars.ContextVar("trace_id", default=None)


def new_trace_id() -> str:
    """Génère un identifiant de traçabilité court et lisible."""
    return uuid.uuid4().hex[:12]


def get_trace_id() -> Optional[str]:
    """Retourne l'identifiant de traçabilité de la requête en cours, ou None
    si aucun `trace_context()` n'est actif."""
    return _trace_id_var.get()


@contextmanager
def trace_context(trace_id: Optional[str] = None) -> Iterator[str]:
    """Définit un identifiant de traçabilité pour toute la durée du bloc : tous
    les logs émis pendant ce bloc (par n'importe quel agent) porteront cet
    identifiant, ce qui permet de retrouver tous les logs d'une même requête,
    même si elle est traitée par plusieurs agents en plusieurs étapes.

    Basé sur `contextvars` : chaque thread/tâche qui entre dans son propre
    `trace_context()` a son propre identifiant, sans interférence avec les
    autres requêtes traitées en parallèle (cf. test de charge, ticket 11).
    """
    token = _trace_id_var.set(trace_id or new_trace_id())
    try:
        yield _trace_id_var.get()
    finally:
        _trace_id_var.reset(token)
