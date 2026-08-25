"""
Interface Streamlit du système multi-agents (US 3.2).

Usage: streamlit run streamlit_app.py
"""
import os
import sys

sys.path.append(os.path.dirname(__file__))

import streamlit as st

from agents.analyste_agent import build_analyste_team
from agents.research_agent import build_research_team
from protocol.router import ROUTE_ANALYSE, ROUTE_DEVELOPPEMENT, ROUTE_RECHERCHE, ROUTE_RECHERCHE_ET_ANALYSE
from protocol.routing_engine import RoutingEngine

STEP_LABELS = {
    "recherche": "🌐 Recherche",
    "planificateur": "🗂️ Planificateur",
    "codeur": "💻 Codeur",
    "analyse": "📊 Analyse",
    "reviseur": "🔍 Réviseur",
}

st.set_page_config(page_title="Système Multi-Agents", page_icon="🤖", layout="wide")

AGENT_STYLE = {
    "utilisateur": {"avatar": "🧑‍💻", "color": "#64748b"},
    "chat_manager": {"avatar": "🧭", "color": "#64748b"},
    "planificateur": {"avatar": "🗂️", "color": "#6366f1"},
    "codeur": {"avatar": "💻", "color": "#8b5cf6"},
    "reviseur": {"avatar": "🔍", "color": "#10b981"},
    "recherche": {"avatar": "🌐", "color": "#0ea5e9"},
    "research_executor": {"avatar": "🌐", "color": "#0ea5e9"},
    "analyste": {"avatar": "📊", "color": "#f59e0b"},
    "analyste_executor": {"avatar": "📊", "color": "#f59e0b"},
}

MODES = {
    "Développement (Planificateur → Codeur → Réviseur)": "dev",
    "Recherche (Wikipedia + NewsAPI)": "recherche",
    "Analyse de données (statistiques + anomalies)": "analyse",
}

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

.hero {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 55%, #0ea5e9 100%);
    padding: 2.2rem 2.4rem;
    border-radius: 18px;
    color: white;
    margin-bottom: 1.6rem;
    box-shadow: 0 10px 30px -12px rgba(79, 70, 229, 0.45);
}
.hero h1 { margin: 0 0 0.35rem 0; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.02em; }
.hero p { margin: 0; opacity: 0.92; font-size: 0.98rem; }

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    color: white;
    margin-right: 6px;
}

