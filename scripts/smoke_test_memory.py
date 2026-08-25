"""
Test manuel (non pytest) : valide le résumé progressif (US 7) avec le vrai Azure
OpenAI, sur un historique fictif de plus de 10 messages, et vérifie la
persistance en mémoire à long terme.
Usage: python scripts/smoke_test_memory.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from protocol.memory import LongTermMemory, ProgressiveSummaryTransform

MEMORY_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "memory.json")

if __name__ == "__main__":
    # Historique fictif : l'objectif initial est donné au tout début, puis noyé
    # sous des échanges de détail — exactement le scénario du bug (perte de
    # contexte après de longs échanges).
    historique = [
        {"role": "user", "name": "utilisateur", "content": "Objectif : construire une API de gestion de stock pour une boutique en ligne, avec alertes de rupture de stock."},
        {"role": "assistant", "name": "planificateur", "content": "1. Modéliser les produits. 2. Endpoint CRUD produits. 3. Endpoint de mise à jour de stock. 4. Alerte si stock < seuil."},
        {"role": "assistant", "name": "codeur", "content": "J'ai créé le modèle Produit avec id, nom, quantite, seuil_alerte."},
        {"role": "user", "name": "reviseur", "content": "Le modèle est correct, mais il manque un champ 'derniere_maj'."},
        {"role": "assistant", "name": "codeur", "content": "Ajouté le champ derniere_maj de type datetime."},
        {"role": "user", "name": "reviseur", "content": "Bien. Passons à l'endpoint CRUD."},
        {"role": "assistant", "name": "codeur", "content": "Endpoints POST/GET/PUT/DELETE /produits créés avec FastAPI."},
        {"role": "user", "name": "reviseur", "content": "Il manque la validation des entrées (quantite >= 0)."},
        {"role": "assistant", "name": "codeur", "content": "Ajouté un validator Pydantic pour quantite >= 0."},
        {"role": "user", "name": "reviseur", "content": "Parfait. Maintenant l'endpoint de mise à jour de stock."},
        {"role": "assistant", "name": "codeur", "content": "Endpoint PATCH /produits/{id}/stock créé."},
        {"role": "user", "name": "reviseur", "content": "Il faut aussi déclencher l'alerte si quantite < seuil_alerte après la mise à jour."},
    ]

    print(f"Historique complet : {len(historique)} messages\n")

    transform = ProgressiveSummaryTransform(max_messages=10, keep_recent=6)  # summarizer réel (Azure)
    resultat = transform.apply_transform(historique)

    print(f"Après transformation : {len(resultat)} messages (1 résumé + {len(resultat) - 1} récents)\n")
    print("--- Résumé généré ---")
    print(resultat[0]["content"])

    print("\n--- Messages récents conservés tels quels ---")
    for m in resultat[1:]:
        print(f"[{m['name']}] {m['content'][:70]}")

    # Vérification qualitative : l'objectif initial doit survivre dans le résumé.
    objectif_present = "stock" in resultat[0]["content"].lower()
    print(f"\nL'objectif initial ('stock') est-il bien conservé dans le résumé ? {objectif_present}")

    # Mémoire à long terme
    memoire = LongTermMemory(path=MEMORY_PATH)
    memoire.remember("demo_projet_stock", resultat[0]["content"])
    print(f"\nRésumé persisté dans {MEMORY_PATH} sous la clé 'demo_projet_stock'.")
    print("Relecture depuis le disque :", memoire.recall("demo_projet_stock")[:80], "...")
