from types import SimpleNamespace
from typing import Any, Dict


class FakeModelClient:
    """Client LLM factice respectant le protocole ModelClient d'AutoGen.

    Utilisé pour les tests unitaires afin de valider le comportement des agents
    (instanciation, communication, historique) sans appel réseau réel vers Azure OpenAI.
    """

    def __init__(self, config: Dict[str, Any], **kwargs):
        self.model = config.get("model", "fake-model")
        self.reply_text = config.get("reply_text", "Réponse simulée. TERMINATE")
        self.call_count = 0
        self.received_messages = []

    def create(self, params: Dict[str, Any]):
        self.call_count += 1
        self.received_messages.append(params.get("messages", []))

        message = SimpleNamespace(content=self.reply_text, function_call=None, tool_calls=None)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return SimpleNamespace(choices=[choice], model=self.model, usage=usage)

    def message_retrieval(self, response):
        return [choice.message.content for choice in response.choices]

    def cost(self, response) -> float:
        return 0.0

    @staticmethod
    def get_usage(response) -> Dict[str, Any]:
        return {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "cost": 0.0,
            "model": response.model,
        }


def fake_llm_config(reply_text: str = "Réponse simulée. TERMINATE") -> Dict[str, Any]:
    return {
        "config_list": [
            {
                "model": "fake-model",
                "model_client_cls": "FakeModelClient",
                "reply_text": reply_text,
            }
        ],
        # Cache désactivé : on veut que chaque test appelle réellement FakeModelClient.create()
        # plutôt que de recevoir une réponse mise en cache sur disque par un test précédent.
        "cache_seed": None,
    }
