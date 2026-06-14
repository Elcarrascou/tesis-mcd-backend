# Backend ML — Tesis MCD USACH

Servicio Python (FastAPI) que baja datos de mercado desde Yahoo Finance, corre
los modelos de machine learning de la tesis y escribe resultados en Supabase.

Parte del proyecto **Portafolio de Inversiones Gestionado por IA** (MCD USACH).
La web (React) vive en el repo `web/` → Vercel; este backend → Railway.

> **Por qué no va en Vercel:** los modelos reales (PyTorch, Prophet, XGBoost)
> pesan cientos de MB y requieren un proceso persistente + jobs programados,
> incompatible con el modelo serverless de Vercel. Railway corre un contenedor
> siempre encendido.

---

## Requisitos

- **Python 3.12** (vía lanzador `py`: `py -3.12`). No usar 3.14 todavía —
  algunas librerías de ML (Prophet) aún no la soportan bien.

## Setup local

```bash
# 1. Crear entorno virtual aislado con Python 3.12
py -3.12 -m venv .venv

# 2. Activarlo
#    PowerShell:
.venv\Scripts\Activate.ps1
#    bash (Git Bash):
source .venv/Scripts/activate

# 3. Instalar dependencias
python -m pip install -r requirements-dev.txt

# 4. Configurar secretos
copy .env.example .env        # luego pega la SUPABASE_SERVICE_ROLE_KEY

# 5. Levantar el servidor
uvicorn app.main:app --reload
```

- API:   http://localhost:8000
- Health: http://localhost:8000/health
- Docs:   http://localhost:8000/docs   (autogeneradas)

## Validación (lo mismo que correrá el CI)

```bash
ruff check .
pytest
```

---

## Estructura

```
backend/
├── app/
│   ├── main.py            # app FastAPI + CORS + routers
│   ├── config.py          # settings desde entorno (.env)
│   ├── api/health.py      # GET /health
│   ├── data/
│   │   ├── yahoo.py       # ingesta yfinance (get_history, get_quote)
│   │   └── features.py    # indicadores técnicos (RSI, SMA, vol, momentum, drawdown)
│   └── db/supabase_client.py  # cliente service_role → escribe predicciones/decisiones
├── tests/                 # pytest (health + features)
├── requirements.txt       # runtime
├── requirements-dev.txt   # + pytest, ruff
└── pyproject.toml         # config ruff + pytest
```

### Roadmap del backend
- **Fase A (esta):** esqueleto FastAPI + datos Yahoo + cliente Supabase. ✅
- **Fase B:** 4 modelos ML reales (LSTM, XGBoost, Prophet, Random Forest) + notebooks.
- **Fase C:** backtesting y métricas de evaluación.
- **Fase D:** agente (consolidación + routing LLM, Ollama local en dev).
- **Fase F:** Dockerfile + deploy Railway + cron diario.