.result-card {
    background: var(--background-color, #ffffff);
    border: 1px solid rgba(120,120,140,0.18);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 6px 20px -14px rgba(0,0,0,0.25);
}

.outcome-approuve { color: #10b981; font-weight: 700; }
.outcome-boucle_detectee { color: #f59e0b; font-weight: 700; }
.outcome-erreur, .outcome-timeout { color: #ef4444; font-weight: 700; }
.outcome-max_round_atteint { color: #f59e0b; font-weight: 700; }
.outcome-termine { color: #6366f1; font-weight: 700; }

section[data-testid="stSidebar"] { border-right: 1px solid rgba(120,120,140,0.15); }

div[data-testid="stChatMessage"] {
    border-radius: 14px;
    box-shadow: 0 2px 10px -6px rgba(0,0,0,0.15);
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def make_ui_hook(container):
    """Hook AutoGen (process_message_before_send) qui affiche chaque message en
    direct dans l'interface, au fur et à mesure des échanges entre agents."""

    def hook(sender, message, recipient, silent):
        content = message.get("content") if isinstance(message, dict) else message
        # Les proxys internes ("proxy_planificateur", etc.) ne font que relayer le
        # message précédent vers l'agent réel : les masquer évite les doublons.
        if sender.name.startswith("proxy_"):
            return message
        if content and str(content).strip():
            style = AGENT_STYLE.get(sender.name, {"avatar": "🤖", "color": "#64748b"})
            with container:
                with st.chat_message(sender.name, avatar=style["avatar"]):
                    st.markdown(
                        f"<span class='badge' style='background:{style['color']}'>{sender.name}</span> "
                        f"<span style='opacity:0.6;font-size:0.8rem'>→ {recipient.name}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(content)
        return message

    return hook


def render_outcome(outcome: str) -> str:
    labels = {
        "approuve": "✅ Approuvé",
        "boucle_detectee": "⚠️ Boucle détectée — clarification demandée",
        "max_round_atteint": "⏱️ Plafond de tours atteint",
        "timeout": "⏱️ Timeout",
        "erreur": "❌ Erreur",
        "termine": "🏁 Terminé",
    }
    css_class = f"outcome-{outcome}"
    label = labels.get(outcome, outcome or "—")
    return f"<span class='{css_class}'>{label}</span>"


# --- Sidebar ---
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    mode_label = st.selectbox("Type de requête", list(MODES.keys()))
    mode = MODES[mode_label]

    max_round = 10
    if mode == "dev":
        max_round = st.slider("Nombre max de tours (Codeur ↔ Réviseur)", 4, 20, 10)

    st.markdown("---")
    st.caption("Système Multi-Agents · AutoGen + Azure OpenAI")
    st.caption("Stage Smartovate 2026")

# --- Header ---
st.markdown(
    """
    <div class="hero">
        <h1>🤖 Système Multi-Agents</h1>
        <p>Soumettez votre requête et suivez les agents collaborer en temps réel.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Formulaire de requête ---
with st.form("requete_form"):
    demande = st.text_area(
        "Votre requête",
        height=100,
        placeholder="Ex : Écris une fonction Python qui vérifie si un nombre est premier.",
    )
    data_input = None
    if mode == "analyse":
        data_input = st.text_input(
            "Données numériques (séparées par des virgules)",
            placeholder="21.5, 22.0, 21.8, 57.0, 21.9",
        )
    submitted = st.form_submit_button("🚀 Envoyer", use_container_width=True)

if submitted:
    if not demande.strip():
        st.warning("Merci de saisir une requête.")
        st.stop()
    if mode == "analyse" and not (data_input and data_input.strip()):
        st.warning("Merci de fournir des données numériques pour ce mode.")
        st.stop()

    st.markdown("### 💬 Échanges entre agents")
    chat_container = st.container(height=480, border=True)
    ui_hook = make_ui_hook(chat_container)

    resultat_final = None
    outcome = None
    error = None
    routing_result = None

    try:
        with st.spinner("Les agents travaillent..."):
            if mode == "dev":
                # --- RoutingEngine (US 10) : décide, avant tout, quel(s) agent(s)
                # mobiliser. Une demande purement informative (définition,
                # actualités, statistiques) est traitée directement par Recherche
                # et/ou Analyste, sans passer par le Réviseur — qui n'aurait alors
                # aucun code à évaluer et forcerait le Codeur à inventer un exemple
                # sans rapport juste pour lui en donner un. Si du code est demandé,
                # les 5 agents s'enchaînent : Recherche -> Planificateur -> Codeur
                # -> Analyse -> Réviseur, chacun consommant réellement la sortie du
                # précédent. Codeur/Réviseur rebouclent (US 2.2) si rejeté, jusqu'à
                # approbation, détection de boucle (Bug 1), ou max_round atteint.
                engine = RoutingEngine(ui_hook=ui_hook, max_rounds=max_round)
                routing_result = engine.route(demande)
                resultat_final = routing_result.resultat_final

                if routing_result.route == ROUTE_DEVELOPPEMENT:
                    if routing_result.boucle_detectee:
                        outcome = "boucle_detectee"
                    elif routing_result.approuve:
                        outcome = "approuve"
                    else:
                        outcome = "termine"
                else:
                    outcome = "termine"

            elif mode == "recherche":
                assistant, executor = build_research_team()
                for agent in (assistant, executor):
                    agent.register_hook("process_message_before_send", ui_hook)
                result = executor.initiate_chat(assistant, message=demande)
                resultat_final = result.chat_history[-1]["content"] if result.chat_history else None
                outcome = "termine"

            else:  # analyse
                data = [float(x.strip()) for x in data_input.split(",") if x.strip()]
                assistant, executor = build_analyste_team()
                for agent in (assistant, executor):
                    agent.register_hook("process_message_before_send", ui_hook)
                message = f"{demande}\n\nDonnées : {data}"
                result = executor.initiate_chat(assistant, message=message)
                resultat_final = result.chat_history[-1]["content"] if result.chat_history else None
                outcome = "termine"

    except Exception as exc:  # noqa: BLE001 - afficher l'erreur plutôt que de crasher l'UI
        error = str(exc)
        outcome = "erreur"

    if routing_result is not None:
        st.markdown("### 🔎 Routage")
        if routing_result.route == ROUTE_DEVELOPPEMENT:
            chemin = " → ".join(STEP_LABELS.get(s.agent, s.agent) for s in routing_result.steps)
            st.markdown(f"**Chaîne complète empruntée** : {chemin}")
            with st.expander("Détail de chaque étape"):
                for step in routing_result.steps:
                    st.markdown(f"**{STEP_LABELS.get(step.agent, step.agent)}**")
                    st.markdown(step.content)
                    st.divider()
        elif routing_result.route == ROUTE_RECHERCHE:
            st.info(
                "Requête purement informative : traitée directement par l'agent Recherche, "
                "sans passer par le pipeline de développement."
            )
        elif routing_result.route == ROUTE_ANALYSE:
            st.info(
                "Requête purement analytique : traitée directement par l'agent Analyste, "
                "sans passer par le pipeline de développement."
            )
        else:
            st.info(
                "Requête informative combinée : traitée par Recherche + Analyste, "
                "sans passer par le pipeline de développement."
            )

    st.markdown("### 📋 Résultat")
    st.markdown(f"Statut : {render_outcome(outcome)}", unsafe_allow_html=True)

    if error:
        st.error(f"Une erreur est survenue : {error}")
    elif resultat_final:
        st.markdown(f'<div class="result-card">{resultat_final}</div>', unsafe_allow_html=True)

        extension = "py" if "```python" in resultat_final else "txt"
        st.download_button(
            "⬇️ Exporter le résultat",
            data=resultat_final,
            file_name=f"resultat.{extension}",
            mime="text/plain",
            use_container_width=True,
        )
    else:
        st.info("Aucun résultat final produit.")
