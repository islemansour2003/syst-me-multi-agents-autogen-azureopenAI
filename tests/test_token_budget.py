import pytest

from protocol.token_budget import TokenBudgetManager, count_tokens


def test_count_tokens_counts_more_for_longer_text():
    court = count_tokens("Bonjour")
    long = count_tokens("Bonjour " * 50)
    assert long > court


def test_manager_rejects_non_positive_budget():
    with pytest.raises(ValueError):
        TokenBudgetManager(max_tokens_per_request=0)


def test_fits_true_for_small_text_under_budget():
    manager = TokenBudgetManager(max_tokens_per_request=100)
    assert manager.fits("Un petit texte.") is True


def test_fits_false_for_text_exceeding_budget():
    manager = TokenBudgetManager(max_tokens_per_request=5)
    assert manager.fits("Ceci est un texte bien plus long que cinq tokens, à coup sûr.") is False


def test_chunk_produces_pieces_each_within_budget():
    manager = TokenBudgetManager(max_tokens_per_request=10)
    texte = "mot " * 200  # largement au-delà de 10 tokens
    morceaux = manager.chunk(texte)
    assert len(morceaux) > 1
    assert all(manager.count(m) <= 10 for m in morceaux)


def test_chunk_single_piece_when_text_already_fits():
    manager = TokenBudgetManager(max_tokens_per_request=1000)
    texte = "Un texte court."
    assert manager.chunk(texte) == [texte]


def test_bound_returns_text_unchanged_when_it_fits():
    manager = TokenBudgetManager(max_tokens_per_request=1000)
    texte = "Texte qui tient largement dans le budget."
    assert manager.bound(texte) == texte


def test_bound_truncates_and_adds_notice_when_too_long():
    manager = TokenBudgetManager(max_tokens_per_request=5)
    texte = "Ceci est un texte bien plus long que cinq tokens, à coup sûr, vraiment."
    resultat = manager.bound(texte)
    assert manager.count(resultat) > 5  # la mention de troncature s'ajoute au budget
    assert "tronqué" in resultat
    assert resultat != texte


def test_bound_result_always_shorter_than_original_when_truncated():
    manager = TokenBudgetManager(max_tokens_per_request=5)
    texte = "mot " * 200
    resultat = manager.bound(texte)
    assert len(resultat) < len(texte)
