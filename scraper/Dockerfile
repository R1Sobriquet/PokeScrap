# Conteneur scraper : image Playwright (navigateurs préinstallés). Construit depuis
# la racine du repo pour partager ./backend/app (services sourcing/matching/évaluation).
#   build: { context: ., dockerfile: scraper/Dockerfile }
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SCRAPER_SELECTORS_PATH=/app/selectors.yaml

WORKDIR /app

# Dépendances backend (sqlalchemy, pymysql, beautifulsoup4, pyyaml…) + APScheduler.
COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY scraper/requirements.txt /tmp/scraper-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt -r /tmp/scraper-requirements.txt

# Code applicatif partagé + code scraper + sélecteurs externalisés.
COPY backend/app /app/app
COPY scraper /app/scraper
COPY scraper/selectors.yaml /app/selectors.yaml

CMD ["python", "-m", "scraper.scraper"]
