# PLAN FINAL — Tesis MCD USACH · Cierre 100% operativo + presentable a comisión

> Documento **vivo**. Se actualiza a medida que avanzamos: marcar `[x]` lo hecho,
> anotar fecha/commit en "Bitácora". Persiste entre instancias de chat (está en el
> repo backend, rama `main`). Complemento técnico-histórico: ver `HANDOFF.md`.
>
> Última actualización: 2026-06-15. Autor: Daniel Carrasco U. (dacarrascu@gmail.com).

---

## 0. Cómo usar este documento

- Cada tarea tiene checkbox `[ ]`. Al completarla → `[x]` + commit del cambio.
- Campos de cada fase: **Objetivo · Tareas · Archivos · Pasos manuales (usuario) ·
  Criterio de aceptación · Costo**.
- Las decisiones pendientes están en §2 (Decisiones abiertas). Resolverlas desbloquea
  el alcance exacto.
- Triggers de servicios de pago: §7 (Supabase Pro) y §8 (OpenClaw en Hostinger).

---

## 1. Estado actual (línea base)

**✅ COMPLETO y en producción (Fases A→F):**
- **Backend** FastAPI live en **https://tesis-mcd-backend-production.up.railway.app**
  (Railway). 4 modelos ML reales (LSTM/XGBoost/Prophet/Random Forest), endpoint
  `GET /predict/{symbol}`, `/health`. CI GitHub Actions (ruff + pytest, 24 tests).
  Cron diario `predict --write` → `ml_predictions`.
- **Web** live en **https://tesis-mcd-usach.vercel.app** (Vercel). Sitio marketing +
  Portal autenticado (6 páginas) + `StockAnalyzer` consume `/predict` real vía
  `VITE_API_URL`. Página Evaluación lee `model_metrics`.
- **Datos Supabase** (proyecto `PT_MCD_USACH_DCU`, id `xzedmtnouzarsslyglbe`, free):
  - `ml_predictions`: 96 filas, 6 símbolos, frescas (cron diario).
  - `model_metrics`: 92 filas, 8 símbolos — backtest walk-forward COMPLETO (4 modelos
    + benchmarks ECH/^DJI + estrategia long-only).
  - `ai_decisions`: 11 (6 reales `rule-based` + 5 demo).
  - `portfolio`(6) / `performance`(30d) / `movements`(7): **seed estático**, último
    2026-05-31, sin refresco automático.

**⚠️ Huecos para el cierre (lo que cubre este plan):**
1. Documentos comisión (anteproyecto PDF + láminas) = placeholders. **Bloqueante.**
2. Datos operacionales congelados (portfolio/performance/movements). Portal se ve detenido.
3. ~~Agente sin LLM~~ → **H1 ✅** rationale con Claude Haiku 4.5 (`engine=anthropic`).
4. ~~`decide --write` sin cron~~ → **G1 ✅** `decide-cron.yml` diario.
5. Ejecución = stub (`execute.py` `intended`); qty ya dimensionada (H3), Alpaca pendiente (Fase I).
6. ~~AUC ROC multiclase pendiente~~ → **H2 ✅** métrica `auc` en `model_metrics` + página Evaluación.

---

## 2. Decisiones abiertas (resolver para fijar alcance)

| # | Decisión | Opciones | Resuelto |
|---|---|---|---|
| D1 | Por dónde arrancar | J docs / G frescura / H agente / todo en orden | ⏳ |
| D2 | Alpaca paper trading (gratis) | Sí / No | ⏳ |
| D3 | Rationale LLM | Claude API (pago bajo) / Ollama (gratis) / rule-based | ✅ Claude API (Haiku 4.5) |
| D4 | Autoría documentos | Yo redacto borrador / esqueleto+tú rellenas / tú los provees | ⏳ |
| D5 | Supabase Pro | Cuándo (ver §7) | ⏳ |
| D6 | OpenClaw en Hostinger | Cuándo / si va (ver §8) | ⏳ |

---

## 3. Tablero de fases

| Fase | Objetivo | Prioridad | Costo | Estado |
|---|---|---|---|---|
| **G** | Frescura de datos operacionales | ALTA | Gratis | 🟡 G1+G2 ✅ (G3 opcional) |
| **H** | Riqueza del agente IA (LLM + AUC) | ALTA (académica) | H1 pago bajo, resto gratis | ✅ H1+H2+H3 |
| **I** | Ejecución paper trading (Alpaca) | MEDIA | Gratis | ⏳ |
| **J** | Documentos para comisión | **MÁXIMA (bloqueante)** | Gratis | ⏳ |
| **K** | Pulido y QA final | MEDIA | Gratis | ⏳ |

**Orden recomendado:** J ‖ G (paralelo) → H → I → K. Todo gratis salvo H1 (Claude API ~centavos).

---

