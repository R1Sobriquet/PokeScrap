# Image officielle Playwright Python (navigateurs déjà installés), prête pour
# le scraping réel des jalons suivants. Au Jalon 1, le conteneur ne fait qu'un
# heartbeat de démarrage.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY scraper.py .

CMD ["python", "scraper.py"]
