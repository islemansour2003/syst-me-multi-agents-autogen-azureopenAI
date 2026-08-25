from types import SimpleNamespace
from typing import Any, Dict, List

from autogen import AssistantAgent

from agents.analyste_agent import AnalysteAgent
from agents.base_agents import create_user_proxy_agent
from agents.codeur_agent import CodeurAgent
from agents.planificateur_agent import PlanificateurAgent
from agents.reviseur_agent import ReviseurAgent
from protocol.router import ROUTE_ANALYSE, ROUTE_DEVELOPPEMENT, ROUTE_RECHERCHE, ROUTE_RECHERCHE_ET_ANALYSE
from protocol.routing_engine import RoutingEngine
from tests.fake_model_client import FakeModelClient, fake_llm_config


def make_team(reply_text: str, name: str = "fake_assistant"):
    assistant = AssistantAgent(name=name, llm_config=fake_llm_config(reply_text))
    assistant.register_model_client(model_client_cls=FakeModelClient)
    executor = create_user_proxy_agent(name=f"{name}_executor", max_consecutive_auto_reply=1)
    return assistant, executor


def make_agent(cls, reply_text: str):
    agent = cls(llm_config=fake_llm_config(reply_text))
    agent.register_model_client(model_client_cls=FakeModelClient)
    return agent


class CyclingFakeModelClient:
    """Comme FakeModelClient, mais renvoie une réponse différente à chaque appel
    (cycle sur une liste) — pour simuler un Réviseur qui change d'avis d'un tour
    à l'autre (accepte au 2e essai, ou refuse toujours avec des motifs distincts)."""

    def __init__(self, config: Dict[str, Any], **kwargs):
        self.model = config.get("model", "fake-model")
        self.replies: List[str] = config["replies"]
        self._index = 0
        self.received_messages: List[List[Dict[str, Any]]] = []

    def create(self, params: Dict[str, Any]):
        self.received_messages.append(params.get("messages", []))
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


def make_cycling_agent(cls, replies: List[str]):
    agent = cls(llm_config=cycling_llm_config(replies))
    agent.register_model_client(model_client_cls=CyclingFakeModelClient)
    return agent


# --- Raccourcis (pas de code demandé) ---

def test_route_pure_recherche_calls_only_recherche():
    recherche_team = make_team("Python est un langage de programmation. TERMINATE", name="recherche")
    engine = RoutingEngine(llm_config=fake_llm_config(), recherche_team_factory=lambda: recherche_team)

    result = engine.route("C'est quoi Python ?")

    assert result.route == ROUTE_RECHERCHE
    assert len(result.steps) == 1
    assert result.steps[0].agent == "recherche"
    assert "langage de programmation" in result.resultat_final


def test_route_pure_analyse_calls_only_analyse():
    analyse_team = make_team("### Rapport d'Analyse\nTERMINATE", name="analyse")
    engine = RoutingEngine(llm_config=fake_llm_config(), analyse_team_factory=lambda: analyse_team)

    result = engine.route("Analyse ces valeurs : 10, 20, 30.")

    assert result.route == ROUTE_ANALYSE
    assert len(result.steps) == 1
    assert result.steps[0].agent == "analyse"


def test_route_recherche_et_analyse_calls_both_without_chain():
    recherche_team = make_team("Réponse recherche. TERMINATE", name="recherche")
    analyse_team = make_team("Réponse analyse. TERMINATE", name="analyse")
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        recherche_team_factory=lambda: recherche_team,
        analyse_team_factory=lambda: analyse_team,
    )

    result = engine.route("Recherche des infos sur HTTP et analyse ces temps : 10, 20, 30.")

    assert result.route == ROUTE_RECHERCHE_ET_ANALYSE
    assert [s.agent for s in result.steps] == ["recherche", "analyse"]
    assert "Réponse recherche" in result.resultat_final
    assert "Réponse analyse" in result.resultat_final


# --- Chaîne complète (code demandé) ---

def test_full_chain_runs_all_5_agents_in_order():
    recherche_team = make_team("Contexte trouvé par Recherche. TERMINATE", name="recherche")
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape un\nTERMINATE"),
        codeur_factory=lambda: make_agent(CodeurAgent, "```python\nprint('hi')\n```"),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nCode correct.\nTERMINATE"),
        reviseur_factory=lambda: make_agent(ReviseurAgent, "CODE_APPROUVE"),
    )

    result = engine.route("Écris une fonction Python qui vérifie si un nombre est premier.")

    assert result.route == ROUTE_DEVELOPPEMENT
    assert [s.agent for s in result.steps] == ["recherche", "planificateur", "codeur", "analyse", "reviseur"]
    assert result.approuve is True
    assert "print" in result.resultat_final


def test_full_chain_each_agent_receives_previous_agents_output():
    recherche_team = make_team("INFO_RECHERCHE_UNIQUE. TERMINATE", name="recherche")

    planificateur = make_agent(PlanificateurAgent, "PLAN_UNIQUE\nTERMINATE")
    codeur = make_agent(CodeurAgent, "CODE_UNIQUE")
    analyste = make_agent(AnalysteAgent, "RAPPORT_UNIQUE\nTERMINATE")
    reviseur = make_agent(ReviseurAgent, "CODE_APPROUVE")

    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: planificateur,
        codeur_factory=lambda: codeur,
        analyste_factory=lambda: analyste,
        reviseur_factory=lambda: reviseur,
    )

    engine.route("Écris une fonction Python qui additionne deux nombres.")

    # Le Planificateur doit avoir reçu le résultat de Recherche.
    planificateur_client = planificateur.client._clients[0]
    assert "INFO_RECHERCHE_UNIQUE" in planificateur_client.received_messages[0][-1]["content"]

    # Le Codeur doit avoir reçu le plan.
    codeur_client = codeur.client._clients[0]
    assert "PLAN_UNIQUE" in codeur_client.received_messages[0][-1]["content"]

    # L'Analyste doit avoir reçu le code.
    analyste_client = analyste.client._clients[0]
    assert "CODE_UNIQUE" in analyste_client.received_messages[0][-1]["content"]

    # Le Réviseur doit avoir reçu le code ET le rapport de l'Analyste.
    reviseur_client = reviseur.client._clients[0]
    reviseur_message = reviseur_client.received_messages[0][-1]["content"]
    assert "CODE_UNIQUE" in reviseur_message
    assert "RAPPORT_UNIQUE" in reviseur_message


