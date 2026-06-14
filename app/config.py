"""Configuración central del backend.

Toda clave/secreto se lee del entorno (o de un archivo .env en desarrollo),
NUNCA se escribe en el código. Así el mismo código corre igual en tu PC y en
Railway, y los secretos jamás terminan en git.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Supabase ──────────────────────────────────────────────
    # service_role = salta RLS y permite ESCRIBIR. Secreto, solo backend.
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # ── CORS ──────────────────────────────────────────────────
    # Orígenes web autorizados a llamar a esta API.
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "https://tesis-mcd-usach.vercel.app",
    ]

    # ── Agente IA / LLM (Fase D) ──────────────────────────────
    # Motor por defecto: Ollama local (gratis en dev). Si no responde, el router
    # cae a 'rule-based' (razonamiento determinista). Las keys de pago se dejan
    # para el final.
    llm_engine: str = "ollama"  # ollama | anthropic | openai | rule-based
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ── App ───────────────────────────────────────────────────
    app_name: str = "Tesis MCD USACH — Backend ML"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Settings cacheado (se construye una sola vez por proceso)."""
    return Settings()
