Systeme multi-agnets+autogen+azure openai


Bienvenue ! Merci de vouloir contribuer à ce projet. Ce guide explique comment bien contribuer en suivant les bonnes pratiques Git et notre workflow.

---

## 📑 Table des Matières

1. [Avant de Commencer](#avant-de-commencer)
2. [Setup Local](#setup-local)
3. [Workflow Git](#workflow-git)
4. [Types de Commits](#types-de-commits)
5. [Nommage des Branches](#nommage-des-branches)
6. [Pull Requests](#pull-requests)
7. [Bonnes Pratiques](#bonnes-pratiques)
8. [Checklist](#checklist)
9. [Dépannage](#dépannage)

---

## ✅ Avant de Commencer

### Prérequis

- Python 3.9+
- Git installé et configuré
- Compte GitHub
- VS Code (optionnel mais recommandé)

### Lire la Documentation

- ✅ Lis [README.md](README.md) pour comprendre le projet
- ✅ Teste le projet localement avant de contribuer

### Cloner le Repository

```bash
# Cloner
git clone https://github.com/tonusername/autogen-naval.git
cd autogen-naval

# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Vérifier que tout fonctionne
python -m pytest tests/
```

---

## 🔧 Setup Local

### Configuration Git (Une seule fois)

```bash
# Configure ton identité
git config --global user.name "Ton Nom"
git config --global user.email "tonmail@example.com"

# Configure un bon éditeur pour les messages
git config --global core.editor "code"

# Configure les fins de ligne (IMPORTANT)
git config --global core.autocrlf true  # Windows
# ou
git config --global core.autocrlf false # Linux/Mac
```

---

## 🌿 Workflow Git

### Flux Standard (5 étapes)

#### **Étape 1 : Créer une Branche**

```bash
# Mets-toi à jour depuis develop
git checkout develop
git pull origin develop

# Crée une nouvelle branche (voir "Nommage des Branches")
git checkout -b feature/ajouter-logging-agents
```

#### **Étape 2 : Coder et Tester**

```bash
# Fais ton travail dans VS Code
# Teste tout localement AVANT de commiter
python -m pytest tests/test_planificateur.py -v
```

#### **Étape 3 : Commiter avec Bons Messages**

```bash
# Vois les fichiers modifiés
git status

# Ajoute les fichiers
git add agents/planificateur.py config/llm_config.py

# Commit structuré
git commit -m "feat: ajouter logging structuré pour tous les agents

- Ajout de logging via loguru
- Chaque agent log ses actions
- Logs enregistrés dans logs/agents.log

Closes #42"
```

#### **Étape 4 : Pousser sur GitHub**

```bash
# Pousse ta branche
git push -u origin feature/ajouter-logging-agents
```

#### **Étape 5 : Créer une Pull Request**

Va sur GitHub → Pull Requests → New Pull Request

---

## 📝 Types de Commits ACCEPTÉS

| Type | Utilisation | Exemple |
|------|-------------|---------|
| **feat** | Nouvelle fonctionnalité | `feat: ajouter agent Recherche` |
| **fix** | Correction de bug | `fix: corriger boucle infinie` |
| **docs** | Documentation | `docs: ajouter guide architecture` |
| **refactor** | Refactorisation | `refactor: simplifier config` |
| **test** | Tests unitaires | `test: ajouter tests agents` |
| **chore** | Maintenance (dépendances, config) | `chore: update requirements.txt` |
| **perf** | Optimisation | `perf: optimiser routing engine` |
| **style** | Formatage du code | `style: appliquer black formatter` |
| **ci** | Configuration CI/CD | `ci: ajouter workflow pytest` |

---

### Exemples pour Chaque Type

#### 1️⃣ feat – Nouvelle Fonctionnalité

```bash
git commit -m "feat(agents): ajouter agent Recherche

- Implémente RechercheAgent héritant de AutoGenBaseAgent
- Peut chercher et résumer des informations
- Intégration avec GroupChatManager
- Tests unitaires inclus"
```

#### 2️⃣ fix – Correction de Bug

```bash
git commit -m "fix(agents): corriger boucle infinie entre Codeur et Réviseur

Avant: Les agents échangeaient indéfiniment sans converger
Après: LoopDetector arrête après 5 itérations max
Fixes: #42"
```

#### 3️⃣ docs – Documentation

```bash
git commit -m "docs: ajouter guide d'architecture multi-agents

- Explique le flux entre agents
- Diagramme de l'orchestrateur
- Exemples d'utilisation
- FAQ pour problèmes courants"
```

#### 4️⃣ refactor – Refactorisation

```bash
git commit -m "refactor(config): simplifier configuration LLM

- Extraire la config en dict réutilisable
- Réduire duplication entre agents
- Aucune changement fonctionnel
- Améliore la maintenabilité"
```

#### 5️⃣ test – Tests

```bash
git commit -m "test(agents): ajouter tests pour agent Planificateur

- Test: création d'un agent
- Test: génération d'un plan
- Test: intégration avec GroupChat
- Coverage: 85% → 92%"
```

#### 6️⃣ chore – Maintenance

```bash
git commit -m "chore(deps): mettre à jour pyautogen 0.2 → 0.2.5

- Fixes: plusieurs bugs de stabilité
- Security: patch pour CVE-2024-1234"
```

#### 7️⃣ perf – Performance

```bash
git commit -m "perf(groupchat): optimiser sélection d'agents

- Avant: O(n²) complexity
- Après: O(n) avec cache
- Résultat: -60% temps de réponse"
```

#### 8️⃣ style – Formatage

```bash
git commit -m "style: appliquer black formatter et isort

- Formatter le code Python
- Organiser les imports
- Aucune changement logique"
```

#### 9️⃣ ci – CI/CD

```bash
git commit -m "ci: ajouter workflow pytest sur pull requests

- Lancer tests à chaque PR
- Fail si coverage < 80%
- Notify sur Slack si fail"
```

---

## 🌿 Nommage des Branches

### Format Standard