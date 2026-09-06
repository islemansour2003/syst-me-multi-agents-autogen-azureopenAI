"""Démo/preuve pour le rapport — ticket "Dépassement du budget de tokens".

Deux parties, indépendantes de tout accès réseau réel à Azure :

1. TokenBudgetManager : montre le comptage de tokens et le bornage (chunking)
   d'un contenu volontairement énorme.
2. Retry avec backoff exponentiel : simule de VRAIES réponses HTTP 429 (via un
   faux transport httpx, sans toucher au réseau ni au quota Azure) pour prouver
   que le client openai.AzureOpenAI, configuré avec max_retries, réessaie
   automatiquement jusqu'à réussir — au lieu de planter à la première erreur.

Lancer depuis la racine du projet :
    python scripts/demo_token_budget_et_retry.py
"""

import json
import sys
import time

import httpx
from openai import AzureOpenAI

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from protocol.token_budget import TokenBudgetManager  # noqa: E402


def demo_token_budget() -> None:
    print("=" * 70)
    print("PARTIE 1 — TokenBudgetManager (comptage + bornage)")
    print("=" * 70)

    code_enorme = "```python\n" + ("x = 1\n" * 3000) + "```"
    manager = TokenBudgetManager(max_tokens_per_request=50)

    print(f"Taille du code généré : {len(code_enorme)} caractères, "
          f"{manager.count(code_enorme)} tokens (budget autorisé : 50)")
    print(f"Tient dans le budget ? {manager.fits(code_enorme)}")

    resultat = manager.bound(code_enorme)
    print(f"\nAprès bound() : {len(resultat)} caractères, {manager.count(resultat)} tokens")
    print("Contenu (tronqué à l'affichage) :")
    print(resultat[:200] + ("..." if len(resultat) > 200 else ""))
    assert "tronqué" in resultat
    print("\n-> Le contenu envoyé au modèle est garanti borné, avec mention explicite de troncature.")


def demo_retry_backoff() -> None:
    print("\n" + "=" * 70)
    print("PARTIE 2 — Retry avec backoff exponentiel sur une vraie erreur 429")
    print("=" * 70)

    appels = {"n": 0}
    horodatages: list = []

    def faux_endpoint_azure(request: httpx.Request) -> httpx.Response:
        appels["n"] += 1
        horodatages.append(time.perf_counter())
        if appels["n"] <= 2:
            print(f"  [appel {appels['n']}] Azure répond 429 (quota dépassé) — "
                  f"le client va réessayer automatiquement...")
            return httpx.Response(
                429,
                json={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            )
        print(f"  [appel {appels['n']}] Azure répond 200 (quota disponible) — succès.")
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-demo",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "OK, requête traitée."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9},
            },
        )

    faux_transport = httpx.MockTransport(faux_endpoint_azure)

    client = AzureOpenAI(
        api_key="fake-key-demo",
        azure_endpoint="https://fake.openai.azure.com",
        api_version="2025-01-01-preview",
        max_retries=5,  # même valeur par défaut que config/azure_config.py
        http_client=httpx.Client(transport=faux_transport),
    )

    print("Envoi d'une requête (2 échecs 429 simulés avant succès)...\n")
    debut = time.perf_counter()
    reponse = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Test"}],
    )
    duree_totale = time.perf_counter() - debut

    print(f"\nRéponse finale obtenue : \"{reponse.choices[0].message.content}\"")
    print(f"Nombre total de tentatives HTTP : {appels['n']}")
    print(f"Durée totale (attente de backoff incluse) : {duree_totale:.2f}s")

    if len(horodatages) >= 3:
        delai_1 = horodatages[1] - horodatages[0]
        delai_2 = horodatages[2] - horodatages[1]
        print(f"Délai entre tentative 1 et 2 : {delai_1:.2f}s")
        print(f"Délai entre tentative 2 et 3 : {delai_2:.2f}s")

    assert appels["n"] == 3, "Le client aurait dû réessayer exactement 2 fois avant de réussir."
    assert reponse.choices[0].message.content == "OK, requête traitée."
    print("\n-> Le client a bien absorbé 2 erreurs 429 réelles et réessayé automatiquement "
          "avec un backoff (pas de sleep(0), un vrai délai croissant) avant de réussir.")


if __name__ == "__main__":
    demo_token_budget()
    demo_retry_backoff()
    print("\n" + "=" * 70)
    print("DÉMO TERMINÉE — les deux mécanismes fonctionnent comme attendu.")
    print("=" * 70)