def test_full_chain_approuve_false_when_reviseur_rejects_and_repeats():
    # Le Réviseur redonne mot pour mot le même avis à chaque tour : la boucle
    # de correction Codeur<->Réviseur (US 2.2) doit détecter la répétition
    # (Bug 1) et s'arrêter plutôt que de tourner indéfiniment.
    recherche_team = make_team("Contexte. TERMINATE", name="recherche")
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        max_rounds=5,
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape\nTERMINATE"),
        codeur_factory=lambda: make_agent(CodeurAgent, "```python\nprint('hi')\n```"),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nProblème détecté.\nTERMINATE"),
        reviseur_factory=lambda: make_agent(ReviseurAgent, "Corrige la gestion d'erreur avant de valider."),
    )

    result = engine.route("Écris une fonction Python qui divise deux nombres.")

    assert result.approuve is False
    assert result.boucle_detectee is True
    assert result.raison_boucle == "repetition"


# --- Boucle de correction Codeur <-> Réviseur (US 2.2) ---

def test_full_chain_retries_codeur_when_reviseur_rejects_then_approves():
    recherche_team = make_team("Contexte. TERMINATE", name="recherche")
    codeur = make_cycling_agent(CodeurAgent, ["```python\nversion_1\n```", "```python\nversion_2_corrigee\n```"])
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        max_rounds=5,
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape\nTERMINATE"),
        codeur_factory=lambda: codeur,
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nTERMINATE"),
        reviseur_factory=lambda: make_cycling_agent(
            ReviseurAgent, ["Il manque une gestion d'erreur pour b == 0.", "CODE_APPROUVE"]
        ),
    )

    result = engine.route("Écris une fonction Python qui divise deux nombres.")

    assert result.approuve is True
    assert result.boucle_detectee is False
    assert [s.agent for s in result.steps] == [
        "recherche",
        "planificateur",
        "codeur",
        "analyse",
        "reviseur",
        "codeur",
        "analyse",
        "reviseur",
    ]
    assert "version_2_corrigee" in result.resultat_final
    assert result.steps[5].content == "```python\nversion_2_corrigee\n```"

    # Le 2e appel au Codeur doit contenir le retour du Réviseur du 1er tour.
    codeur_client = codeur.client._clients[0]
    assert len(codeur_client.received_messages) == 2
    deuxieme_message = codeur_client.received_messages[1][-1]["content"]
    assert "Il manque une gestion d'erreur pour b == 0." in deuxieme_message
    assert "version_1" in deuxieme_message


def test_full_chain_stops_at_max_rounds_when_feedback_keeps_varying_without_approval():
    recherche_team = make_team("Contexte. TERMINATE", name="recherche")
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        max_rounds=3,
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape\nTERMINATE"),
        codeur_factory=lambda: make_cycling_agent(
            CodeurAgent, ["```python\nv1\n```", "```python\nv2\n```", "```python\nv3\n```"]
        ),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nTERMINATE"),
        reviseur_factory=lambda: make_cycling_agent(
            ReviseurAgent,
            [
                "Il faut valider que le paramètre n'est jamais None avant de l'utiliser.",
                "La fonction ne gère pas le cas où la liste est vide, ajoute une vérification.",
                "Le nom de la variable n'est pas assez explicite, renomme-la pour plus de clarté.",
            ],
        ),
    )

    result = engine.route("Écris une fonction Python qui divise deux nombres.")

    assert result.approuve is False
    assert result.boucle_detectee is True
    assert result.raison_boucle == "max_rounds"


def test_full_chain_with_ui_hook_survives_codeur_retry():
    # Régression : le Codeur est réutilisé (même instance) entre le 1er essai et
    # la correction après rejet. Un ui_hook (comme celui de Streamlit) était
    # réenregistré à chaque appel via _one_shot -> _attach, ce qui faisait planter
    # AutoGen ("... is already registered as a hook.") dès qu'un rejet survenait.
    captured_senders = []

    def ui_hook(sender, message, recipient, silent):
        captured_senders.append(sender.name)
        return message

    recherche_team = make_team("Contexte. TERMINATE", name="recherche")
    engine = RoutingEngine(
        llm_config=fake_llm_config(),
        ui_hook=ui_hook,
        max_rounds=5,
        recherche_team_factory=lambda: recherche_team,
        planificateur_factory=lambda: make_agent(PlanificateurAgent, "1. Étape\nTERMINATE"),
        codeur_factory=lambda: make_cycling_agent(
            CodeurAgent, ["```python\nv1\n```", "```python\nv2\n```"]
        ),
        analyste_factory=lambda: make_agent(AnalysteAgent, "### Rapport d'Analyse\nTERMINATE"),
        reviseur_factory=lambda: make_cycling_agent(
            ReviseurAgent, ["Corrige la gestion d'erreur.", "CODE_APPROUVE"]
        ),
    )

    result = engine.route("Écris une fonction Python qui divise deux nombres.")  # ne doit pas lever

    assert result.approuve is True
    assert "codeur" in captured_senders
    assert captured_senders.count("codeur") == 2  # 1er jet + correction
