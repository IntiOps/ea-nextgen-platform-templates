"""Tax rates as configured for the payments provider. Infrastructure: it changes with the provider."""
from decimal import Decimal

_RATES = {"PE": Decimal("0.18"), "AR": Decimal("0.21"), "US": Decimal("0.00")}


def tax_rate_for(country: str) -> Decimal:
    return _RATES.get(country, Decimal("0.00"))
