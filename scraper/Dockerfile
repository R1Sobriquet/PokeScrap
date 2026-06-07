# Conteneur scraper : Playwright (paquet + navigateur Chromium) installés
# explicitement, indépendamment de l'image de base. Construit depuis la racine du
# repo pour partager ./backend/app (services sourcing/matching/évaluation).
#   build: { context: ., dockerfile: scraper/Dockerfile }
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SCRAPER_SELECTORS_PATH=/app/selectors.yaml

WORKDIR /app

# Dépendances : backend (sqlalchemy, pymysql, bs4, pyyaml…) + APScheduler + playwright.
COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY scraper/requirements.txt /tmp/scraper-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt -r /tmp/scraper-requirements.txt

# Navigateur Chromium + dépendances système nécessaires à Playwright.
RUN playwright install --with-deps chromium

# Code applicatif partagé + code scraper + sélecteurs externalisés.
COPY backend/app /app/app
COPY scraper /app/scraper
COPY scraper/selectors.yaml /app/selectors.yaml

CMD ["python", "-m", "scraper.scraper"]
