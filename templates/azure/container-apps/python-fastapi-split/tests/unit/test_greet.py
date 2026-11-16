from datetime import datetime, timezone

import pytest

from service.application.greet import Greet
from service.domain.greeting import Greeting

NOON = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


class FixedClock:
    def now(self):
        return NOON


def test_greet_uses_the_clock_port():
    greeting = Greet(FixedClock())("Ada")
    assert greeting == Greeting(name="Ada", at=NOON)
    assert greeting.message == "Hello, Ada!"


def test_names_are_normalized():
    assert Greet(FixedClock())("  Ada   Lovelace ").name == "Ada Lovelace"


@pytest.mark.parametrize("name", ["", "   ", "x" * 65])
def test_invalid_names_are_rejected(name):
    with pytest.raises(ValueError):
        Greet(FixedClock())(name)
