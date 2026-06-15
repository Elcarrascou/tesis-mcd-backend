# Backend ML — Tesis MCD USACH. Imagen de producción para Railway.
#
# Python 3.12 (NO 3.14: Prophet/cmdstanpy no la soportan bien).
# Instala runtime core (requirements.txt) + modelos ML (requirements-ml.txt).
# Los artefactos entrenados (artifacts/) se hornean en la imagen → arranque
# determinista, sin reentrenar en build.

FROM python:3.12-slim

# Deps de sistema para compilar/ejecutar Prophet (cmdstanpy) y libs científicas.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Capa de deps cacheable: copiar solo requirements primero.
COPY requirements.txt requirements-ml.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements-ml.txt

# Código + artefactos entrenados (lstm/xgboost/random_forest; Prophet refit on-the-fly).
COPY app ./app
COPY artifacts ./artifacts

EXPOSE 8000

# Railway inyecta $PORT. Fallback 8000 en local (docker run -p 8000:8000).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
