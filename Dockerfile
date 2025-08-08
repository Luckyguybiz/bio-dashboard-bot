FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml /app/
RUN pip install --upgrade pip && pip install fastapi uvicorn[standard] sqlalchemy alembic psycopg[binary] celery redis python-telegram-bot google-api-python-client pydantic-settings
COPY . /app
CMD ["uvicorn", "scc.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
