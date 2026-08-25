from protocol.delegator import Task
from protocol.pre_step import build_enriched_demande, detect_needs, run_pre_step


# --- detect_needs ---

def test_detect_needs_recognizes_recherche_keyword():
    needs = detect_needs("Fais une recherche sur le protocole HTTP.")
    assert needs.besoin_recherche is True
    assert needs.besoin_analyse is False


def test_detect_needs_recognizes_analyse_with_enough_numbers():
    needs = detect_needs("Fais une analyse de ces temps de réponse : 120, 118, 125, 480, 122.")
    assert needs.besoin_analyse is True
    assert needs.donnees_numeriques == [120.0, 118.0, 125.0, 480.0, 122.0]


def test_detect_needs_cancels_analyse_without_enough_numbers():
    needs = detect_needs("Fais une analyse de la situation.")
    assert needs.besoin_analyse is False
    assert needs.donnees_numeriques is None


def test_detect_needs_neither_triggered():
    needs = detect_needs("Écris une fonction qui additionne deux nombres.")
    assert needs.besoin_recherche is False
    assert needs.besoin_analyse is False


def test_detect_needs_both_triggered():
    needs = detect_needs("Recherche des infos sur les temps de réponse HTTP, puis analyse ces valeurs : 10, 20, 30.")
    assert needs.besoin_recherche is True
    assert needs.besoin_analyse is True
    assert needs.donnees_numeriques == [10.0, 20.0, 30.0]


def test_detect_needs_recognizes_qu_est_ce_que():
    needs = detect_needs("Qu'est-ce que Python ?")
    assert needs.besoin_recherche is True


def test_detect_needs_recognizes_variant_without_hyphen():
    needs = detect_needs("Qu'est ce que Python ?")
    assert needs.besoin_recherche is True


def test_detect_needs_recognizes_variant_without_apostrophe():
    needs = detect_needs("Quest-ce que Python ?")
    assert needs.besoin_recherche is True


def test_detect_needs_recognizes_cest_quoi():
    needs = detect_needs("C'est quoi Python ?")
    assert needs.besoin_recherche is True


def test_detect_needs_recognizes_cest_quoi_without_apostrophe():
    needs = detect_needs("Cest quoi Python ?")
    assert needs.besoin_recherche is True


def test_detect_needs_recognizes_definition():
    needs = detect_needs("Définition de HTTP")
    assert needs.besoin_recherche is True


def test_detect_needs_recognizes_definis():
    needs = detect_needs("Définis le machine learning")
    assert needs.besoin_recherche is True


def test_detect_needs_recognizes_qui_est():
    needs = detect_needs("Qui est Ada Lovelace ?")
    assert needs.besoin_recherche is True


def test_detect_needs_ignores_accents_on_analyse_keyword():
    needs = detect_needs("Fait une analyse de ces donnees : 10, 20, 30.")
    assert needs.besoin_analyse is True


def test_detect_needs_handles_comma_decimal_numbers():
    needs = detect_needs("Analyse ces valeurs : 21,5 et 57,0 et 22,1.")
    assert needs.besoin_analyse is True
    assert needs.donnees_numeriques == [21.5, 57.0, 22.1]


# --- run_pre_step ---

class FakeDelegator:
    def __init__(self):
        self.calls = []

    def delegate(self, task: Task) -> str:
        self.calls.append(task)
        return f"résultat pour {task.type}"


def test_run_pre_step_delegates_recherche_only():
    delegator = FakeDelegator()
    result = run_pre_step("Fais une recherche sur Python.", delegator)

    assert result["needs"].besoin_recherche is True
    assert result["resultats"] == {"recherche": "résultat pour recherche"}
    assert len(delegator.calls) == 1
    assert delegator.calls[0].type == "recherche"


def test_run_pre_step_delegates_analyse_only():
    delegator = FakeDelegator()
    result = run_pre_step("Analyse ces valeurs : 1, 2, 3.", delegator)

    assert result["resultats"] == {"analyse": "résultat pour analyse"}
    assert delegator.calls[0].type == "analyse"
    assert delegator.calls[0].data == [1.0, 2.0, 3.0]


def test_run_pre_step_delegates_both():
    delegator = FakeDelegator()
    result = run_pre_step("Recherche sur HTTP puis analyse : 1, 2, 3.", delegator)

    assert set(result["resultats"].keys()) == {"recherche", "analyse"}
    assert len(delegator.calls) == 2


def test_run_pre_step_delegates_nothing_when_no_need_detected():
    delegator = FakeDelegator()
    result = run_pre_step("Écris une fonction qui additionne deux nombres.", delegator)

    assert result["resultats"] == {}
    assert delegator.calls == []


# --- build_enriched_demande ---

def test_build_enriched_demande_unchanged_when_no_results():
    demande = "Écris une fonction."
    assert build_enriched_demande(demande, {}) == demande


def test_build_enriched_demande_appends_context():
    demande = "Écris une fonction."
    enrichie = build_enriched_demande(demande, {"recherche": "Contenu trouvé."})
    assert demande in enrichie
    assert "[Contexte — recherche]" in enrichie
    assert "Contenu trouvé." in enrichie


def test_build_enriched_demande_appends_multiple_contexts():
    demande = "Écris une fonction."
    enrichie = build_enriched_demande(demande, {"recherche": "R", "analyse": "A"})
    assert "[Contexte — recherche]" in enrichie
    assert "[Contexte — analyse]" in enrichie
