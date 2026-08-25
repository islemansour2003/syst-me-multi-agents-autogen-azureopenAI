from protocol.router import (
    ROUTE_ANALYSE,
    ROUTE_DEVELOPPEMENT,
    ROUTE_RECHERCHE,
    ROUTE_RECHERCHE_ET_ANALYSE,
    route_request,
)


def test_pure_definition_question_routes_to_recherche_only():
    decision = route_request("C'est quoi Python ?")
    assert decision.route == ROUTE_RECHERCHE
    assert decision.needs_code is False


def test_qu_est_ce_que_routes_to_recherche_only():
    decision = route_request("Qu'est-ce que le machine learning ?")
    assert decision.route == ROUTE_RECHERCHE


def test_pure_analysis_question_routes_to_analyse_only():
    decision = route_request("Analyse ces valeurs : 10, 20, 30.")
    assert decision.route == ROUTE_ANALYSE
    assert decision.needs_code is False


def test_recherche_and_analyse_without_code_routes_to_combined():
    decision = route_request("Recherche des infos sur HTTP et analyse ces temps : 10, 20, 30.")
    assert decision.route == ROUTE_RECHERCHE_ET_ANALYSE
    assert decision.needs_code is False


def test_coding_request_routes_to_developpement_even_with_research_keyword():
    # Contient "recherche" ET une intention de code explicite ("écris une fonction") :
    # le pipeline complet doit s'exécuter (avec pré-étape recherche en amont).
    decision = route_request(
        "Recherche des informations sur le protocole HTTP, puis écris une fonction "
        "Python qui envoie une requête GET."
    )
    assert decision.route == ROUTE_DEVELOPPEMENT
    assert decision.needs_code is True
    assert decision.needs.besoin_recherche is True


def test_plain_coding_request_routes_to_developpement():
    decision = route_request("Écris une fonction Python qui vérifie si un nombre est premier.")
    assert decision.route == ROUTE_DEVELOPPEMENT
    assert decision.needs_code is True
    assert decision.needs.besoin_recherche is False
    assert decision.needs.besoin_analyse is False


def test_ambiguous_request_with_no_keywords_defaults_to_developpement():
    decision = route_request("Fais quelque chose d'utile avec des données.")
    # "données" fait partie des mots-clés analyse, mais sans nombres exploitables,
    # detect_needs annule ce besoin — donc on retombe sur le pipeline par défaut.
    assert decision.route == ROUTE_DEVELOPPEMENT
