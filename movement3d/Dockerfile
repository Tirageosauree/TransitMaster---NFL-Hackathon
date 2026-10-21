# Image de prediction cinematique 3D des deplacements NFL
FROM python:3.12-slim

# Dependances systeme pour kaleido/plotly (export PNG via Chromium headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer les dependances Python en premier (cache des couches Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kaleido >=1.0 a besoin d'un navigateur Chrome pour l'export PNG.
# plotly_get_chrome telecharge un Chrome headless compatible.
RUN plotly_get_chrome -y || true

# Copier le code source du moteur et le paquet du dashboard
COPY config.py data_loader.py kinematics.py analyzer.py visualizer.py main.py ./
COPY dashboard ./dashboard

# Emplacements des donnees (lecture seule) et des sorties, montes en volumes
# via docker-compose. Surchargeables par config.py qui lit ces variables.
ENV DATA_DIR=/data \
    OUTPUT_DIR=/app/output \
    DASH_HOST=0.0.0.0 \
    DASH_PORT=8050 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /app/output

EXPOSE 8050

# Par defaut : lance le dashboard interactif via gunicorn (serveur WSGI).
# `dashboard.app:server` est l'objet Flask expose par l'application Dash.
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "1", "--threads", "4", \
     "--timeout", "180", "dashboard.app:server"]