## 4. Fases detalladas

### Fase G — Frescura de datos operacionales `[ALTA · gratis]`
**Objetivo:** que el portal nunca se vea congelado ante la comisión.

- [x] **G1 · Cron `decide --write` diario.** Nuevo `.github/workflows/decide-cron.yml`
  (espeja `predict-cron.yml`): `python -m app.pipeline.decide --engine rule-based --write`
  a las 11:10 UTC (10 min tras el predict-cron). Engine `rule-based` (determinista,
  gratis, sin host LLM) hasta resolver D3/H1.
  - Archivos: `.github/workflows/decide-cron.yml`.
  - Aceptación: ✅ `ai_decisions` recibe 6 filas nuevas (verificado corriendo el comando del cron).
- [x] **G2 · Snapshot operacional diario.** Nuevo `app/pipeline/snapshot.py`:
  - Recalcula `portfolio.current_price/market_value/unrealized_pnl/weight_pct` con
    precios Yahoo (`app/data/yahoo.py`).
  - Inserta fila diaria en `performance` (total_value, daily_return_pct,
    cumulative_return_pct, benchmark_return_pct vs ECH/^DJI).
  - CLI `python -m app.pipeline.snapshot --write` + cron.
  - Archivos: `app/pipeline/snapshot.py`, `app/db/supabase_client.py` (`get_portfolio`,
    `upsert_portfolio`, `get_last_performance`, `upsert_performance`),
    `.github/workflows/snapshot-cron.yml` (11:20 UTC), `tests/test_snapshot.py` (7 tests).
  - Modelo: posiciones = fuente de verdad (no se tocan); se recalcula valuación con
    precio Yahoo + caja fija `CASH_USD=5000`. total_value = equity + caja; retorno
    acum vs capital inicial (costo+caja); retorno diario vs última fila; benchmark = ECH
    desde `INCEPTION_DATE=2026-01-02`. `build_snapshot` es función pura (testeable).
  - Aceptación: ✅ `performance` tiene fila 2026-06-15 (total 52783.18, cum +20.55%,
    bench ECH +2.80%); portfolio.updated_at = hoy. **OJO:** NVDA muestra pnl muy
    negativo porque su `avg_price` seed (620) es pre-split — re-sembrar el costo si se
    quiere demo coherente (fuera de alcance G2).
- [ ] **G3 (opcional) · Backtest semanal `--write`.** Cron semanal para refrescar
  `model_metrics`. Prophet lento (~10-15 min) → `schedule` con timeout holgado.
- **Pasos manuales:** confirmar secrets del repo (`SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`) ya seteados (cron predict ya corre → OK).

### Fase H — Riqueza del agente IA `[ALTA académica]`
**Objetivo:** decisiones explicables y métrica robusta para defender los modelos.

- [x] **H1 · Rationale LLM real** (D3 resuelto → **Claude API**).
  - Modelo `claude-haiku-4-5` (barato). `anthropic_model` default en `config.py`; prompt
    endurecido a TEXTO PLANO (sin markdown) en `app/agent/prompts.py`. `decide-cron.yml`
    ahora corre `--engine anthropic` con secret `ANTHROPIC_API_KEY` (router cae a
    `rule-based` si falta). El LLM **solo reescribe** el rationale; decisión determinista.
  - Archivos: `config.py`, `app/agent/prompts.py`, `.github/workflows/decide-cron.yml`.
  - Aceptación: ✅ 6 `ai_decisions` con `engine=anthropic:claude-haiku-4-5` y rationale
    legible/específico en texto plano (verificado con `decide --engine anthropic --write`).
  - **Pasos manuales (usuario):** agregar `ANTHROPIC_API_KEY` como (a) secret del repo
    GitHub `tesis-mcd-backend` (para el cron) y (b) variable de entorno en Railway (para
    `/decide` on-demand si se usa). **ROTAR la key compartida en chat** (quedó expuesta).
- [x] **H2 · AUC ROC multiclase.** `predict_one` de XGBoost/RF ahora expone `proba`
  (dict clase→prob) vía nuevo campo `Prediction.proba` (excluido de `ml_predictions`).
  `app/ml/metrics.py::auc_macro` (One-vs-Rest macro, %); el backtest la calcula para los
  clasificadores.
  - Archivos: `app/models/base.py`, `app/models/{xgb_signal,rf_risk}.py`, `app/ml/metrics.py`,
    `app/pipeline/backtest.py`, `tests/test_metrics.py`, web `PortalEvaluacion.tsx`.
  - Aceptación: ✅ `model_metrics` con métrica `auc` (RF global 78.2%, XGBoost 53.6%);
    página Evaluación la muestra (CLASSIF_METRICS += 'auc').
