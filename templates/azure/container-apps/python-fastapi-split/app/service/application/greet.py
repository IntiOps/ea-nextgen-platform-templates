"""Use case: greet someone. Depends on the Clock port, never on a concrete clock."""
from __future__ import annotations

from service.application.ports import Clock
from service.domain.greeting import Greeting


class Greet:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def __call__(self, name: str = "world") -> Greeting:
        return Greeting(name=name, at=self._clock.now())
