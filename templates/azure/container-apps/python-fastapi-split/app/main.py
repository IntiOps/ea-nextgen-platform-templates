"""Entrypoint. The container runs ``python -m uvicorn main:app`` from /app (Dockerfile); keep this name."""
from service.infrastructure.http.api import app

__all__ = ["app"]