- [x] **H3 · Dimensionar orden (qty).** `app/agent/execute.py::size_order` calcula la
  cantidad de acciones: buy → lleva la posición al peso objetivo (`TARGET_WEIGHT_PCT=15%`)
  escalado por confianza; sell/reduce → recorta la posición por confianza. `intended_order`
  acepta `price`/`portfolio_value`/`current_qty` opcionales (None si faltan → comportamiento
  previo). Listo para conectar en Fase I.
  - Archivos: `app/agent/execute.py`, `tests/test_consolidate.py`.
  - Aceptación: ✅ tests de sizing (buy>0, no compra si ya supera objetivo, sell ≤ posición).

### Fase I — Ejecución paper trading (Alpaca) `[MEDIA · gratis]` (según D2)
**Objetivo:** "el sistema ejecuta" — órdenes reales simuladas, sin dinero real.

- [ ] **I1 · Broker Alpaca paper.** Implementar en `app/agent/execute.py` un broker que
  envíe la orden intencionada a Alpaca **paper** API (`paper-api.alpaca.markets`) →
  registrar `movements` con `side/quantity/price/amount/alpaca_order_id`,
  status `filled`. Mantener dinero real (live) FUERA.
  - Archivos: `app/agent/execute.py`, `config.py` (`alpaca_key/secret`, `alpaca_paper=True`),
    `requirements.txt` (`alpaca-py`), `app/db/supabase_client.py` (`insert_movements`),
    `tests/test_execute.py`.
  - Pasos manuales: crear cuenta Alpaca paper (gratis) → API key/secret → setear en env.
  - Aceptación: `decide --orders --write` crea movimientos `filled` con `alpaca_order_id`;
    portal Movimientos los muestra.

### Fase J — Documentos para comisión `[MÁXIMA · BLOQUEANTE]` (según D4)
**Objetivo:** entregables formales para la defensa.

- [ ] **J1 · Anteproyecto PDF.** Documento formal: portada, resumen, problema,
  objetivos/hipótesis, marco teórico (4 modelos + IA agéntica), metodología
  (walk-forward sin look-ahead, proxy ECH del IPSA), arquitectura (Railway+Vercel+
  Supabase), resultados backtest, planificación, referencias. Generar con skill
  `docx`/`pdf` desde el material construido.
  - Archivos: `web/public/Anteproyecto_Tesis_MCD_2026.pdf`,
    `web/src/pages/AnteproyectoPage.tsx` (activar botón descarga, quitar "próximamente"),
    `web/src/data/presentation.ts` (`ANTEPROYECTO_SECTIONS.done`).
  - Aceptación: botón "Descargar PDF" funcional en la web.
- [ ] **J2 · Láminas presentación (.pptx).** Narrativa: problema → datos IPSA/ECH/Dow →
  4 modelos ML → backtest sin look-ahead → agente OpenClaw → arquitectura → demo en
  vivo → resultados/conclusiones. Generar con skill `pptx`.
  - Archivos: `web/public/Presentacion_MCD_2026.pptx` (+ miniaturas), `PresentacionPage.tsx`,
    `presentation.ts` (`SLIDES`, `PRESENTATION_STATS`).
  - Aceptación: grilla de láminas reales + descarga.
- [ ] **J3 · Guión de demo en vivo.** Doc corto: orden de pantallas, credenciales demo
  (`demo@tesis-mcd.cl` / `Portafolio2026`), símbolos a buscar, qué resaltar, plan B si
  falla la red. → `PLAN-DEMO.md` o sección en este archivo.

### Fase K — Pulido y QA final `[MEDIA · gratis]`
- [ ] **K1** Revisar las 6 páginas del portal con datos frescos + estados vacíos.
- [ ] **K2** Verificar acceso público (Vercel Deployment Protection OFF) + hoja de credenciales.
- [ ] **K3** READMEs de ambos repos + diagrama de arquitectura actualizado (incluir Railway).
- [ ] **K4** Ensayo completo de defensa (cronometrar, anticipar preguntas del comité).

---

## 5. Free vs Pago (resumen)

| Ítem | Free OK | Cuándo conviene pagar |
|---|---|---|
| Railway (backend) | Sí para dev/demo | Si el free se agota por uso/horas en la semana de defensa |
| Vercel (web) | Sí | No hace falta |
| GitHub Actions (cron + CI) | Sí | No hace falta |
| Supabase | Sí (cron diario lo mantiene activo) | **Ver §7** |
| LLM rationale | Ollama gratis (necesita host) | Claude API ~centavos (calidad, sin host) |
| Alpaca | Paper gratis | Nunca para la tesis (live = dinero real, fuera de alcance) |
| OpenClaw/Hostinger | — | **Ver §8** |

---

## 6. Checklist día de defensa (comisión)

