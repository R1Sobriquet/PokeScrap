# Le bot réutilise la couche données + services du backend (dispatcher,
# interactions) ; il est donc construit depuis la racine du repo.
#   build: { context: ., dockerfile: bot/Dockerfile }
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dépendances backend (sqlalchemy, pymysql…) + discord.py.
COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY bot/requirements.txt /tmp/bot-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt -r /tmp/bot-requirements.txt

COPY backend/app /app/app
COPY bot/bot.py /app/bot.py

CMD ["python", "bot.py"]
