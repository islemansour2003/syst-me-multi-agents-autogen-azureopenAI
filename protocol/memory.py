import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from autogen import ConversableAgent
from autogen.agentchat.contrib.capabilities.transform_messages import TransformMessages
from openai import AzureOpenAI

from config.azure_config import get_llm_config

DEFAULT_MEMORY_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "memory.json")


class LongTermMemory:
    """Mémoire persistante entre conversations (survit au-delà d'un seul échange,
    contrairement au résumé progressif qui ne vit que le temps d'une conversation) :
    stocke des faits clés (ex: résumés) sous forme clé/valeur dans un fichier JSON.
    """

    def __init__(self, path: str = DEFAULT_MEMORY_PATH):
        self.path = path
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            self._write({})

    def _read(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: Dict[str, Any]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def remember(self, key: str, value: Any) -> None:
        data = self._read()
        data[key] = value
        self._write(data)

    def recall(self, key: str) -> Optional[Any]:
        return self._read().get(key)

    def all(self) -> Dict[str, Any]:
        return self._read()

    def forget(self, key: str) -> None:
        data = self._read()
        data.pop(key, None)
        self._write(data)


def _default_summarizer(messages: List[Dict[str, Any]], previous_summary: Optional[str]) -> str:
    """Résumeur par défaut : appel Azure OpenAI réel, indépendant d'AutoGen
    (utilitaire brut, pas un agent — pas besoin de passer par ConversableAgent)."""
    config = get_llm_config()["config_list"][0]
    client = AzureOpenAI(
        api_key=config["api_key"],
        azure_endpoint=config["base_url"],
        api_version=config["api_version"],
    )

    texte = "\n".join(f"{m.get('name', m.get('role', '?'))}: {m.get('content', '')}" for m in messages)
    contexte_precedent = f"Résumé précédent : {previous_summary}\n\n" if previous_summary else ""

    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {
                "role": "user",
                "content": (
                    f"{contexte_precedent}Résume en 3 à 5 phrases maximum les échanges suivants, "
                    "en conservant impérativement l'objectif initial de la conversation et les "
                    "décisions déjà prises (ne perds aucune information critique) :\n\n" + texte
                ),
            }
        ],
        max_completion_tokens=300,
    )
    return response.choices[0].message.content


class ProgressiveSummaryTransform:
    """Transform AutoGen (`TransformMessages`) : au-delà de `max_messages` messages
    dans l'historique, résume les plus anciens en un seul message condensé plutôt
    que de les tronquer silencieusement — préserve le contexte initial et les
    décisions déjà prises au lieu de les perdre (Bug 7 : perte de contexte après
    de longs échanges).

    Le résumé est progressif : chaque nouveau résumé part du précédent plutôt que
    de repartir de zéro, pour ne pas perdre l'information des tours déjà résumés.
    """

    def __init__(
        self,
        max_messages: int = 10,
        keep_recent: int = 6,
        summarizer_fn: Optional[Callable[[List[Dict[str, Any]], Optional[str]], str]] = None,
        long_term_memory: Optional[LongTermMemory] = None,
        memory_key: Optional[str] = None,
    ) -> None:
        if keep_recent >= max_messages:
            raise ValueError("keep_recent doit être strictement inférieur à max_messages.")
        self.max_messages = max_messages
        self.keep_recent = keep_recent
        self._summarizer_fn = summarizer_fn or _default_summarizer
        self._long_term_memory = long_term_memory
        self._memory_key = memory_key
        self.running_summary: Optional[str] = None

    def apply_transform(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(messages) <= self.max_messages:
            return messages

        a_resumer = messages[: len(messages) - self.keep_recent]
        recents = messages[len(messages) - self.keep_recent :]

        self.running_summary = self._summarizer_fn(a_resumer, self.running_summary)

        if self._long_term_memory is not None and self._memory_key:
            self._long_term_memory.remember(self._memory_key, self.running_summary)

        summary_message = {
            "role": "system",
            "content": f"[Résumé des échanges précédents]\n{self.running_summary}",
        }
        return [summary_message] + recents

    def get_logs(
        self, pre_transform_messages: List[Dict[str, Any]], post_transform_messages: List[Dict[str, Any]]
    ) -> Tuple[str, bool]:
        had_effect = len(pre_transform_messages) != len(post_transform_messages)
        if had_effect:
            return (
                f"Résumé progressif appliqué : {len(pre_transform_messages)} messages -> "
                f"{len(post_transform_messages)} (1 résumé + {self.keep_recent} messages récents).",
                True,
            )
        return ("Pas de résumé nécessaire (sous le seuil).", False)


def attach_memory_management(
    agent: ConversableAgent,
    max_messages: int = 10,
    keep_recent: int = 6,
    summarizer_fn: Optional[Callable[[List[Dict[str, Any]], Optional[str]], str]] = None,
    long_term_memory: Optional[LongTermMemory] = None,
    memory_key: Optional[str] = None,
) -> ProgressiveSummaryTransform:
    """Ajoute la gestion de la perte de contexte à un agent (Bug 7) : résumé
    progressif de l'historique au-delà de `max_messages`, avec persistance
    optionnelle du dernier résumé en mémoire à long terme."""
    transform = ProgressiveSummaryTransform(
        max_messages=max_messages,
        keep_recent=keep_recent,
        summarizer_fn=summarizer_fn,
        long_term_memory=long_term_memory,
        memory_key=memory_key or agent.name,
    )
    TransformMessages(transforms=[transform], verbose=False).add_to_agent(agent)
    return transform
