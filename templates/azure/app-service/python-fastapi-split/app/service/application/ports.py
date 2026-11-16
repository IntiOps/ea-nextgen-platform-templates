"""Ports: what the use cases need from the outside world, as protocols. Adapters implement them."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
