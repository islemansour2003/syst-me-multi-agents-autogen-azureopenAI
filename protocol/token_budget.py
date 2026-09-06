"""Gestion du budget de tokens Azure OpenAI.

Bug corrigé (US "Dépassement du budget de tokens") : certaines requêtes (notamment
dans la boucle de correction Codeur <-> Réviseur, où le code et les rapports
s'accumulent d'un tour à l'autre) pouvaient dépasser la limite de tokens acceptée
par le déploiement Azure OpenAI, provoquant une erreur 429.

Ce module ne gère qu'une chose : estimer/limiter la taille (en tokens) du contenu
avant de l'envoyer. Le retry avec backoff exponentiel sur les 429 est géré
séparément, au niveau du client lui-même (voir config/azure_config.py,
paramètre `max_retries`) : le SDK openai implémente déjà un backoff exponentiel
robuste (il respecte l'en-tête `Retry-After` renvoyé par Azure) — pas besoin de
le réimplémenter ici.
"""

from typing import List

import tiktoken

DEFAULT_ENCODING = "cl100k_base"  # encodage utilisé par la famille de modèles gpt-4/gpt-4o


def count_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """Nombre de tokens que `text` consommera pour l'encodage donné."""
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))


class TokenBudgetManager:
    """Vérifie qu'un texte tient dans un budget de tokens donné, et le découpe
    (chunking) en morceaux respectant ce budget sinon.

    Le découpage se fait au niveau des tokens eux-mêmes (via encode/decode), pas
    des caractères : ça garantit que chaque morceau respecte exactement le budget,
    contrairement à une coupe par nombre de caractères qui ne fait qu'approximer.
    """

    def __init__(self, max_tokens_per_request: int, encoding_name: str = DEFAULT_ENCODING):
        if max_tokens_per_request <= 0:
            raise ValueError("max_tokens_per_request doit être strictement positif.")
        self.max_tokens_per_request = max_tokens_per_request
        self.encoding_name = encoding_name
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def fits(self, text: str) -> bool:
        return self.count(text) <= self.max_tokens_per_request

    def chunk(self, text: str) -> List[str]:
        """Découpe `text` en une liste de morceaux tenant chacun dans le budget."""
        tokens = self._encoding.encode(text)
        if not tokens:
            return [text]
        step = self.max_tokens_per_request
        return [self._encoding.decode(tokens[i : i + step]) for i in range(0, len(tokens), step)]

    def bound(self, text: str, truncation_notice: str = "\n[...contenu tronqué pour respecter le budget de tokens...]") -> str:
        """Retourne `text` inchangé s'il tient dans le budget, sinon son premier
        morceau (le plus pertinent : début du contenu) suivi d'une mention explicite
        de troncature — pour éviter d'envoyer une requête qui déclencherait un 429,
        sans jamais faire disparaître l'information silencieusement."""
        if self.fits(text):
            return text
        premier_morceau = self.chunk(text)[0]
        return premier_morceau + truncation_notice
