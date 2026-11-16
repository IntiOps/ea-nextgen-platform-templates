"""HTTP adapter. Wires the use cases to FastAPI; holds no business rule.

/health   liveness + the deployed source commit (CD's smoke test checks it)
/ready    readiness (extend when the service gets dependencies)
/hello    the example use case
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from service.application.greet import Greet
from service.infrastructure.clock import SystemClock

APP_ROOT = Path(__file__).resolve().parents[3]
BUILD = APP_ROOT / "build-info.json"
REVISION = json.loads(BUILD.read_text())["revision"] if BUILD.exists() else "development"
SERVICE = os.environ.get("SERVICE_NAME", "service")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"level": record.levelname, "logger": record.name, "message": record.getMessage(),
                           "service": SERVICE, "revision": REVISION})


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
log = logging.getLogger("service")
log.addHandler(_handler)
log.setLevel(logging.INFO)
log.propagate = False

app = FastAPI(title=SERVICE, version=REVISION)
greet = Greet(SystemClock())


@app.get("/health")
def health():
    return {"status": "ok", "revision": REVISION}


@app.get("/ready")
def ready():
    return {"status": "ready"}


@app.get("/")
def root():
    return {"application": SERVICE, "revision": REVISION}


@app.get("/hello")
def hello(name: str = Query("world", max_length=200)):
    try:
        greeting = greet(name)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    log.info("greeted")
    return {"message": greeting.message, "name": greeting.name, "at": greeting.at.isoformat()}
