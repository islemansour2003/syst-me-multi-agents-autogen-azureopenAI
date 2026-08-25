from types import SimpleNamespace
from typing import Any, Dict, List

from agents.code_review_loop import _is_terminal, run_code_review_loop
from agents.codeur_agent import CodeurAgent
from agents.reviseur_agent import ReviseurAgent
from tests.fake_model_client import FakeModelClient, fake_llm_config


class CyclingFakeModelClient:
    """Comme FakeModelClient, mais renvoie une réponse différente à chaque appel
    (cycle sur une liste) — utile pour simuler un désaccord qui varie réellement
    d'un round à l'autre, sans jamais se répéter à l'identique."""

    def __init__(self, config: Dict[str, Any], **kwargs):
        self.model = config.get("model", "fake-model")
        self.replies: List[str] = config["replies"]
        self._index = 0

    def create(self, params: Dict[str, Any]):
        text = self.replies[self._index % len(self.replies)]
        self._index += 1
        message = SimpleNamespace(content=text, function_call=None, tool_calls=None)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return SimpleNamespace(choices=[choice], model=self.model, usage=usage)

    def message_retrieval(self, response):
        return [choice.message.content for choice in response.choices]

    def cost(self, response) -> float:
        return 0.0

    @staticmethod
    def get_usage(response) -> Dict[str, Any]:
        return {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10, "cost": 0.0, "model": response.model}


def cycling_llm_config(replies: List[str]) -> Dict[str, Any]:
    return {
        "config_list": [{"model": "fake-model", "model_client_cls": "CyclingFakeModelClient", "replies": replies}],
        "cache_seed": None,
    }


def make_codeur(reply_text: str, max_rounds: int) -> CodeurAgent:
    codeur = CodeurAgent(
        llm_config=fake_llm_config(reply_text),
        max_consecutive_auto_reply=max_rounds,
        is_termination_msg=_is_terminal,
    )
    codeur.register_model_client(model_client_cls=FakeModelClient)
    return codeur


def make_reviseur(reply_text: str, max_rounds: int) -> ReviseurAgent:
    reviseur = ReviseurAgent(llm_config=fake_llm_config(reply_text), max_consecutive_auto_reply=max_rounds)
    reviseur.register_model_client(model_client_cls=FakeModelClient)
    return reviseur


def test_loop_stops_as_soon_as_reviseur_approves():
    codeur = make_codeur("```python\nprint('hello')\n```", max_rounds=5)
    reviseur = make_reviseur("CODE_APPROUVE", max_rounds=5)

    result = run_code_review_loop("Plan de test", max_rounds=5, codeur=codeur, reviseur=reviseur)

    assert result["approuve"] is True
    assert result["boucle_detectee"] is False
    assert result["premier_code"] == "```python\nprint('hello')\n```"
    # 1 message du codeur + 1 approbation du réviseur = 2 échanges, pas 5.
    assert result["nombre_echanges"] == 2


def test_loop_detects_repetition_before_max_rounds():
    # Le Réviseur redonne mot pour mot le même avis à chaque round : signe classique
    # de stagnation (Bug 1 — demande initiale trop vague, le Codeur ne progresse pas).
    codeur = make_codeur("```python\nprint('hello')\n```", max_rounds=5)
    reviseur = make_reviseur("Corrige la variable X, elle n'est pas utilisée.", max_rounds=5)

    result = run_code_review_loop("Plan de test", max_rounds=5, codeur=codeur, reviseur=reviseur)

    assert result["approuve"] is False
    assert result["boucle_detectee"] is True
    assert result["raison_boucle"] == "repetition"
    # Détecté dès la 2e fois que le Réviseur répète son avis, bien avant max_rounds=5.
    assert result["nombre_echanges"] <= 4


def test_loop_stops_at_max_rounds_when_feedback_keeps_varying():
    # Le Réviseur donne un avis différent à chaque round (donc pas de répétition
    # détectable), mais n'approuve jamais : la boucle doit quand même s'arrêter
    # au plafond de rounds plutôt que de continuer indéfiniment.
    codeur = CodeurAgent(
        llm_config=cycling_llm_config(
            ["```python\nprint('v1')\n```", "```python\nprint('v2')\n```", "```python\nprint('v3')\n```"]
        ),
        max_consecutive_auto_reply=3,
        is_termination_msg=_is_terminal,
    )
    codeur.register_model_client(model_client_cls=CyclingFakeModelClient)

    reviseur = ReviseurAgent(
        llm_config=cycling_llm_config(
            [
                "Il faut valider que le paramètre n'est jamais None avant de l'utiliser.",
                "La fonction ne gère pas le cas où la liste est vide, ajoute une vérification.",
                "Le nom de la variable n'est pas assez explicite, renomme-la pour plus de clarté.",
            ]
        ),
        max_consecutive_auto_reply=3,
    )
    reviseur.register_model_client(model_client_cls=CyclingFakeModelClient)

    result = run_code_review_loop("Plan de test", max_rounds=3, codeur=codeur, reviseur=reviseur)

    assert result["approuve"] is False
    assert result["boucle_detectee"] is True
    assert result["raison_boucle"] == "max_rounds"


def test_loop_returns_expected_keys():
    codeur = make_codeur("code", max_rounds=2)
    reviseur = make_reviseur("CODE_APPROUVE", max_rounds=2)

    result = run_code_review_loop("Plan de test", max_rounds=2, codeur=codeur, reviseur=reviseur)

    assert set(result.keys()) == {
        "plan",
        "premier_code",
        "code_final",
        "approuve",
        "nombre_echanges",
        "historique",
        "boucle_detectee",
        "raison_boucle",
    }
