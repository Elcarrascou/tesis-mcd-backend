# HANDOFF — Tesis MCD USACH · Portafolio de Inversiones Gestionado por IA

Documento de traspaso para continuar el proyecto en una nueva instancia de chat.
Última actualización: 2026-06-15 (post Fase F código). Autor: Daniel Carrasco U. (dacarrascu@gmail.com).

**Estado en una línea:** Web en producción. Backend **Fases A→F COMPLETAS** y
desplegado en Railway (https://tesis-mcd-backend-production.up.railway.app). Fase E
cerrada: la web (`StockAnalyzer`) consume `/predict/{symbol}` real vía `VITE_API_URL`.
Pendientes menores: secrets del repo para el cron (si no se setearon) y los ítems
"DEJAR PARA EL FINAL" (Alpaca, LLM de pago, docs).
Commits backend: `52612a4` (A) → `80c92d3` (B) → `cb6e89e` (C) → `7afcb59` (D)
→ `11b285a` (HANDOFF E) → `d4806d6` (F). Commits web Fase E: `b4a33f6` → `0cffc32`.

---

## 1. Qué es el proyecto

Proyecto de Título del **Magíster en Ciencia de Datos (MCD), USACH**. Sistema web
que integra un **agente de IA** + **4 modelos de machine learning** para analizar,
predecir y apoyar decisiones sobre un portafolio de acciones en tiempo real. Foco:
índice chileno **IPSA** y su relación con el **Dow Jones**.

Dos dominios académicos:
- **Machine Learning:** LSTM (precio), XGBoost (señal compra/venta), Prophet
  (tendencia/estacionalidad), Random Forest (riesgo).
- **IA agéntica:** agente "OpenClaw" consolida las 4 predicciones, razona con
  motores LLM (Claude/GPT/Ollama) y genera recomendaciones explicables.

---

## 2. Estructura de repos (IMPORTANTE)

Son **DOS repos git separados** dentro de `C:\Proyecto desarrollos antigravity\Tesis MCD USACH\`:

| Carpeta | Repo git | Deploy | Estado |
|---|---|---|---|
| `web/` | `Elcarrascou/Tesis-MCD-USACH` (GitHub) | Vercel | ✅ Producción |
| `backend/` | `Elcarrascou/tesis-mcd-backend` (GitHub, rama `main`) | Railway (Fase F) | ✅ A→D + en GitHub |

- **OJO ramas:** el backend local usa rama `master`, el remoto usa `main`
  (`git push -u origin master:main` ya configurado, tracking `master`↔`origin/main`).
- **Push backend sin `gh`:** `gh` NO está en PATH y el GitHub MCP dio "Bad credentials".
  El push funcionó vía Git Credential Manager de Windows (mismo user Elcarrascou que
  el repo web). Si un push falla por auth, usar git directo (no `gh`/MCP).
- **Seguridad verificada antes de subir:** `.env` ignorado y nunca en historial;
  solo `.env.example` (placeholders) trackeado. Escaneado todo el historial: sin
  service_role JWT filtrado.

- El git root de `web/` está atado a Vercel → por eso `backend/` es repo aparte
  (un monorepo exigiría re-enraizar y romper la integración con Vercel).
- **El backend NO va en Vercel:** los modelos reales (PyTorch/Prophet) son muy
  pesados para serverless. Railway corre un contenedor persistente.

---

## 3. Estado actual

### Web (`web/`) — ✅ COMPLETA en producción
- URL: https://tesis-mcd-usach.vercel.app · Portal: `/portal` (`demo@tesis-mcd.cl` / `Portafolio2026`)
- Vite + React 19 + TS + Tailwind v3 + React Router + Supabase JS.
- Sitio marketing (`/`, `/solucion`) + Portal autenticado (6 páginas: Dashboard,
  Movimientos, Decisiones IA, Ganancias, Modelos ML, Analytics) + auth + realtime
  + cotizaciones Yahoo en vivo. Edge function `yahoo-finance` (inferencia DEMO).
- Reglas de diseño y workflow en `web/CLAUDE.md` (leer antes de tocar la web).

### Backend (`backend/`) — 🚧 Fases A, B, C y D listas
- **Python 3.12** (vía `py -3.12`). NO usar 3.14 (Prophet no la soporta bien).
  Ambas conviven. venv en `backend/.venv` (gitignored).
- **Fase A** (commit `52612a4`): FastAPI (`/health`, `/`), `config.py`
  (pydantic-settings), `data/yahoo.py` (yfinance), `data/features.py`
  (RSI/SMA/vol/momentum/drawdown), `db/supabase_client.py` (service_role → escribe).
- **Fase B** (commit `80c92d3`): 4 modelos ML reales entrenados sobre 5y de Yahoo,
  validados escribiendo 24 predicciones reales a Supabase.

#### Modelos (`app/models/`, interfaz común `BaseModel`)
| Modelo | Archivo | prediction_type | Horizonte | Confianza |
|---|---|---|---|---|
| LSTM (PyTorch) | `lstm_price.py` | `price` | 5d | precisión direccional val |
| XGBoost | `xgb_signal.py` | `signal` (buy/sell/hold) | 5d | prob. de clase |
| Prophet | `prophet_trend.py` | `trend` | 30d | ancho de intervalo |
| Random Forest | `rf_risk.py` | `risk` (bajo/medio/alto) | 20d | votación árboles |

#### Pipeline
- `app/pipeline/train.py` → entrena los 4, guarda en `artifacts/` (gitignored).
- `app/pipeline/predict.py` → inferencia; `--write` inserta en `ml_predictions`.
- `app/constants.py` → `UNIVERSE = [NVDA, MSFT, AAPL, TSLA, GOOGL, SQM]`.
- `app/ml/dataset.py` → matriz de features + etiquetas supervisadas.

---

## 4. Servicios y credenciales

- **Supabase** proyecto `PT_MCD_USACH_DCU` (id `xzedmtnouzarsslyglbe`), free tier.
  - 5 tablas (todas RLS ON): `portfolio`, `movements`, `ai_decisions`,
    `ml_predictions`, `performance`.
  - `ml_predictions`: `symbol, model[lstm|xgboost|prophet|random_forest],
    prediction_type, predicted_value, signal, confidence, horizon_days, predicted_at`.
  - `ai_decisions`: `symbol, action[buy|sell|hold|rebalance], confidence, rationale,
    engine, created_at`.
  - Backend escribe con **service_role** (salta RLS). Key en `backend/.env`.
- **Vercel** proyecto `web` (`prj_Nxsq6ZuPQpNF0rokSFyNocicnNZQ`). Deployment
  Protection debe estar OFF (sitio público).

---

## 5. Comandos clave (backend)

Desde `backend/` con venv activo (`.venv\Scripts\Activate.ps1`):
```powershell
$env:PYTHONUTF8=1                       # Windows: evita crash de encoding
python -m app.pipeline.train            # reentrena los 4 modelos
python -m app.pipeline.predict          # dry-run (imprime, no escribe)
python -m app.pipeline.predict --write  # + escribe a Supabase
python -m app.pipeline.backtest --write # Fase C: backtest → model_metrics
python -m app.pipeline.decide --write   # Fase D: agente → ai_decisions
uvicorn app.main:app --reload           # API local :8000 (/docs, /health)
ruff check .                            # lint (lo que correrá el CI)
pytest                                  # tests
```

---

## 6. GOTCHAS resueltos (no repetir)

1. **Prophet en Windows** fallaba `'Prophet' object has no attribute 'stan_backend'`
   → cmdstanpy no encontraba `tbb.dll`. Fix: `prophet_trend._ensure_tbb_on_path()`
   agrega `prophet/stan_model/cmdstan-*/.../tbb` al PATH antes de importar Prophet.
2. **`.env`**: se había guardado como `.env.txt` (Windows oculta extensiones).
   Debe ser exactamente `.env`. Claves: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
3. **Consola Windows (cp1252)** no imprime `✓`/emojis → usar ASCII en `print()`.
   Correr scripts con `PYTHONUTF8=1`.
4. **Python 3.14** instalado pero NO usarlo (Prophet). Usar `py -3.12`.

---

## 7. LO QUE FALTA — plan de fases

### Fase C — Backtesting y evaluación ✅ (núcleo listo)
Material clave para defender ante el comité.
- ✅ `app/ml/metrics.py`: métricas puras (RMSE, MAE, MAPE, dir-acc, accuracy,
  F1 macro, retorno acumulado, Sharpe, max drawdown). Testeadas en `tests/test_metrics.py`.
- ✅ `app/pipeline/backtest.py`: walk-forward **sin look-ahead** (ventana expansiva
  con reentrenamiento por folds; cada predicción usa solo el pasado, igual que
  producción vía `predict_one`).
  - LSTM/Prophet → RMSE/MAE/MAPE/dir-acc · XGBoost/RF → accuracy/F1.
  - Backtest de estrategia long-only (señal XGBoost) vs buy&hold del universo y
    benchmarks de contexto.
  - CLI: `python -m app.pipeline.backtest [--models …] [--symbols …]
    [--retrain-folds N] [--max-symbols N] [--no-strategy] [--write]`.
- ✅ Tabla `model_metrics` en Supabase (RLS, lectura pública) + `insert_metrics`.
  `--write` la puebla. **PENDIENTE:** correr `--write` completo (6 símbolos, sin
  reducir) para llenar la tabla — Prophet es lento (~10-15 min por refit Stan).
- ✅ `notebooks/04_backtest_eval.ipynb` (eval + estrategia + gráficos).
- **OJO IPSA:** Yahoo descontinuó `^IPSA` en 2019. Se usa el ETF **ECH** (iShares
  MSCI Chile) como proxy del IPSA. `^DJI` (Dow) sigue vigente. Benchmarks en
  `backtest.BENCHMARKS`.
- **Mejora futura:** AUC ROC multiclase requiere exponer probabilidades en
  `predict_one` (hoy solo top-class + confianza).

### Fase D — Agente IA "OpenClaw" ✅ (núcleo listo)
- ✅ `app/agent/consolidate.py`: fusiona las 4 predicciones → **score unificado**
  en [-1,1] (voto direccional ponderado LSTM/XGBoost/Prophet, riesgo del RF como
  multiplicador) → acción `buy/sell/hold/rebalance` + confianza + rationale
  determinista. Auditable y reproducible (la decisión NO la inventa el LLM).
  Testeado en `tests/test_consolidate.py`.
- ✅ `app/agent/prompts.py` + `llm_router.py`: el LLM solo **reescribe** el rationale.
  Routing `ollama` (local, gratis, default) / `anthropic` / `openai`, con **fallback
  limpio a `rule-based`** si el motor falla o no está (el pipeline nunca se rompe).
  Config en `config.py` (`llm_engine`, `ollama_url/model`, `*_api_key`).
- ✅ `app/agent/execute.py`: stub de ejecución — `intended_order()` registra la orden
  intencionada (`status='intended'`, `broker=None`) SIN tocar Alpaca.
- ✅ `app/pipeline/decide.py`: pipeline CLI `python -m app.pipeline.decide
  [--symbols …] [--engine …] [--orders] [--write]`. `--write` inserta en
  `ai_decisions`. Validado: 6 decisiones reales escritas (engine `rule-based`,
  Ollama no estaba corriendo → fallback OK).
- **Para usar Ollama:** instalar Ollama + `ollama pull llama3.1`, dejarlo corriendo;
  el default ya apunta a `localhost:11434`. Para Claude/GPT: setear las keys en `.env`
  y `--engine anthropic|openai` (dejar para el final, son de pago).
- **Mejora futura:** dimensionar la orden (qty) según portfolio/peso; hoy el stub no
  calcula cantidad.

### Fase E — Integración web ↔ backend ✅ COMPLETA (salvo lo que depende del deploy)
Objetivo: que la web muestre lo real que ya produce el backend. Datos en Supabase:
`ml_predictions`, `model_metrics` (Fase C), `ai_decisions` (6 reales `rule-based` + 5 demo).
- ✅ **Página "Evaluación"** del portal (`web/src/pages/portal/PortalEvaluacion.tsx`,
  ruta `/portal/evaluacion`): lee `model_metrics` vía `queries.getModelMetrics`
  (Supabase directo, RLS público, sin backend). Tabla estrategia IA vs Buy&Hold/
  benchmarks ECH/^DJI (cum_return/Sharpe/maxDD) + cards por modelo (LSTM/Prophet/
  XGBoost/RF) con métricas agregadas del walk-forward (symbol NULL) y desglose por
  símbolo expandible. Ítem de nav `ClipboardCheck` agregado en `PortalLayout.tsx`;
  `database.types.ts` regenerado con `model_metrics`. Commit web `b4a33f6`.
- ✅ **Decisiones IA del portal:** `/portal/decisiones` ya leía `getAiDecisions(100)`
  ordenado por `created_at` desc → muestra reales (`rule-based`) + demo. Sin cambios.
- ✅ **Edge function versionada:** `web/supabase/functions/yahoo-finance/index.ts`
  (+ README). Antes solo vivía en Supabase remoto. `eslint.config.js` ignora
  `supabase/functions` (runtime Deno). Commit web `0cffc32`.
- ⏳ **PENDIENTE (depende de Fase F):** endpoint FastAPI `/predict/{symbol}`
  (inferencia on-demand) + apuntar el `StockAnalyzer` del portal (`web/src/components/
  portal/StockAnalyzer.tsx`) al backend real en vez de la edge function demo
  (`action:'predict'`). Requiere backend desplegado o túnel local → hacer en Fase F.
- **OJO web:** repo `web/` aparte. Leer `web/CLAUDE.md` antes de tocarla. Workflow
  obligatorio: `npm run lint && npm run build`, commit, push, `npx vercel deploy
  --prod --yes`, `npx vercel alias set <url> tesis-mcd-usach.vercel.app`.

### Fase F — Deploy backend (sin servicios de pago) 🚧 CÓDIGO LISTO, falta acción manual
Repo: `Elcarrascou/tesis-mcd-backend` (rama `main`). Commit Fase F: `d4806d6`.

**✅ Hecho en código (commiteado y pusheado):**
1. ✅ **`Dockerfile`** — `python:3.12-slim`, `build-essential`/gcc/g++ para
   Prophet/cmdstanpy, instala `requirements-ml.txt` (core+ML, sin dev), copia `app/`
   + `artifacts/`, `CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
   `.dockerignore` excluye venv/.env/tests/notebooks/docs.
2. ✅ **Endpoint `GET /predict/{symbol}`** (`app/api/predict.py`, montado en
   `app/main.py`): inferencia on-demand de los 4 modelos. Modelos en singleton
   `lru_cache` (carga 1 vez/proceso); Prophet refit on-the-fly. Lectura, NO escribe.
   Respuesta `{symbol, in_universe, predictions[], errors{}}`. Probado vía TestClient
   (NVDA → 200, 4 modelos OK).
3. ✅ **Estrategia de artefactos DECIDIDA:** `lstm_price.pt`/`xgboost_signal.joblib`/
   `random_forest_risk.joblib` (6.5MB) **commiteados** (force-add sobre gitignore) →
   imagen determinista, sin reentrenar en build. Prophet no necesita artefacto.
4. ✅ **CI** (`.github/workflows/ci.yml`): `ruff check .` + `pytest` en py3.12 (push/PR
   a `main`). Instala `requirements-ml` + `requirements-dev`. **24 tests** (se sumó
   `tests/test_predict.py`, mockea Yahoo/modelos → sin red en CI).
5. ✅ **Cron** (`.github/workflows/predict-cron.yml`): GitHub Actions scheduled
   `0 11 * * 1-5` (~07:00 Chile) + `workflow_dispatch` → `python -m app.pipeline.predict
   --write`. Gratis, usa los artefactos del repo. Alternativa al cron de Railway.

**⏳ PENDIENTE (acción manual del usuario — no automatizable desde aquí):**
- **A. Secrets del repo GitHub** (para que corra el cron): en `tesis-mcd-backend` →
  Settings → Secrets and variables → Actions → New repository secret:
  `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` (valores en `backend/.env`).
- **B. Railway:** crear proyecto → Deploy from GitHub repo `Elcarrascou/tesis-mcd-backend`
  (detecta el `Dockerfile`). Variables: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
  `PYTHONUTF8=1` (opcional `LLM_ENGINE=rule-based`). Healthcheck path `/health`.
  Vigilar build (imagen PyTorch+Prophet pesada) y límites free tier.
- **C. Verificar deploy:** `GET <railway-url>/health` → `{"status":"ok"}`;
  `GET <railway-url>/predict/NVDA` → 4 predicciones. Medir latencia de arranque
  (carga de modelos).
- ✅ **D. Fase E cerrada:** `StockAnalyzer` (commit web `90a4252`) muestra los 4
  modelos reales vía `GET /predict/{symbol}` (env `VITE_API_URL` en Vercel = URL
  Railway). Backend live en **https://tesis-mcd-backend-production.up.railway.app**
  (`/health` ok, `/predict/NVDA` 4 modelos, CORS para el dominio vercel ok). Web
  desplegada y aliaseada a tesis-mcd-usach.vercel.app. Panel híbrido: viz demo Yahoo
  + panel "Modelos entrenados" reales (degrada solo a demo si el backend cae).

### DEJAR PARA EL FINAL (instrucción explícita del usuario)
- 🔌 **Alpaca** — ejecución real de órdenes.
- 🔌 **OpenClaw en Hostinger** + LLM keys de pago (Claude/GPT) + Telegram/WhatsApp.
- 🔌 **Supabase de pago** — escalar del free tier.
- 📄 **Anteproyecto PDF** + **láminas presentación** (hoy placeholders en
  `web/src/pages/AnteproyectoPage.tsx` y `PresentacionPage.tsx`).

---

## 8. Decisiones tomadas
- Backend = repo separado (no monorepo) por la atadura web↔Vercel.
- Modelos ML **reales completos** (no ligeros) — es tesis MCD.
- Docs (anteproyecto/presentación) al final.
- Backtest **walk-forward sin look-ahead** (reentrena solo con pasado) — defendible.
- Agente: decisión **determinista y auditable**; el LLM solo explica. Ollama local
  por defecto con fallback `rule-based` (nunca rompe el pipeline). Keys de pago al final.
- IPSA: Yahoo lo descontinuó en 2019 → proxy ETF **ECH**.
- Preferencia del usuario: respuestas concisas en bullets al codear.

---

## 9. Primer paso en la nueva instancia
> "Lee `backend/HANDOFF.md` y arranca la **Fase F**: deploy del backend a Railway
>  free (Dockerfile con Python 3.12, envs Supabase service_role, endpoint
>  `/predict/{symbol}`, cron `predict --write`, CI con ruff+pytest). Backend ya
>  está en GitHub `Elcarrascou/tesis-mcd-backend` (rama `main`)."

Antes de codear:
- Backend: activar venv (`backend/.venv\Scripts\Activate.ps1`), `$env:PYTHONUTF8=1`,
  confirmar `ruff check .` y `pytest` verdes (22 tests). Git: local rama `master` ↔
  remoto `main`. **NO usar `gh` ni GitHub MCP** (no disponibles/sin auth) — git directo.
- Web (solo si se cierra el pendiente de Fase E): `cd web`, leer `web/CLAUDE.md`,
  `npm install`. Workflow lint→build→commit→push→vercel deploy→alias.

### Resumen de lo construido (Fases A–E)
| Fase | Entregable | Estado | Commit |
|---|---|---|---|
| A | FastAPI + datos Yahoo + cliente Supabase | ✅ | `52612a4` |
| B | 4 modelos ML reales (LSTM/XGB/Prophet/RF) | ✅ | `80c92d3` |
| C | Backtesting walk-forward + `model_metrics` | ✅ | `cb6e89e` |
| D | Agente IA (consolidación + LLM router + stub orden) | ✅ | `7afcb59` |
| E | Web lee real: Evaluación, decisiones IA, edge fn, `StockAnalyzer`→`/predict` | ✅ | web `b4a33f6`,`0cffc32`,`90a4252` |
| F | Docker + `/predict` + cron + CI + deploy Railway (24 tests) | ✅ live en Railway | `d4806d6` |

Archivos clave del backend:
- Modelos: `app/models/{lstm_price,xgb_signal,prophet_trend,rf_risk}.py` (interfaz `base.py`).
- Pipelines CLI: `app/pipeline/{train,predict,backtest,decide}.py`.
- Agente: `app/agent/{consolidate,llm_router,prompts,execute}.py`.
- Métricas: `app/ml/metrics.py` · Features/labels: `app/ml/dataset.py`, `app/data/features.py`.
- Tests: `tests/test_{features,dataset,health,metrics,consolidate}.py`.
