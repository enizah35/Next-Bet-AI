# Utilise une image Python légère et stable
FROM python:3.11-slim

# Évite de générer des fichiers .pyc et permet l'affichage des logs en temps réel
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Définit le port par défaut pour Hugging Face Spaces
ENV PORT 7860
ENV PYTHONPATH=/app

# Répertoire de travail
WORKDIR /app

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copie et installation des dépendances Python
COPY requirements.txt .
# On installe une version CPU de torch pour rester sous des limites de taille raisonnables
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Copie le reste du code source
COPY . .

# Commande de démarrage pour Google Cloud Run
# On utilise uvicorn avec le port dynamique fourni par l'environnement
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}"]
