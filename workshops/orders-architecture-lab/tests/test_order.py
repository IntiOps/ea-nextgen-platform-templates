from decimal import Decimal

import pytest

from orders.domain.errors import OrderError
from orders.domain.order import Order
from orders.domain.order_status import OrderStatus


def test_total_includes_lines_and_tax():
    order = Order("o-1", "c-1", country="PE")
    order.add_product("p-1", 2, Decimal("10.00"))
    assert order.total() == Decimal("23.60")


def test_an_empty_order_cannot_be_placed():
    with pytest.raises(OrderError):
        Order("o-1", "c-1").change_status(OrderStatus.PLACED)


def test_status_follows_the_allowed_transitions():
    order = Order("o-1", "c-1")
    order.add_product("p-1", 1, Decimal("5"))
    order.change_status(OrderStatus.PLACED)
    with pytest.raises(OrderError):
        order.change_status(OrderStatus.DRAFT)
    with pytest.raises(OrderError):
        order.add_product("p-2", 1, Decimal("1"))


@pytest.mark.parametrize(("quantity", "price"), [(0, Decimal("1")), (1, Decimal("-1"))])
def test_lines_keep_their_invariants(quantity, price):
    with pytest.raises(OrderError):
        Order("o-1", "c-1").add_product("p-1", quantity, price)
