# Image de base : Python 3.12, alignée avec l'environnement de développement du projet.
FROM python:3.12-slim

WORKDIR /app

# Copier uniquement requirements.txt d'abord : Docker met cette étape en cache et
# ne réinstalle les dépendances que si ce fichier change, pas à chaque édition du code.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code applicatif (.dockerignore exclut venv/, .git/, .env, etc.).
COPY . .

EXPOSE 8501

# Mode headless : pas de navigateur à ouvrir dans le conteneur.
# Écoute sur toutes les interfaces (0.0.0.0), pas seulement localhost, pour être
# accessible depuis l'extérieur du conteneur via le port exposé.
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Les identifiants Azure OpenAI (.env) ne sont PAS copiés dans l'image (cf.
# .dockerignore) : ils doivent être fournis à l'exécution, ex:
#   docker run --env-file .env -p 8501:8501 <image>
CMD ["streamlit", "run", "streamlit_app.py"]
