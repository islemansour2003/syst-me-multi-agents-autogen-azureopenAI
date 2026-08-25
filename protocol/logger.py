import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

DEFAULT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "communications.jsonl")

# Un verrou par fichier (chemin absolu), partagé entre toutes les instances de
# CommunicationLogger qui pointent vers le même fichier — nécessaire car sous
# charge (US 11 : 50 requêtes simultanées), chaque requête crée généralement sa
# propre instance de logger, mais elles écrivent toutes dans le même fichier.
# Sans ce verrou, des écritures concurrentes s'entrelacent et corrompent le JSONL.
_write_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for_path(path: str) -> threading.Lock:
    abs_path = os.path.abspath(path)
    with _locks_guard:
        if abs_path not in _write_locks:
            _write_locks[abs_path] = threading.Lock()
        return _write_locks[abs_path]


class CommunicationLogger:
    """Journalise tous les messages échangés entre agents.

    S'attache à un agent via `attach()`, qui enregistre un hook AutoGen natif
    (`process_message_before_send`) : chaque message que cet agent envoie est
    journalisé juste avant transmission, sans en modifier le contenu (pass-through).

    Thread-safe : les écritures vers un même fichier sont sérialisées via un
    verrou partagé, même entre différentes instances de CommunicationLogger.
    """

    def __init__(self, log_path: str = DEFAULT_LOG_PATH):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
        self._write_lock = _lock_for_path(self.log_path)

    def attach(self, agent: Any) -> None:
        # Idempotent : un même agent peut être passé plusieurs fois à attach()
        # (ex: réutilisé sur plusieurs tours d'une boucle de correction) — AutoGen
        # refuse d'enregistrer deux fois le même hook sur un agent.
        hooks = agent.hook_lists.get("process_message_before_send", [])
        if self._log_hook not in hooks:
            agent.register_hook("process_message_before_send", self._log_hook)

    def _log_hook(self, sender: Any, message: Any, recipient: Any, silent: bool) -> Any:
        content = message.get("content") if isinstance(message, dict) else message
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from": getattr(sender, "name", str(sender)),
            "to": getattr(recipient, "name", str(recipient)),
            "content": content,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._write_lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
        return message

    def read_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.log_path):
            return []
        with open(self.log_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
