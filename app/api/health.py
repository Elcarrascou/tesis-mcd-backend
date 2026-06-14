"""Endpoint de salud: confirma que el servicio está vivo.

Lo usa Railway (y cualquier monitor) para saber que el contenedor arrancó bien.
Es lo primero que se prueba antes de meterle complejidad al backend.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok"}
