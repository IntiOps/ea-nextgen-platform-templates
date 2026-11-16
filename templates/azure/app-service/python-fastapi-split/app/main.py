"""Entrypoint. App Service runs ``python -m uvicorn main:app`` (infra/bicep/web.bicep); keep this name."""
from service.infrastructure.http.api import app

__all__ = ["app"]
