# Le scheduler réutilise la couche données du backend (app.services), il est donc
# construit depuis la racine du repo pour embarquer ./backend/app.
#   build: { context: ., dockerfile: scheduler/Dockerfile }
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dépendances : celles du backend (sqlalchemy, pymysql, httpx, pyyaml…) + APScheduler.
COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY scheduler/requirements.txt /tmp/scheduler-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt -r /tmp/scheduler-requirements.txt

# Code applicatif partagé + entrypoint scheduler.
COPY backend/app /app/app
COPY scheduler/scheduler.py /app/scheduler.py

CMD ["python", "scheduler.py"]
