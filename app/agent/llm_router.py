"""Router de motores LLM para redactar el razonamiento de las decisiones.

Estrategia: usar **Ollama local** (gratis) en desarrollo; permitir Claude o GPT
cuando haya keys de pago (al final del proyecto). Si el motor elegido falla o no
está disponible, se cae limpiamente a `rule-based` (el razonamiento determinista
que ya trae el consolidado), de modo que el pipeline NUNCA se rompe por el LLM.

`generate_rationale` devuelve `(texto, engine)` donde `engine` queda registrado en
ai_decisions para trazabilidad.
"""

from __future__ import annotations

import httpx

from app.agent.consolidate import Consolidation
from app.agent.prompts import SYSTEM_PROMPT, build_user_prompt
from app.config import get_settings

TIMEOUT = 30.0
RULE_BASED = "rule-based"


def generate_rationale(c: Consolidation, engine: str | None = None) -> tuple[str, str]:
    """Redacta el razonamiento con el motor pedido; cae a rule-based si falla."""
    s = get_settings()
    engine = (engine or s.llm_engine or RULE_BASED).lower()
    user = build_user_prompt(c)
    try:
        if engine == "ollama":
            return _ollama(user, s.ollama_url, s.ollama_model), f"ollama:{s.ollama_model}"
        if engine == "anthropic":
            if not s.anthropic_api_key:
                raise RuntimeError("falta ANTHROPIC_API_KEY")
            text = _anthropic(user, s.anthropic_api_key, s.anthropic_model)
            return text, f"anthropic:{s.anthropic_model}"
        if engine == "openai":
            if not s.openai_api_key:
                raise RuntimeError("falta OPENAI_API_KEY")
            return _openai(user, s.openai_api_key, s.openai_model), f"openai:{s.openai_model}"
    except Exception as e:  # noqa: BLE001
        print(f"  (LLM '{engine}' no disponible: {e}; uso rule-based)")
    return c.rationale, RULE_BASED


def _ollama(user: str, url: str, model: str) -> str:
    r = httpx.post(
        f"{url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def _anthropic(user: str, api_key: str, model: str) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        json={
            "model": model,
            "max_tokens": 300,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()


def _openai(user: str, api_key: str, model: str) -> str:
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "max_tokens": 300,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
