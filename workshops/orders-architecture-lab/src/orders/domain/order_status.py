from enum import Enum


class OrderStatus(str, Enum):
    DRAFT = "draft"
    PLACED = "placed"
    PAID = "paid"
    CANCELLED = "cancelled"


#: Allowed transitions. Anything else is a business error, not a database error.
TRANSITIONS = {
    OrderStatus.DRAFT: {OrderStatus.PLACED, OrderStatus.CANCELLED},
    OrderStatus.PLACED: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: set(),
    OrderStatus.CANCELLED: set(),
}
