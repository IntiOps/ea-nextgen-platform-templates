"""A greeting: the smallest domain object that still carries a rule."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_NAME = 64


@dataclass(frozen=True)
class Greeting:
    name: str
    at: datetime

    def __post_init__(self) -> None:
        cleaned = " ".join(self.name.split())
        if not cleaned or len(cleaned) > MAX_NAME:
            raise ValueError(f"name must be 1-{MAX_NAME} characters")
        object.__setattr__(self, "name", cleaned)

    @property
    def message(self) -> str:
        return f"Hello, {self.name}!"