- [ ] Supabase activo y NO pausado (ver §7).
- [ ] Backend Railway responde `/health` y `/predict/NVDA` (probar 1h antes).
- [ ] Web pública sin login wall de Vercel; portal abre con credenciales demo.
- [ ] Datos frescos (cron corrió hoy): predicciones, decisiones, performance.
- [ ] PDF anteproyecto + láminas descargables.
- [ ] Guión de demo a mano + plan B offline (capturas/grabación si cae la red).

---

## 7. ¿Cuándo pagar Supabase Pro (US$25/mes)?

**Free tier basta durante el desarrollo** porque el cron diario escribe y eso resetea
el contador de inactividad. Riesgos del free: **el proyecto se PAUSA tras ~7 días sin
actividad**, backups limitados, y egress/recursos acotados para un demo en vivo.

**Pagar Pro cuando se cumpla cualquiera:**
1. **~1 semana antes de la defensa** → garantizar uptime, evitar pausa automática,
   activar backups diarios / point-in-time recovery (seguro ante imprevistos). **(Trigger principal.)**
2. Si se **conecta OpenClaw en Hostinger** (§8) con escritura 24/7 + más egress.
3. Si la BD se acerca a límites del free (500 MB / egress) — improbable a esta escala.
4. Si se requiere un **segundo proyecto** (staging) además del de producción.

**Acción al pagar:** upgrade del proyecto `xzedmtnouzarsslyglbe` a Pro; verificar que
no se pausó; activar backups; revisar `get_advisors` (security/perf).

> Recomendación: **NO pagar todavía.** Mantener free mientras el cron lo conserve
> activo; subir a Pro en la semana previa a la defensa (o al conectar OpenClaw).

---

## 8. ¿Cuándo conectar OpenClaw en Hostinger?

**Qué es:** desplegar el agente "OpenClaw" en un VPS Hostinger para operación
**autónoma 24/7** + LLM (Ollama local gratis o Claude key) + notificaciones
(Telegram/WhatsApp). Hoy el cron vive en GitHub Actions y el backend en Railway —
suficiente para la defensa.

**Conectar OpenClaw SOLO cuando:**
1. Fases **H** (agente con LLM) e **I** (ejecución) estén **estables y probadas**.
   OpenClaw es la "puesta en producción real" del agente — no antes.
2. Se quiera la narrativa de tesis "**sistema autónomo 24/7 con alertas**" (valor
   diferencial), más allá del cron de GitHub Actions.
3. Idealmente **junto con Supabase Pro** (§7) para escritura continua confiable.

**Secuencia de conexión (cuando toque):**
1. Provisionar VPS Hostinger (Docker).
2. Desplegar la imagen del backend (mismo `Dockerfile`) en el VPS.
3. LLM: instalar **Ollama** local en el VPS (`ollama pull llama3.1`) → rationale gratis
   24/7; o usar `ANTHROPIC_API_KEY`. Setear `LLM_ENGINE`.
4. Agendar `predict`/`decide`/`snapshot` con cron/systemd en el VPS (reemplaza o
   complementa GitHub Actions).
5. Bot de notificaciones (Telegram/WhatsApp) que publique decisiones/ejecuciones.
6. Apuntar Supabase (Pro) como backend de datos; verificar egress/uptime.

> Recomendación: **OpenClaw es el ÚLTIMO paso de infraestructura.** Para aprobar la
> comisión NO es estrictamente necesario (Railway + GitHub Actions cubren la demo);
> es el "extra" que eleva la tesis a sistema productivo autónomo. Hacerlo tras J/G/H/I.

---

## 9. Bitácora (registro de avances)

| Fecha | Fase/tarea | Detalle | Commit |
|---|---|---|---|
| 2026-06-15 | F | Backend desplegado en Railway; web consume `/predict` real | bk `d4806d6`/`6b0abc4`, web `90a4252` |
| 2026-06-15 | F | Cron `predict --write` diario operativo (secrets repo seteados) | — |
| 2026-06-15 | PLAN | Creado este PLAN-FINAL.md | (este commit) |
| 2026-06-15 | G1 | Cron `decide-cron.yml` diario (engine rule-based); 6 decisiones frescas escritas | (este commit) |
| 2026-06-15 | G2 | `snapshot.py` + helpers supabase + `snapshot-cron.yml` + 7 tests; performance 2026-06-15 + portfolio revaluado | 5315d1e |
| 2026-06-16 | H1 | Rationale Claude Haiku 4.5 (prompt texto plano); decide-cron `--engine anthropic`; 6 decisiones `anthropic:claude-haiku-4-5` | (este commit) |
| 2026-06-16 | H2 | `Prediction.proba` + `auc_macro` (OvR); backtest clf re-escrito con AUC (RF 78.2% / XGB 53.6%); web Evaluación muestra AUC | (este commit) |
| 2026-06-16 | H3 | `size_order` en execute.py (qty por peso objetivo × confianza); tests sizing | (este commit) |
