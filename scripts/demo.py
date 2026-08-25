"""
Démo consolidée : illustre les agents développés jusqu'ici sur un exemple concret.
- Planificateur -> Codeur -> Réviseur (pipeline manuel : le GroupChat autonome
  n'est pas encore implémenté, ce sera un ticket dédié).
- Agent Recherche (Wikipedia + NewsAPI), en démonstration indépendante.
- Agent Analyste (Chain-of-Thought + détection d'anomalies), en démonstration indépendante.
- Protocole de communication inter-agents : délégation asynchrone, logging, consensus.
- Détection de boucle entre agents et demande de clarification (Bug 1).
- Agent orchestrateur (GroupChatManager) avec dashboard de monitoring.
- Résumé progressif et mémoire à long terme sur les longs échanges (Bug 7).

Usage: python scripts/demo.py
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.analyste_agent import analyze_data
from agents.base_agents import create_user_proxy_agent
from agents.code_review_loop import run_code_review_loop
from agents.codeur_agent import CodeurAgent
from agents.orchestrator import run_orchestrated_task
from agents.planificateur_agent import PlanificateurAgent
from agents.research_agent import ask_research_agent
from agents.reviseur_agent import ReviseurAgent
from protocol.consensus import collect_verdicts, resolve_consensus
from protocol.delegator import Task, TaskDelegator
from protocol.logger import CommunicationLogger
from protocol.loop_detection import LoopDetector, build_clarification_message
from protocol.memory import LongTermMemory, ProgressiveSummaryTransform

DEMO_MEMORY_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "memory.json")

DEMO_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "communications.jsonl")


def separator(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def run_step(agent, message: str) -> str:
    user_proxy = create_user_proxy_agent(max_consecutive_auto_reply=1)
    result = user_proxy.initiate_chat(agent, message=message, max_turns=1)
    return result.chat_history[-1]["content"]


def strip_terminate(text: str) -> str:
    return text.replace("TERMINATE", "").strip()


if __name__ == "__main__":
    demande_utilisateur = (
        "Écris une fonction Python qui calcule la moyenne, le minimum et le maximum "
        "d'une liste de températures."
    )

    separator("DEMANDE UTILISATEUR")
    print(demande_utilisateur)

    # 1. Planificateur
    separator("ÉTAPE 1 — Agent Planificateur")
    plan = run_step(PlanificateurAgent(), demande_utilisateur)
    print(plan)

    # 2. Codeur (reçoit le plan du Planificateur)
    separator("ÉTAPE 2 — Agent Codeur")
    code = run_step(CodeurAgent(), f"Voici le plan à implémenter :\n\n{strip_terminate(plan)}")
    print(code)

    # 3. Réviseur (reçoit le code du Codeur)
    separator("ÉTAPE 3 — Agent Réviseur")
    revue = run_step(ReviseurAgent(), f"Voici le code à relire :\n\n{strip_terminate(code)}")
    print(revue)

    # 4. Agent Recherche (démonstration indépendante : Wikipedia + NewsAPI)
    separator("ÉTAPE 4 — Agent Recherche")
    reponse_recherche = ask_research_agent(
        "Qu'est-ce que le langage Python et y a-t-il des actualités récentes à son sujet ?"
    )
    print(reponse_recherche)

    # 5. Agent Analyste (démonstration indépendante : Chain-of-Thought + anomalies)
    separator("ÉTAPE 5 — Agent Analyste")
    temperatures = [21.5, 22.0, 21.8, 22.3, 57.0, 21.9, 22.1, 21.7, 22.4, 21.6]
    rapport_analyse = analyze_data(
        "Voici des relevés de température (°C) d'un capteur sur 10 jours consécutifs.",
        temperatures,
    )
    print(rapport_analyse)

    # 6. Protocole de communication inter-agents : délégation asynchrone, logging, consensus
    separator("ÉTAPE 6 — Protocole de communication (délégation, logging, consensus)")

    logger = CommunicationLogger(log_path=DEMO_LOG_PATH)
    delegator = TaskDelegator(logger=logger)

    print("\n[6a] Délégation asynchrone de 2 tâches en parallèle (recherche + analyse)...")
    start = time.perf_counter()
    delegator.delegate_many(
        [
            Task(type="recherche", message="Qu'est-ce que le protocole HTTP ?"),
            Task(type="analyse", message="Temps de réponse serveur (ms).", data=[120, 118, 125, 480, 122]),
        ]
    )
    elapsed = time.perf_counter() - start
    print(f"    -> Terminé en {elapsed:.1f}s (les 2 appels LLM tournent en parallèle, pas en série).")

    print("\n[6b] Logging : chaque message envoyé par ces agents a été journalisé.")
    entries = logger.read_all()
    print(f"    -> {len(entries)} messages dans logs/communications.jsonl, ex :")
    for entry in entries[:2]:
        print(f"       [{entry['from']} -> {entry['to']}] {str(entry['content'])[:70]}...")

    print("\n[6c] Consensus : 2 Réviseurs indépendants examinent le même code.")
    code_a_revoir = "def diviser(a, b):\n    return a / b\n"
    verdicts = collect_verdicts(
        f"Voici le code à relire :\n\n{code_a_revoir}",
        [ReviseurAgent(name="reviseur_1"), ReviseurAgent(name="reviseur_2")],
    )
    for v in verdicts:
        print(f"    [{v.agent_name}] approuvé={v.approved}")

    resultat = resolve_consensus(
        verdicts,
        arbitre=ReviseurAgent(name="arbitre"),
        task=f"Voici le code à relire :\n\n{code_a_revoir}",
    )
    print(f"    -> Consensus direct : {resultat['consensus']} | Décision finale : {resultat['decision']}")
    if resultat["arbitrage"]:
        print("    -> Désaccord détecté : un 3e agent a tranché (arbitrage).")

    # 7. Détection de boucle entre agents et demande de clarification (Bug 1)
    separator("ÉTAPE 7 — Détection de boucle entre agents")

    print("\n[7a] Essai réel : demande volontairement vague envoyée à la boucle Codeur/Réviseur.")
    print("     (un LLM moderne peut converger même sur une demande vague : le résultat")
    print("      ci-dessous est celui obtenu réellement, pas un cas forcé.)")
    resultat_boucle = run_code_review_loop("Fais quelque chose d'utile avec des données.", max_rounds=4)
    print(
        f"    -> Approuvé : {resultat_boucle['approuve']} | "
        f"Boucle détectée : {resultat_boucle['boucle_detectee']} (raison : {resultat_boucle['raison_boucle']}) | "
        f"Échanges : {resultat_boucle['nombre_echanges']}"
    )

    print("\n[7b] Illustration garantie du mécanisme : un Réviseur qui répète le même avis.")
    detector = LoopDetector(max_rounds=5)
    avis_repete = "Il manque une gestion d'erreur pour la division par zéro."
    detector.observe("reviseur", avis_repete)
    statut = detector.observe("reviseur", avis_repete)  # même avis deux fois -> aucun progrès
    print(f"    -> Boucle détectée : {statut.loop_detected} (raison : {statut.reason})")
    print("    -> Message de clarification qui serait envoyé à la place de continuer :\n")
    print(build_clarification_message(statut.reason))

    # 8. Agent orchestrateur (GroupChatManager) avec dashboard de monitoring
    separator("ÉTAPE 8 — Agent Orchestrateur (GroupChatManager)")
    print("Un seul appel : l'orchestrateur fait parler Planificateur, Codeur et Réviseur")
    print("automatiquement, dans le bon ordre, sans qu'on ait à les enchaîner nous-mêmes.\n")

    resultat_orchestre = run_orchestrated_task(
        "Écris une fonction Python qui vérifie si un nombre est premier.",
        max_round=10,
    )
    print(resultat_orchestre["report"].render())

    # 9. Résumé progressif et mémoire à long terme (Bug 7)
    separator("ÉTAPE 9 — Résumé progressif et mémoire à long terme")
    print("Historique fictif de 12 messages, où l'objectif initial n'apparaît qu'au tout")
    print("premier message — exactement le scénario du bug de perte de contexte.\n")

    historique_long = [
        {"role": "user", "name": "utilisateur", "content": "Objectif : construire une API de gestion de stock avec alertes de rupture."},
        {"role": "assistant", "name": "planificateur", "content": "1. Modèle Produit. 2. CRUD produits. 3. Endpoint stock. 4. Alerte si seuil dépassé."},
        {"role": "assistant", "name": "codeur", "content": "Modèle Produit créé : id, nom, quantite, seuil_alerte."},
        {"role": "user", "name": "reviseur", "content": "Il manque un champ derniere_maj."},
        {"role": "assistant", "name": "codeur", "content": "Ajouté derniere_maj (datetime)."},
        {"role": "user", "name": "reviseur", "content": "Bien, passons au CRUD."},
        {"role": "assistant", "name": "codeur", "content": "Endpoints POST/GET/PUT/DELETE /produits créés."},
        {"role": "user", "name": "reviseur", "content": "Il manque la validation quantite >= 0."},
        {"role": "assistant", "name": "codeur", "content": "Validator Pydantic ajouté."},
        {"role": "user", "name": "reviseur", "content": "Parfait, maintenant l'endpoint de mise à jour du stock."},
        {"role": "assistant", "name": "codeur", "content": "Endpoint PATCH /produits/{id}/stock créé."},
        {"role": "user", "name": "reviseur", "content": "Ajoute le déclenchement de l'alerte si quantite < seuil_alerte."},
    ]
    transform = ProgressiveSummaryTransform(max_messages=10, keep_recent=6)
    resultat_resume = transform.apply_transform(historique_long)

    print(f"{len(historique_long)} messages -> {len(resultat_resume)} (1 résumé + {len(resultat_resume) - 1} récents)\n")
    print("[Résumé généré par Azure OpenAI]")
    print(resultat_resume[0]["content"])
    objectif_conserve = "stock" in resultat_resume[0]["content"].lower()
    print(f"\nL'objectif initial est-il conservé dans le résumé ? {objectif_conserve}")

    memoire = LongTermMemory(path=DEMO_MEMORY_PATH)
    memoire.remember("demo", resultat_resume[0]["content"])
    print(f"Résumé persisté dans logs/memory.json (mémoire à long terme, survit à la conversation).")

    separator("DÉMO TERMINÉE")
